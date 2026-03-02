import threading
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db, Contract
from app.schemas import AgentChatRequest, AgentChatResponse
from app.services.agent_service import agent_service
from app.services import file_storage
from app.routers.contracts import _async_reparse_process
from app.config import config


router = APIRouter(prefix="/agent", tags=["AI助手"])


@router.get("/health")
def agent_health():
    return {
        "status": "ok",
        "ark_configured": bool(config.ARK_API_KEY and config.ARK_BOT_MODEL),
        "ark_model": config.ARK_BOT_MODEL or None,
        "appbuilder_configured": bool(config.APPBUILDER_API_TOKEN and config.APPBUILDER_APP_ID),
        "appbuilder_app_id": config.APPBUILDER_APP_ID or None,
    }


@router.post("/chat/stream")
def agent_chat_stream(payload: AgentChatRequest):
    """SSE 流式端点：优先 ARK（快速逐token），回退 AppBuilder。"""
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    def event_generator():
        # 优先使用 ARK（火山引擎豆包，速度快）
        if config.ARK_API_KEY and config.ARK_BOT_MODEL:
            for chunk in agent_service.consult_with_ark_stream(
                message=message, conversation_id=payload.conversation_id
            ):
                yield f"data: {chunk}\n\n"
            return
        # 回退到 AppBuilder
        for chunk in agent_service.consult_with_appbuilder_stream(
            message=message, conversation_id=payload.conversation_id
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/probe", response_model=AgentChatResponse)
def agent_probe(payload: AgentChatRequest):
    """联调检查：仅验证咨询链路（AppBuilder/Qianfan回退）"""
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    result = agent_service.consult(message=message, conversation_id=payload.conversation_id)
    return AgentChatResponse(
        reply=result.get("reply", ""),
        operation=payload.operation,
        conversation_id=result.get("conversation_id"),
        provider=result.get("provider"),
        error_detail=result.get("error_detail"),
    )


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(payload: AgentChatRequest, db: Session = Depends(get_db)):
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    op = payload.operation or agent_service.detect_operation(message)
    if not op:
        return AgentChatResponse(reply="我没有理解你的需求，请重试。")

    if op.action == "list_contracts":
        filters = op.filters if op.filters else {}
        items = agent_service.list_contracts(db, limit=10, filters=filters)

        # 生成友好描述
        filter_desc = ""
        if filters.get("status"):
            filter_desc += f"状态为「{filters['status']}」的"
        if filters.get("contract_type"):
            filter_desc += f"「{filters['contract_type']}」类型的"
        if filters.get("department"):
            filter_desc += f"「{filters['department']}」部门的"
        if filters.get("expiring_soon"):
            filter_desc += "30天内即将到期的"

        if not items:
            return AgentChatResponse(
                reply=f"未找到{filter_desc}合同。" if filter_desc else "当前没有可用合同数据。",
                operation=op, data=[], provider="rule",
            )
        return AgentChatResponse(
            reply=f"为您找到 {len(items)} 份{filter_desc}合同：",
            operation=op,
            data=items,
            provider="rule",
        )

    if op.action == "get_contract":
        if not op.contract_id:
            return AgentChatResponse(reply="请提供合同ID，例如：查看合同16。", operation=op, provider="rule")
        item = agent_service.get_contract(db, op.contract_id)
        if not item:
            return AgentChatResponse(reply=f"未找到合同 {op.contract_id}。", operation=op, provider="rule")
        return AgentChatResponse(reply=f"已获取合同 {op.contract_id} 的详情。", operation=op, data=[item], provider="rule")

    if op.action == "delete_contract":
        if not op.contract_id:
            return AgentChatResponse(reply="删除操作需要合同ID，例如：删除合同16。", operation=op, provider="rule")

        contract = db.query(Contract).filter(Contract.id == op.contract_id, Contract.is_deleted == False).first()
        if not contract:
            return AgentChatResponse(reply=f"未找到合同 {op.contract_id}。", operation=op, provider="rule")

        if not payload.confirm:
            return AgentChatResponse(
                reply=f"请确认是否删除合同 {op.contract_id}《{contract.title}》。确认后再发送一次，并勾选确认。",
                requires_confirmation=True,
                operation=op,
                provider="rule",
            )

        contract.is_deleted = True
        db.commit()
        return AgentChatResponse(reply=f"合同 {op.contract_id} 已删除。", operation=op, provider="rule")

    if op.action == "reparse_contract":
        if not op.contract_id:
            return AgentChatResponse(reply="重新解析需要合同ID，例如：重新解析合同16。", operation=op, provider="rule")

        contract = db.query(Contract).filter(Contract.id == op.contract_id, Contract.is_deleted == False).first()
        if not contract:
            return AgentChatResponse(reply=f"未找到合同 {op.contract_id}。", operation=op, provider="rule")

        # 触发后台异步重解析
        full_path = file_storage.get_file_path(contract.file_path)
        t = threading.Thread(target=_async_reparse_process, args=(contract.id, str(full_path)))
        t.daemon = True
        t.start()
        return AgentChatResponse(reply=f"已开始后台重新解析合同 {op.contract_id}，请稍后查看结果。", operation=op, provider="rule")

    # consult：如果 ARK 已配置，快速返回标记让前端走流式，不调用慢的 AppBuilder
    if config.ARK_API_KEY and config.ARK_BOT_MODEL:
        return AgentChatResponse(
            reply="",
            operation=op,
            provider="ark",
        )

    # ARK 未配置时回退到 AppBuilder
    result = agent_service.consult(message=message, conversation_id=payload.conversation_id)
    return AgentChatResponse(
        reply=result.get("reply", ""),
        operation=op,
        conversation_id=result.get("conversation_id"),
        provider=result.get("provider"),
        error_detail=result.get("error_detail"),
    )
