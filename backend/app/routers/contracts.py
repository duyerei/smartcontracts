from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date
import json
import re
from dateutil.relativedelta import relativedelta

from app.database import get_db, Contract, init_db, User
from app.schemas import ContractResponse, ContractListResponse, ContractUpdate, UploadResponse, ExtractData
from app.services import file_storage, contract_parser, llm_service
from app.auth import get_current_user

router = APIRouter(prefix="/contracts", tags=["合同管理"])

def _calculate_contract_status(end_date_str) -> str:
    """根据合同结束日期自动计算合同状态
    
    规则：
    - 合同履行中：合同在有效期内且距离到期日大于2个月
    - 即将到期：合同到期前2个月内
    - 履行完成：已过到期日
    """
    try:
        if end_date_str is None:
            return "合同履行中"
        
        end_date_str = str(end_date_str)
        
        if not end_date_str or end_date_str == "None":
            return "合同履行中"
        
        # 处理日期格式
        if isinstance(end_date_str, datetime):
            end_date = end_date_str.date()
        elif isinstance(end_date_str, date):
            end_date = end_date_str
        else:
            # 尝试解析字符串，支持 T 或空格分隔的时间格式
            date_part = str(end_date_str).split('T')[0].split(' ')[0]
            end_date = datetime.strptime(date_part, "%Y-%m-%d").date()
        
        today = date.today()
        days_until_expiry = (end_date - today).days
        
        if days_until_expiry < 0:
            # 已过到期日
            return "履行完成"
        elif days_until_expiry <= 60:  # 2个月约60天
            # 即将到期（2个月内）
            return "即将到期"
        else:
            # 合同履行中
            return "合同履行中"
    except Exception as e:
        print(f"[ERROR] _calculate_contract_status: {e}")
        return "合同履行中"

def _generate_contract_summary(extracted: dict, full_text: str = "") -> str:
    """生成完整合同摘要：签约方 + 服务期限 + 合作内容 + 服务内容 + 付款方式"""
    parts = []

    # 1. 签约方（支持三方合同）
    parties = extracted.get("parties", [])
    if parties and isinstance(parties, list):
        valid_parties = [str(p) for p in parties if p and str(p) != "待填写" and str(p).lower() != "null"]
        if len(valid_parties) >= 3:
            # 三方合同
            parts.append(f"甲方：{valid_parties[0]}\n乙方：{valid_parties[1]}\n丙方：{valid_parties[2]}")
        elif len(valid_parties) >= 2:
            # 双方合同
            parts.append(f"甲方：{valid_parties[0]}\n乙方：{valid_parties[1]}")
        elif len(valid_parties) == 1:
            parts.append(f"签约方：{valid_parties[0]}")

    # 2. 合同期限
    start_date = extracted.get("start_date", "")
    end_date = extracted.get("end_date", "")
    if start_date and end_date and start_date != end_date:
        parts.append(f"服务期限：{start_date} 至 {end_date}")

    if full_text:
        # 3. 合作内容/项目概况 - 完整提取
        cooperation = _extract_cooperation_content(full_text)
        if cooperation:
            parts.append(f"【合作内容】\n{cooperation}")

        # 4. 服务内容 - 完整提取
        service_content = _extract_service_content(full_text)
        if service_content:
            parts.append(f"【服务内容】\n{service_content}")

        # 5. 付款方式 - 完整提取（不含价格明细表）
        payment = _extract_payment_content(full_text, include_table=False)
        if payment:
            parts.append(f"【付款方式】\n{payment}")

        # 6. 价格明细表 - 单独作为表格部分
        price_table = _extract_price_table(full_text)
        if price_table:
            parts.append(f"【价格明细表】\n{price_table}")

    if parts:
        return "\n\n".join(parts)
    else:
        return "由AI自动解析提取"


