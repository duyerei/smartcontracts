import re
import logging
from typing import Optional, List, Dict, Any
import requests
from sqlalchemy.orm import Session

from app.database import Contract
from app.schemas import AgentOperation
from app.services.llm_service import llm_service
from app.config import config

logger = logging.getLogger(__name__)


class AgentService:
    """合同助手：支持咨询和基础合同操作意图识别。"""

    @staticmethod
    def detect_operation(message: str) -> Optional[AgentOperation]:
        text = (message or "").strip()
        if not text:
            return None

        id_match = re.search(r"(?:合同\s*|id\s*[=:：]?\s*)(\d+)", text, re.IGNORECASE)
        contract_id = int(id_match.group(1)) if id_match else None

        if any(k in text for k in ["删除合同", "删掉合同", "删除"]):
            return AgentOperation(action="delete_contract", contract_id=contract_id)

        if any(k in text for k in ["重新解析", "重解析", "重新识别"]):
            return AgentOperation(action="reparse_contract", contract_id=contract_id)

        if any(k in text for k in ["查看合同", "合同详情", "查看详情"]) and contract_id:
            return AgentOperation(action="get_contract", contract_id=contract_id)

        list_keywords = ["合同列表", "列出合同", "查询合同", "最近合同", "查询下", "查一下",
                         "有没有", "有哪些", "到期", "快到期", "即将到期", "所有合同",
                         "帮我查", "帮我找", "筛选", "查找合同", "搜索合同",
                         "找一个", "找一份", "找个", "找出", "哪个合同", "哪些合同",
                         "金额最大", "金额最高", "金额最小", "金额最低",
                         "最新的合同", "最近的合同", "最早的合同", "最老的合同",
                         "搜索", "搜一下", "查找", "找合同", "查合同"]
        pattern_match = bool(re.search(r"(.{2,})的合同", text)) or \
                        bool(re.search(r"关于(.{2,})", text)) or \
                        bool(re.search(r"(.{2,})相关", text)) or \
                        bool(re.search(r"包含(.{2,})", text)) or \
                        bool(re.search(r"叫(.{2,})", text)) or \
                        bool(re.search(r"甲方[为是叫](.{2,})", text)) or \
                        bool(re.search(r"乙方[为是叫](.{2,})", text)) or \
                        bool(re.search(r"甲方(.{2,})", text)) or \
                        bool(re.search(r"乙方(.{2,})", text))
        if any(k in text for k in list_keywords) or pattern_match:
            filters = AgentService._extract_filters(text)
            return AgentOperation(action="list_contracts", filters=filters)

        if 2 <= len(text) <= 20 and not any(c in text for c in ["？", "?", "吗", "呢", "怎么", "如何", "什么是"]):
            filters = {"keyword": text}
            return AgentOperation(action="list_contracts", filters=filters)

        return AgentOperation(action="consult")

    @staticmethod
    def _extract_filters(text: str) -> Dict[str, Any]:
        """从用户消息中提取合同筛选条件。"""
        filters: Dict[str, Any] = {}

        status_map = {
            "待审核": ["待审核", "未审核"],
            "审核中": ["审核中", "在审核"],
            "已生效": ["已生效", "生效中", "有效"],
            "已过期": ["已过期", "过期了", "失效"],
            "已终止": ["已终止", "终止"],
        }
        for status, keywords in status_map.items():
            if any(k in text for k in keywords):
                filters["status"] = status
                break

        type_map = {
            "采购合同": ["采购"], "销售合同": ["销售"], "服务合同": ["服务"],
            "租赁合同": ["租赁"], "劳动合同": ["劳动", "劳务"],
            "技术合同": ["技术"], "综合合同": ["综合"],
        }
        for ctype, keywords in type_map.items():
            if any(k in text for k in keywords):
                filters["contract_type"] = ctype
                break

        dept_keywords = ["科技中心", "财务中心", "法务部", "市场部", "人事部", "研发部", "运营部"]
        for dept in dept_keywords:
            if dept in text:
                filters["department"] = dept
                break

        if any(k in text for k in ["快到期", "即将到期", "要到期", "快过期", "到期"]):
            filters["expiring_soon"] = True

        if any(k in text for k in ["金额最大", "金额最高"]):
            filters["order_by"] = "amount_desc"
        elif any(k in text for k in ["金额最小", "金额最低"]):
            filters["order_by"] = "amount_asc"
        elif any(k in text for k in ["最新", "最近"]):
            filters["order_by"] = "newest"
        elif any(k in text for k in ["最早", "最老", "最旧"]):
            filters["order_by"] = "oldest"

        num_match = re.search(r"(?:找|前|top)\s*(\d+)\s*(?:个|份|条)?", text, re.IGNORECASE)
        if num_match:
            filters["limit"] = int(num_match.group(1))
        elif any(k in text for k in ["找一个", "找一份", "找个", "哪个", "哪一个", "是哪", "最大的", "最小的", "最高的", "最低的"]):
            filters["limit"] = 1

        stop_words = [
            "合同列表", "列出合同", "查询合同", "最近合同", "查询下", "查一下",
            "有没有", "有哪些", "所有合同", "帮我查", "帮我找", "筛选",
            "查找合同", "搜索合同", "找一个", "找一份", "找个", "找出",
            "哪个合同", "哪些合同", "金额最大", "金额最高", "金额最小", "金额最低",
            "最新的合同", "最近的合同", "最早的合同", "最老的合同",
            "快到期", "即将到期", "要到期", "快过期", "到期",
            "待审核", "未审核", "审核中", "在审核", "已生效", "生效中",
            "已过期", "过期了", "失效", "已终止", "终止",
            "采购", "销售", "服务", "租赁", "劳动", "劳务", "技术", "综合",
            "合同", "的", "了", "吗", "呢", "吧", "啊", "哦", "嗯",
            "帮", "我", "你", "查", "找", "看", "下", "一下", "一个", "一份",
            "请", "是", "有", "哪个", "哪些", "哪一个", "是哪", "什么",
            "最大", "最小", "最高", "最低", "最新", "最近", "最早", "最老",
            "金额", "前", "个", "份", "条", "关于", "相关", "包含", "叫",
            "甲方", "乙方", "为", "名称", "公司", "方",
        ]
        for dept in ["科技中心", "财务中心", "法务部", "市场部", "人事部", "研发部", "运营部"]:
            stop_words.append(dept)

        remaining = text
        for sw in sorted(stop_words, key=len, reverse=True):
            remaining = remaining.replace(sw, " ")
        remaining = remaining.strip()
        remaining = re.sub(r"\d+", " ", remaining).strip()
        remaining = re.sub(r"\s+", " ", remaining).strip()

        if remaining and len(remaining) >= 2:
            filters["keyword"] = remaining

        return filters

    @staticmethod
    def list_contracts(db: Session, limit: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from datetime import datetime, timedelta

        query = db.query(Contract).filter(Contract.is_deleted == False)

        if filters:
            if filters.get("keyword"):
                kw = f"%{filters['keyword']}%"
                from sqlalchemy import or_
                query = query.filter(or_(
                    Contract.title.like(kw),
                    Contract.parties.like(kw),
                    Contract.contract_type.like(kw),
                    Contract.department.like(kw),
                    Contract.contract_number.like(kw),
                ))
            if filters.get("status"):
                query = query.filter(Contract.status == filters["status"])
            if filters.get("contract_type"):
                query = query.filter(Contract.contract_type == filters["contract_type"])
            if filters.get("department"):
                query = query.filter(Contract.department == filters["department"])
            if filters.get("expiring_soon"):
                now = datetime.now()
                past = now - timedelta(days=7)
                soon = now + timedelta(days=60)
                query = query.filter(
                    Contract.end_date != None,
                    Contract.end_date >= past,
                    Contract.end_date <= soon,
                )

        order_by = filters.get("order_by", "") if filters else ""
        if order_by == "amount_desc":
            query = query.filter(Contract.amount != None).order_by(Contract.amount.desc())
        elif order_by == "amount_asc":
            query = query.filter(Contract.amount != None).order_by(Contract.amount.asc())
        elif order_by == "oldest":
            query = query.order_by(Contract.created_at.asc())
        else:
            query = query.order_by(Contract.updated_at.desc())

        if filters and filters.get("limit"):
            limit = filters["limit"]

        items = query.limit(limit).all()
        return [
            {
                "id": c.id,
                "contract_number": c.contract_number,
                "title": c.title,
                "contract_type": c.contract_type,
                "department": c.department,
                "status": c.status,
                "amount": c.amount,
                "end_date": c.end_date.strftime("%Y-%m-%d") if c.end_date else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in items
        ]

    @staticmethod
    def get_contract(db: Session, contract_id: int) -> Optional[Dict[str, Any]]:
        c = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
        if not c:
            return None
        return {
            "id": c.id,
            "contract_number": c.contract_number,
            "title": c.title,
            "contract_type": c.contract_type,
            "department": c.department,
            "status": c.status,
            "parties": c.parties,
            "amount": c.amount,
            "summary": c.summary,
            "risk_level": c.risk_level,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }

    @staticmethod
    def consult_with_bailian(message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """调用阿里云百炼智能体（非流式），返回统一结构。

        API: POST https://dashscope.aliyuncs.com/api/v1/apps/{APP_ID}/completion
        """
        import json as _json

        api_key = config.DASHSCOPE_API_KEY
        app_id = config.DASHSCOPE_AGENT_APP_ID or config.DASHSCOPE_APP_ID

        if not api_key or not app_id:
            return {
                "reply": "",
                "conversation_id": session_id,
                "provider": None,
                "error_detail": "BAILIAN_NOT_CONFIGURED",
            }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        url = f"https://dashscope.aliyuncs.com/api/v1/apps/{app_id}/completion"

        payload = {
            "input": {"prompt": message},
            "parameters": {},
            "debug": {},
        }
        if session_id:
            payload["input"]["session_id"] = session_id

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=90)
            if not resp.ok:
                return {
                    "reply": "",
                    "conversation_id": session_id,
                    "provider": None,
                    "error_detail": f"BAILIAN_HTTP_{resp.status_code}",
                }
            result = resp.json()
            output = result.get("output", {})
            reply = output.get("text", "")
            new_session_id = output.get("session_id", session_id)

            if not reply:
                return {
                    "reply": "",
                    "conversation_id": new_session_id,
                    "provider": None,
                    "error_detail": f"BAILIAN_EMPTY_REPLY:{result.get('message', '')}",
                }

            return {
                "reply": reply,
                "conversation_id": new_session_id,
                "provider": "bailian",
                "error_detail": None,
            }
        except Exception as e:
            return {
                "reply": "",
                "conversation_id": session_id,
                "provider": None,
                "error_detail": f"BAILIAN_EXCEPTION:{str(e)}",
            }

    @staticmethod
    def consult_with_bailian_stream(message: str, session_id: Optional[str] = None):
        """流式调用百炼智能体，yield JSON 事件字符串（供 SSE 端点使用）。

        使用 X-DashScope-SSE: enable 头开启流式，incremental_output: true 获取增量输出。
        事件类型:
          {"event":"token","data":"累积文字"}
          {"event":"done","conversation_id":"...","provider":"bailian"}
          {"event":"error","error_detail":"..."}
        """
        import json as _json

        api_key = config.DASHSCOPE_API_KEY
        app_id = config.DASHSCOPE_AGENT_APP_ID or config.DASHSCOPE_APP_ID

        if not api_key or not app_id:
            yield _json.dumps({"event": "error", "error_detail": "BAILIAN_NOT_CONFIGURED"})
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-SSE": "enable",
        }
        url = f"https://dashscope.aliyuncs.com/api/v1/apps/{app_id}/completion"

        payload = {
            "input": {"prompt": message},
            "parameters": {"incremental_output": True},
            "debug": {},
        }
        if session_id:
            payload["input"]["session_id"] = session_id

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=90, stream=True)
            if not resp.ok:
                error_text = resp.text[:200] if resp.text else str(resp.status_code)
                yield _json.dumps({"event": "error", "error_detail": f"BAILIAN_HTTP_{resp.status_code}:{error_text}"})
                return

            full_text = ""
            new_session_id = session_id or ""

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:].strip()
                else:
                    continue

                if not data_str or data_str == "[DONE]":
                    break

                try:
                    chunk = _json.loads(data_str)
                    output = chunk.get("output", {})
                    text_piece = output.get("text", "")
                    sid = output.get("session_id", "")
                    if sid:
                        new_session_id = sid

                    if text_piece:
                        full_text += text_piece
                        yield _json.dumps({"event": "token", "data": full_text}, ensure_ascii=False)
                except _json.JSONDecodeError:
                    pass

            if full_text:
                yield _json.dumps({"event": "done", "conversation_id": new_session_id, "provider": "bailian"}, ensure_ascii=False)
            else:
                yield _json.dumps({"event": "error", "error_detail": "BAILIAN_EMPTY_REPLY"})
        except Exception as e:
            yield _json.dumps({"event": "error", "error_detail": f"BAILIAN_EXCEPTION:{str(e)}"})

    @staticmethod
    def consult_with_ark_stream(message: str, conversation_id: Optional[str] = None):
        """流式调用火山引擎 ARK（豆包），yield JSON 事件字符串。"""
        import json as _json

        api_key = config.ARK_API_KEY
        model = config.ARK_BOT_MODEL
        api_url = config.ARK_API_URL

        if not api_key or not model:
            yield _json.dumps({"event": "error", "error_detail": "ARK_NOT_CONFIGURED"})
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        system_prompt = (
            "你是AI合同管理系统的内置助手。你的职责是帮助用户管理和查询合同。\n"
            "可用能力：\n"
            "- 查询合同列表\n"
            "- 查看合同详情（需提供合同ID）\n"
            "- 重新解析合同（需提供合同ID）\n"
            "- 删除合同（需二次确认）\n\n"
            "回答要求：\n"
            "1. 用中文回答，简洁明了\n"
            "2. 不编造系统中不存在的数据\n"
            "3. 若用户要执行操作但缺少合同ID，提示补充\n"
            "4. 对于合同相关问题直接给出可操作建议\n"
            "5. 对于非合同相关的一般问题也可以友好回答"
        )

        payload = {
            "model": model,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
        }

        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=60, stream=True)
            if not resp.ok:
                error_text = resp.text[:200] if resp.text else str(resp.status_code)
                yield _json.dumps({"event": "error", "error_detail": f"ARK_HTTP_{resp.status_code}:{error_text}"})
                return

            full_text = ""
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                elif line.startswith("data:"):
                    data_str = line[5:]
                else:
                    continue
                data_str = data_str.strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = _json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_text += content
                            yield _json.dumps({"event": "token", "data": full_text}, ensure_ascii=False)
                except _json.JSONDecodeError:
                    pass

            if full_text:
                yield _json.dumps({"event": "done", "conversation_id": conversation_id or "", "provider": "ark"}, ensure_ascii=False)
            else:
                yield _json.dumps({"event": "error", "error_detail": "ARK_EMPTY_REPLY"})
        except Exception as e:
            yield _json.dumps({"event": "error", "error_detail": f"ARK_EXCEPTION:{str(e)}"})

    @staticmethod
    def consult(message: str, conversation_id: Optional[str] = None, context_text: str = "") -> Dict[str, Any]:
        """非流式咨询：优先百炼，回退到百炼LLM直接调用。"""
        bailian_result = AgentService.consult_with_bailian(message, conversation_id)
        if bailian_result.get("reply"):
            return bailian_result

        # 回退：使用百炼LLM直接调用
        prompt = f"""你是AI合同管理系统内置助手。请根据用户问题提供简明、可执行建议。

可用能力说明：
- 查询合同列表
- 查询合同详情（需合同ID）
- 重新解析合同（需合同ID）
- 删除合同（需二次确认）

回答要求：
1. 用中文回答
2. 不编造系统中不存在的数据
3. 若用户要执行操作但缺少合同ID，明确提示补充ID
4. 输出尽量简洁

用户问题：{message}

上下文：{context_text}
"""
        try:
            result = llm_service._call_bailian(prompt)
            reply = (result or "").strip() or "我可以帮你查询合同、查看详情、重新解析或删除合同。请告诉我合同ID。"
            return {
                "reply": reply,
                "conversation_id": conversation_id,
                "provider": "bailian_llm",
                "error_detail": bailian_result.get("error_detail"),
            }
        except Exception as e:
            return {
                "reply": "我可以帮你查询合同、查看详情、重新解析或删除合同。请告诉我你的具体需求。",
                "conversation_id": conversation_id,
                "provider": "rule",
                "error_detail": f"BAILIAN_EXCEPTION:{str(e)}",
            }


agent_service = AgentService()