def _extract_service_content(text: str) -> str:
    """从合同文本中提取完整的乙方服务/产品内容"""
    lines = []

    # 提取定义章节（第一条）中关于服务的定义 - 保留完整内容
    match = re.search(r"第一条定义\n(.*?)(?:第二条|$)", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # 提取运维服务定义 - 匹配"1.1"到句号之间的内容
        ops_match = re.search(r"1\.1[\s\S]*?运维服务[\s\S]*?是指[\s\S]*?。", content)
        if ops_match:
            lines.append(ops_match.group(0).strip().replace('\n', ' '))
        # 提取维保服务定义
        maint_match = re.search(r"1\.2[\s\S]*?维保服务[\s\S]*?是指[\s\S]*?。", content)
        if maint_match:
            lines.append(maint_match.group(0).strip().replace('\n', ' '))

    # 提取第四条双方工作内容 - 乙方部分
    match = re.search(r"4\.2乙方负责的工作内容\n(.*?)(?:甲方|第五条|$)", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # 提取每条工作内容
        items = re.findall(r"(4\.2\.\d+[^\n]+)", content)
        if items:
            lines.append("乙方工作内容：")
            for item in items[:5]:
                lines.append(item.strip().replace('\n', ' '))

    if lines:
        return "\n".join(lines)

    return ""


def _extract_cooperation_content(text: str) -> str:
    """从合同文本中提取完整的合作内容/项目概况"""
    lines = []

    # 提取第二条项目概况完整内容 - 保留换行
    match = re.search(r"第二条项目概况\n(.*?)(?:第三条|第四条|$)", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        if content:
            # 提取服务期限（2.2）
            period_match = re.search(r"(2\.2[^\n]+)", content)
            if period_match:
                lines.append(period_match.group(1).strip())
            # 提取服务地点（2.3）
            location_match = re.search(r"(2\.3[^\n]+)", content)
            if location_match:
                lines.append(location_match.group(1).strip())
            # 提取签约背景（2.4）
            bg_match = re.search(r"(2\.4[^\n]+)", content)
            if bg_match:
                lines.append(bg_match.group(1).strip())
            # 提取2.5续签条件
            renew_match = re.search(r"(2\.5[^\n]+)", content)
            if renew_match:
                lines.append(renew_match.group(1).strip())

    if lines:
        return "\n".join(lines)

    return ""


def _extract_payment_content(text: str, include_table: bool = True) -> str:
    """从合同文本中提取完整的付款方式和金额（可选包含表格）"""
    lines = []

    # 提取第五条完整内容
    match = re.search(r"第五条服务费用和付款方式\n(.*?)(?:第六条|$)", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        if content:
            # 提取5.1服务费用总额（不包含价格明细表）
            amount_match = re.search(r"5\.1([\s\S]*?)(?=价格明细表|5\.2|$)", content)
            if amount_match:
                lines.append("5.1" + amount_match.group(1).strip())

            # 提取价格明细表（可选）
            if include_table:
                table_match = re.search(r"价格明细表[：:]?\n?(.*?)(?:5\.2|付款方式|第六条|$)", content)
                if table_match:
                    table_content = table_match.group(1).strip()
                    # 格式化表格内容，便于前端识别
                    table_lines = ["【价格明细表】"]
                    for line in table_content.split('\n'):
                        line = line.strip()
                        if line:
                            table_lines.append(line)
                    lines.append("\n".join(table_lines))

            # 提取5.2付款方式
            payment_match = re.search(r"5\.2([\s\S]*?)(?=5\.3|第六条|$)", content)
            if payment_match:
                lines.append("5.2" + payment_match.group(1).strip())

    if lines:
        return "\n".join(lines)

    return ""


def _extract_price_table(text: str) -> str:
    """从合同文本中提取价格明细表"""
    # 直接提取价格明细表部分
    match = re.search(r"价格明细表[：:]?\n?(.*?)(?:5\.2|付款方式|第六条|$)", text, re.DOTALL)
    if match:
        table_content = match.group(1).strip()
        # 直接返回原始表格内容，保留格式
        lines = []
        for line in table_content.split('\n'):
            line = line.strip()
            if line and line != '价格明细表':
                # 将多个空格替换为单个空格，便于前端解析
                line = re.sub(r'\s+', ' ', line)
                lines.append(line)

        return "\n".join(lines)

    return ""


@router.on_event("startup")
def startup_event():
    init_db()

@router.get("", response_model=ContractListResponse)
def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    contract_type: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Contract).filter(Contract.is_deleted == False)
    
    if search:
        query = query.filter(
            (Contract.title.contains(search)) |
            (Contract.contract_number.contains(search)) |
            (Contract.parties.contains(search))
        )
    
    if contract_type:
        query = query.filter(Contract.contract_type == contract_type)
    
    if department:
        query = query.filter(Contract.department == department)
    
    if status:
        query = query.filter(Contract.status == status)
    
    total = query.count()
    contracts = query.order_by(Contract.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    # 自动计算合同状态
    contracts_with_status = []
    for contract in contracts:
        contract_dict = {
            "id": contract.id,
            "contract_number": contract.contract_number,
            "title": contract.title,
            "contract_type": contract.contract_type,
            "department": contract.department,
            "status": _calculate_contract_status(str(contract.end_date)),
            "parties": contract.parties,
            "amount": contract.amount,
            "currency": contract.currency,
            "signed_date": contract.signed_date.isoformat() if contract.signed_date else None,
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "file_path": contract.file_path,
            "summary": contract.summary,
            "risk_level": contract.risk_level,
            "created_at": contract.created_at,
            "updated_at": contract.updated_at,
        }
        contracts_with_status.append(contract_dict)
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "contracts": contracts_with_status
    }

@router.get("/{contract_id}")
def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    return {
        "id": contract.id,
        "contract_number": contract.contract_number,
        "title": contract.title,
        "contract_type": contract.contract_type,
        "department": contract.department,
        "status": _calculate_contract_status(str(contract.end_date)),
        "parties": contract.parties,
        "amount": contract.amount,
        "currency": contract.currency,
        "signed_date": contract.signed_date.isoformat() if contract.signed_date else None,
        "start_date": contract.start_date.isoformat() if contract.start_date else None,
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "file_path": contract.file_path,
        "summary": contract.summary,
        "risk_level": contract.risk_level,
        "risk_analysis": contract.risk_analysis,
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
    }

def _async_llm_process(contract_id: int, raw_text: str):
    """后台线程：异步执行LLM摘要提取"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return

        # LLM提取摘要
        try:
            llm_summary = llm_service.llm_service.extract_full_summary(raw_text)
            if llm_summary:
                contract.summary = llm_summary
        except Exception as e:
            print(f"[异步] LLM摘要提取失败: {e}")

        contract.updated_at = datetime.now()
        db.commit()
        print(f"[异步] 合同 {contract_id} LLM摘要提取完成")
    except Exception as e:
        print(f"[异步] 处理合同 {contract_id} 失败: {e}")
    finally:
        db.close()


@router.post("/upload", response_model=UploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    metadata_hint: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        file_path, relative_path = await file_storage.save_contract(file)
        
        parse_result = contract_parser.parse_contract(file_path, metadata_hint or "")
        
        if not parse_result["success"]:
            raise HTTPException(status_code=400, detail=f"合同解析失败: {parse_result['error']}")
        
        extracted = parse_result["data"]
        raw_text = parse_result.get("raw_text", "")
        note = parse_result.get("note", "")

        # 先用正则生成基础摘要，快速返回
        if note:
            summary = "需要手动填写信息 - " + note
        else:
            summary = _generate_contract_summary(extracted, raw_text)
        
        contract = Contract(
            contract_number=extracted["contract_number"],
            title=extracted["title"],
            contract_type=extracted["contract_type"],
            department=extracted["department"],
            status="待审核",
            parties=json.dumps(extracted["parties"], ensure_ascii=False),
            amount=extracted["amount"],
            currency="CNY",
            signed_date=datetime.strptime(extracted["signed_date"], "%Y-%m-%d") if extracted.get("signed_date") else None,
            start_date=datetime.strptime(extracted["start_date"], "%Y-%m-%d") if extracted.get("start_date") else None,
            end_date=datetime.strptime(extracted["end_date"], "%Y-%m-%d") if extracted.get("end_date") else None,
            file_path=relative_path,
            summary=summary,
            raw_text=raw_text,
            extracted_data=json.dumps(extracted, ensure_ascii=False)
        )
        
        db.add(contract)
        db.commit()
        db.refresh(contract)

        # LLM摘要放到后台线程异步执行，不阻塞上传响应
        # 使用非daemon线程，确保任务有机会完成
        if raw_text and not note:
            import threading
            t = threading.Thread(target=_async_llm_process, args=(contract.id, raw_text))
            t.daemon = False
            t.start()
        
        extract_data = ExtractData(
            contract_number=extracted["contract_number"],
            title=extracted["title"],
            parties=extracted["parties"],
            amount=extracted["amount"],
            contract_type=extracted["contract_type"],
            department=extracted["department"],
            start_date=extracted.get("start_date"),
            end_date=extracted.get("end_date")
        )
        
        return UploadResponse(
            contract_id=contract.id,
            contract_number=contract.contract_number,
            file_path=relative_path,
            message="合同上传成功，AI正在后台解析摘要",
            note=note if note else None,
            extracted_data=extract_data
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: int,
    contract_update: ContractUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    update_data = contract_update.model_dump(exclude_unset=True)
    
    if "parties" in update_data and update_data["parties"]:
        update_data["parties"] = json.dumps(update_data["parties"], ensure_ascii=False)
    
    # 处理日期转换
    if "signed_date" in update_data and update_data["signed_date"]:
        try:
            update_data["signed_date"] = datetime.strptime(update_data["signed_date"], "%Y-%m-%d")
        except:
            update_data["signed_date"] = None
    elif "signed_date" in update_data:
        update_data["signed_date"] = None
        
    if "start_date" in update_data and update_data["start_date"]:
        try:
            update_data["start_date"] = datetime.strptime(update_data["start_date"], "%Y-%m-%d")
        except:
            update_data["start_date"] = None
    elif "start_date" in update_data:
        update_data["start_date"] = None
        
    if "end_date" in update_data and update_data["end_date"]:
        try:
            update_data["end_date"] = datetime.strptime(update_data["end_date"], "%Y-%m-%d")
        except:
            update_data["end_date"] = None
    elif "end_date" in update_data:
        update_data["end_date"] = None
    
    for key, value in update_data.items():
        setattr(contract, key, value)
    
    contract.updated_at = datetime.now()
    
    # 重新计算状态
    contract.status = _calculate_contract_status(str(contract.end_date) if contract.end_date else None)
    
    db.commit()
    db.refresh(contract)
    
    return contract

@router.delete("/{contract_id}")
def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    contract.is_deleted = True
    contract.updated_at = datetime.now()
    db.commit()
    
    return {"message": "合同删除成功"}

@router.get("/{contract_id}/download")
def download_contract(
    contract_id: int,
    mode: str = Query("download"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载或预览合同文件。mode=preview 时内嵌显示，mode=download 时下载"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    full_path = file_storage.get_file_path(contract.file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if mode == "preview":
        from starlette.responses import Response
        with open(str(full_path), "rb") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"}
        )
    
    return FileResponse(
        path=str(full_path),
        filename=f"{contract.contract_number}.pdf",
        media_type="application/pdf"
    )

@router.get("/{contract_id}/analyze")
def analyze_contract_risk(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 优先使用已有的raw_text，避免重复OCR
    raw_text = contract.raw_text
    if not raw_text:
        full_path = file_storage.get_file_path(contract.file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        raw_text = contract_parser.ocr.extract_text_from_file(str(full_path))

    # 使用LLM智能分析风险
    risk_analysis = ""
    try:
        risk_analysis = llm_service.llm_service.analyze_risk(raw_text)
    except Exception as e:
        print(f"LLM风险分析失败: {e}")

    # 根据LLM结果判断风险等级
    if risk_analysis:
        high_count = risk_analysis.count("🔴")
        medium_count = risk_analysis.count("🟡")
        if high_count >= 2:
            risk_level = "high"
        elif high_count >= 1 or medium_count >= 3:
            risk_level = "medium"
        else:
            risk_level = "low"
    else:
        # LLM失败时回退到关键词分析
        risk_result = contract_parser.analyze_risk(raw_text)
        risk_level = risk_result["overall_risk"]
        risk_analysis = risk_result["summary"]

    contract.risk_level = risk_level
    contract.risk_analysis = risk_analysis
    contract.updated_at = datetime.now()
    db.commit()

    return {
        "contract_id": contract_id,
        "risk_level": risk_level,
        "risk_analysis": risk_analysis,
        "analyzed_at": datetime.now().isoformat()
    }

@router.get("/{contract_id}/text")
def get_contract_text(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同文本内容，以JSON格式返回"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 优先从数据库读取，如果没有则调用OCR
    text = contract.raw_text
    from_db = True
    if not text:
        full_path = file_storage.get_file_path(contract.file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        text = contract_parser.ocr.extract_text_from_file(str(full_path))
        from_db = False

    # 解析文本为结构化JSON
    structured = _parse_text_to_json(text, contract)

    return {
        "contract_id": contract_id,
        "text": text,
        "structured": structured,
        "text_length": len(text) if text else 0,
        "from_db": from_db
    }


def _parse_text_to_json(text: str, contract=None) -> dict:
    """将合同文本解析为结构化JSON"""
    result = {}

    # 提取甲方乙方 - 使用更宽松的匹配
    party_a_match = re.search(r"甲方[：:]\s*([^\n]{2,40})", text)
    party_b_match = re.search(r"乙方[：:]\s*([^\n]{2,40})", text)
    if party_a_match:
        result["甲方"] = party_a_match.group(1).strip()
    if party_b_match:
        result["乙方"] = party_b_match.group(1).strip()

    # 提取合同标题
    title_match = re.search(r"([^\n]{10,50}合同)", text)
    if title_match:
        result["合同名称"] = title_match.group(1).strip()

    # 提取项目概况
    project_match = re.search(r"第二条项目概况\n(.*?)(?:第三条|第四条|$)", text, re.DOTALL)
    if project_match:
        content = project_match.group(1).strip()
        project_info = {}
        period_match = re.search(r"2\.2服务期限[：:]\s*(.+?)(?=\n)", content)
        if period_match:
            project_info["服务期限"] = period_match.group(1).strip()
        location_match = re.search(r"2\.3服务地点[：:]\s*(.+?)(?=\n)", content)
        if location_match:
            project_info["服务地点"] = location_match.group(1).strip()
        bg_match = re.search(r"2\.4签约背景.*?：[：]\s*(.+?)(?=\n)", content)
        if bg_match:
            project_info["签约背景"] = bg_match.group(1).strip()
        if project_info:
            result["项目概况"] = project_info

    # 提取服务费用
    amount_match = re.search(r"服务费用总额[为是]*[：:\s]*人民币?([\d,.]+)元", text)
    if amount_match:
        result["服务费用总额"] = f"{amount_match.group(1)}元"

    # 提取付款方式
    payment_match = re.search(r"5\.2付款方式[：:]?\s*(.+?)(?:5\.3|第六条|$)", text, re.DOTALL)
    if payment_match:
        result["付款方式"] = payment_match.group(1).strip().replace('\n', ' ')

    # 提取乙方工作内容
    work_match = re.search(r"4\.2乙方负责的工作内容\n(.*?)(?:甲方|第五条|$)", text, re.DOTALL)
    if work_match:
        work_content = work_match.group(1).strip()
        items = re.findall(r"4\.2\.\d+([^；\n]+)", work_content)
        if items:
            result["乙方工作内容"] = [f.strip() for f in items[:5]]

    # 提取运维和维保服务定义
    ops_match = re.search(r"1\.1\"运维服务\".*?是指(.+?)[。]", text, re.DOTALL)
    if ops_match:
        result["运维服务定义"] = ops_match.group(1).strip()
    maint_match = re.search(r"1\.2\"维保服务\".*?是指(.+?)[。]", text, re.DOTALL)
    if maint_match:
        result["维保服务定义"] = maint_match.group(1).strip()

    return result

def _async_reparse_process(contract_id: int, file_path_str: str):
    """后台线程：异步执行重新解析"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            print(f"[异步重解析] 合同 {contract_id} 不存在")
            return

        print(f"[异步重解析] 开始解析合同 {contract_id}，文件路径: {file_path_str}")
        
        # 优先使用已有的raw_text，避免重复OCR（节省API调用和时间）
        raw_text = contract.raw_text
        extracted = {}
        
        if raw_text and len(raw_text) > 100:
            print(f"[异步重解析] 使用已有OCR文本，长度: {len(raw_text)}")
            # 从已有文本中提取基本信息
            extracted = {
                "contract_number": contract.contract_number,
                "title": contract.title,
                "parties": json.loads(contract.parties) if contract.parties else [],
                "amount": contract.amount,
                "contract_type": contract.contract_type,
                "department": contract.department,
                "signed_date": contract.signed_date.strftime("%Y-%m-%d") if contract.signed_date else None,
                "start_date": contract.start_date.strftime("%Y-%m-%d") if contract.start_date else None,
                "end_date": contract.end_date.strftime("%Y-%m-%d") if contract.end_date else None,
            }
        else:
            # 如果没有raw_text，才重新OCR
            print(f"[异步重解析] 没有已有OCR文本，重新OCR识别...")
            try:
                parse_result = contract_parser.parse_contract(file_path_str, "")
                extracted = parse_result.get("data", {})
                raw_text = parse_result.get("raw_text", "")
                
                print(f"[异步重解析] OCR解析完成，文本长度: {len(raw_text)}")
                if len(raw_text) < 500:
                    print(f"[异步重解析] 警告：文本太短，内容: {raw_text[:200]}")
                    return  # OCR失败，直接返回
            except Exception as e:
                print(f"[异步重解析] OCR解析失败: {e}")
                import traceback
                traceback.print_exc()
                return

        # LLM增强解析
        llm_result = {}
        if raw_text and len(raw_text) > 100:
            try:
                llm_result = llm_service.llm_service.parse_contract_with_llm(raw_text)
                print(f"[异步重解析] LLM解析结果: {llm_result}")
            except Exception as e:
                print(f"[异步重解析] LLM解析失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[异步重解析] 跳过LLM解析，文本长度: {len(raw_text)}")

        if llm_result:
            extracted = _merge_llm_result(extracted, llm_result)

        # LLM生成摘要
        summary = ""
        try:
            llm_summary = llm_service.llm_service.extract_full_summary(raw_text)
            if llm_summary:
                summary = llm_summary
                print(f"[异步重解析] LLM摘要提取成功，长度: {len(summary)}")
            else:
                print(f"[异步重解析] LLM摘要提取返回空")
        except Exception as e:
            print(f"[异步重解析] LLM摘要提取失败: {e}")
            import traceback
            traceback.print_exc()

        if not summary:
            summary = _generate_contract_summary(extracted, raw_text)
            print(f"[异步重解析] 使用基础摘要，长度: {len(summary)}")

        # 更新所有字段
        # 优先使用LLM识别的结果
        if llm_result.get("甲方") or llm_result.get("乙方"):
            parties_list = []
            if llm_result.get("甲方"):
                parties_list.append(llm_result["甲方"])
            if llm_result.get("乙方"):
                parties_list.append(llm_result["乙方"])
            if llm_result.get("丙方") and llm_result.get("丙方") != "null":
                parties_list.append(llm_result["丙方"])
            contract.parties = json.dumps(parties_list, ensure_ascii=False)
            print(f"[异步重解析] 更新甲乙方: {parties_list}")
        else:
            contract.parties = json.dumps(extracted.get("parties", []), ensure_ascii=False)
            print(f"[异步重解析] 使用OCR提取的甲乙方: {extracted.get('parties', [])}")
        
        contract.summary = summary
        contract.raw_text = raw_text
        
        # 优先使用LLM识别的合同名称
        if llm_result.get("合同名称"):
            contract.title = llm_result["合同名称"]
            print(f"[异步重解析] 更新合同名称: {contract.title}")
        else:
            contract.title = extracted.get("title", contract.title)
            print(f"[异步重解析] 使用OCR提取的合同名称: {contract.title}")
        
        contract.contract_type = extracted.get("contract_type", contract.contract_type)
        contract.department = extracted.get("department", contract.department)
        
        # 优先使用LLM识别的金额
        if llm_result.get("服务费用总额"):
            # 尝试从大写数字中提取金额
            amount_str = llm_result["服务费用总额"]
            # 简单处理：提取数字
            import re
            numbers = re.findall(r'\d+\.?\d*', amount_str.replace(',', '').replace('，', ''))
            if numbers:
                try:
                    contract.amount = float(numbers[0])
                except:
                    pass
        elif extracted.get("amount"):
            contract.amount = extracted.get("amount")
        
        # 更新日期字段 - 优先使用LLM识别的日期
        # 签订日期
        if llm_result.get("签订日期") and llm_result.get("签订日期") != "null":
            date_str = llm_result["签订日期"]
            for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                try:
                    contract.signed_date = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
        elif "签订日期" in llm_result and (llm_result["签订日期"] is None or llm_result["签订日期"] == "null"):
            # LLM明确返回None或"null"，清空签订日期
            contract.signed_date = None
        elif extracted.get("signed_date"):
            date_str = extracted["signed_date"]
            for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                try:
                    contract.signed_date = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
        
        # 服务期限开始日期
        if llm_result.get("服务期限开始日期") and llm_result.get("服务期限开始日期") != "null":
            date_str = llm_result["服务期限开始日期"]
            for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                try:
                    contract.start_date = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
        elif "服务期限开始日期" in llm_result and (llm_result["服务期限开始日期"] is None or llm_result["服务期限开始日期"] == "null"):
            # LLM明确返回None或"null"，清空开始日期
            contract.start_date = None
            print(f"[异步重解析] 清空start_date（LLM返回None）")
        elif extracted.get("start_date"):
            date_str = extracted["start_date"]
            for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                try:
                    contract.start_date = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
        
        # 服务期限结束日期
        if llm_result.get("服务期限结束日期") and llm_result.get("服务期限结束日期") != "null":
            date_str = llm_result["服务期限结束日期"]
            for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                try:
                    contract.end_date = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
        elif "服务期限结束日期" in llm_result and (llm_result["服务期限结束日期"] is None or llm_result["服务期限结束日期"] == "null"):
            # LLM明确返回None或"null"，清空结束日期
            contract.end_date = None
            print(f"[异步重解析] 清空end_date（LLM返回None）")
        elif extracted.get("end_date"):
            date_str = extracted["end_date"]
            for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                try:
                    contract.end_date = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
        
        contract.extracted_data = json.dumps(extracted, ensure_ascii=False)
        contract.updated_at = datetime.now()

        db.commit()
        print(f"[异步重解析] 合同 {contract_id} 重新解析完成")
    except Exception as e:
        print(f"[异步重解析] 合同 {contract_id} 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@router.post("/{contract_id}/reparse")
def reparse_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """重新解析合同，后台异步执行"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    full_path = file_storage.get_file_path(contract.file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 先将摘要标记为基础版，触发前端轮询
    contract.summary = _generate_contract_summary({}, contract.raw_text or "")
    contract.updated_at = datetime.now()
    db.commit()

    # 使用非daemon线程，确保任务完成
    # 虽然uvicorn reload会中断，但至少能在不reload的情况下正常工作
    import threading
    t = threading.Thread(target=_async_reparse_process, args=(contract_id, str(full_path)))
    t.daemon = False  # 改为非daemon，让线程有机会完成
    t.start()

    return {
        "contract_id": contract_id,
        "message": "正在后台重新解析，请稍候刷新查看"
    }


def _merge_llm_result(extracted: dict, llm_result: dict) -> dict:
    """合并LLM解析结果与原有结果（支持三方合同和日期）"""
    result = extracted.copy()

    # 甲方
    if llm_result.get("甲方"):
        parties = result.get("parties", [])
        if isinstance(parties, list) and len(parties) > 0:
            parties[0] = llm_result["甲方"]
        else:
            parties = [llm_result.get("甲方"), ""]
        result["parties"] = parties

    # 乙方
    if llm_result.get("乙方"):
        parties = result.get("parties", [])
        if isinstance(parties, list) and len(parties) > 1:
            parties[1] = llm_result["乙方"]
        elif isinstance(parties, list) and len(parties) == 1:
            parties.append(llm_result["乙方"])
        else:
            parties = ["", llm_result.get("乙方")]
        result["parties"] = parties

    # 丙方（如果存在）
    if llm_result.get("丙方") and llm_result.get("丙方") != "null":
        parties = result.get("parties", [])
        if isinstance(parties, list):
            # 确保parties至少有2个元素
            while len(parties) < 2:
                parties.append("")
            # 添加或更新丙方
            if len(parties) > 2:
                parties[2] = llm_result["丙方"]
            else:
                parties.append(llm_result["丙方"])
        else:
            parties = ["", "", llm_result.get("丙方")]
        result["parties"] = parties

    # 签订日期
    if llm_result.get("签订日期") and llm_result.get("签订日期") != "null":
        result["signed_date"] = llm_result["签订日期"]
    
    # 服务期限开始日期
    if llm_result.get("服务期限开始日期") and llm_result.get("服务期限开始日期") != "null":
        result["start_date"] = llm_result["服务期限开始日期"]
    
    # 服务期限结束日期（可能为null）
    if llm_result.get("服务期限结束日期") and llm_result.get("服务期限结束日期") != "null":
        result["end_date"] = llm_result["服务期限结束日期"]
    elif llm_result.get("服务期限结束日期") == "null":
        # 如果LLM明确返回null，说明合同没有结束日期
        result["end_date"] = None

    # 保存LLM结果到extracted_data
    result["llm_data"] = llm_result

    return result


def _generate_contract_summary_with_llm(extracted: dict, raw_text: str, llm_result: dict = None) -> str:
    """使用LLM结果生成摘要（支持三方合同）"""
    if not llm_result or not raw_text:
        return _generate_contract_summary(extracted, raw_text)

    parts = []

    # 1. 签约方（支持三方合同）
    parties = extracted.get("parties", [])
    if parties and isinstance(parties, list):
        valid_parties = [str(p) for p in parties if p and str(p) != "待填写" and str(p).lower() != "null"]
        if len(valid_parties) >= 3:
            # 三方合同
            parts.append(f"甲方：{valid_parties[0]}\n乙方：{valid_parties[1]}\n丙方：{valid_parties[2]}")
        elif len(valid_parties) >= 2:
            # 双方合同
            parts.append(f"甲方：{valid_parties[0]}\n乙方：{valid_parties[1]}")
        elif len(valid_parties) == 1:
            parts.append(f"签约方：{valid_parties[0]}")

    # 2. 合作内容（使用LLM结果）
    cooperation = llm_result.get("合作内容") or llm_result.get("签约背景") or ""
    if cooperation:
        parts.append(f"【合作内容】\n{cooperation}")

    # 3. 服务内容（使用LLM结果）
    service = llm_result.get("乙方工作内容") or llm_result.get("服务内容") or ""
    if service:
        # 可能是列表，转换为字符串
        if isinstance(service, list):
            service = "\n".join([f"- {s}" for s in service])
        parts.append(f"【服务内容】\n{service}")

    # 4. 付款方式（使用LLM结果）- 不含价格明细表
    payment_parts = []
    if llm_result.get("服务费用总额"):
        payment_parts.append(f"服务费用总额：{llm_result.get('服务费用总额')}")
    if llm_result.get("付款方式"):
        payment = llm_result.get("付款方式")
        if isinstance(payment, list):
            payment = "\n".join([f"- {p}" for p in payment])
        payment_parts.append(f"付款方式：\n{payment}")

    if payment_parts:
        parts.append(f"【付款方式】\n" + "\n".join(payment_parts))

    # 5. 价格明细表 - 使用LLM提取
    try:
        price_table = llm_service.llm_service.extract_price_table(raw_text)
        if price_table:
            parts.append(f"【价格明细表】\n{price_table}")
        else:
            # 如果LLM失败，回退到正则提取
            price_table = _extract_price_table(raw_text)
            if price_table:
                parts.append(f"【价格明细表】\n{price_table}")
    except Exception as e:
        print(f"LLM价格明细表提取失败: {e}")
        # 回退到正则提取
        price_table = _extract_price_table(raw_text)
        if price_table:
            parts.append(f"【价格明细表】\n{price_table}")

    # 6. 发票要求
    if llm_result.get("发票要求"):
        parts.append(f"【发票要求】\n{llm_result.get('发票要求')}")

    if parts:
        return "\n\n".join(parts)
    else:
        return _generate_contract_summary(extracted, raw_text)
