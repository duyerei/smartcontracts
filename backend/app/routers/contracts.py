from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date
import json
import re
from dateutil.relativedelta import relativedelta

from app.database import get_db, Contract, init_db, User, ContractAttachment, Supplement
from app.schemas import ContractResponse, ContractListResponse, ContractUpdate, UploadResponse, ExtractData
from app.services import file_storage, contract_parser, llm_service
from app.auth import get_current_user, verify_token

def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """可选认证：有 Authorization header 时验证，没有时返回 None（允许 query token 兜底）"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return verify_token(token, db)
    return None

router = APIRouter(prefix="/contracts", tags=["合同管理"])

# LLM 返回的无效值列表
_INVALID_LLM_VALUES = {"未提及", "未知", "无", "null", "None", "N/A", "不详", "未识别", "未找到", "暂无", ""}

def _is_valid_llm_value(val) -> bool:
    """判断 LLM 返回值是否有效（非空、非占位符）"""
    if val is None:
        return False
    s = str(val).strip()
    return s not in _INVALID_LLM_VALUES

def _extract_title_from_text(text: str) -> str:
    """从合同原文中用正则提取合同名称作为兜底"""
    if not text:
        return ""
    # 匹配常见合同标题模式
    patterns = [
        r'(?:^|\n)\s*([\u4e00-\u9fa5A-Za-z0-9（）()]+(?:合同|协议|合约)(?:书|函)?)\s*(?:\n|$)',
        r'([\u4e00-\u9fa5]{4,30}(?:服务合同|采购合同|租赁合同|保密协议|框架协议|补充协议|合作协议|委托合同|劳动合同|技术合同))',
    ]
    for p in patterns:
        m = re.search(p, text[:500])
        if m:
            title = m.group(1).strip()
            if len(title) >= 4:
                return title
    return ""

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

@router.get("")
def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    contract_type: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    sort_field: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 全局查出所有补充协议关联（linked_contract_id 是子合同，不应出现在主列表中）
    all_supplement_rows = db.query(Supplement.contract_id, Supplement.linked_contract_id).filter(
        Supplement.linked_contract_id != None,
        Supplement.is_deleted == False
    ).all()
    # 所有被关联为补充协议的合同ID（这些不出现在主列表）
    global_child_ids = set(row.linked_contract_id for row in all_supplement_rows)
    # 主合同 -> [子合同ID列表]
    global_supplement_map: dict = {}
    for row in all_supplement_rows:
        global_supplement_map.setdefault(row.contract_id, []).append(row.linked_contract_id)

    # 主查询：排除所有子合同
    query = db.query(Contract).filter(
        Contract.is_deleted == False,
        ~Contract.id.in_(global_child_ids) if global_child_ids else True
    )

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

    # 排序
    field_map = {
        'contract_number': Contract.contract_number,
        'title': Contract.title,
        'contract_type': Contract.contract_type,
        'department': Contract.department,
        'amount': Contract.amount,
        'signed_date': Contract.signed_date,
        'start_date': Contract.start_date,
        'status': Contract.status,
        'updated_at': Contract.updated_at,
    }
    sort_column = field_map.get(sort_field or '', Contract.updated_at)
    if sort_order == 'asc':
        contracts = query.order_by(sort_column.asc()).offset((page - 1) * page_size).limit(page_size).all()
    else:
        contracts = query.order_by(sort_column.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 批量加载本页主合同涉及的子合同详情
    page_contract_ids = [c.id for c in contracts]
    needed_child_ids = []
    for cid in page_contract_ids:
        needed_child_ids.extend(global_supplement_map.get(cid, []))

    linked_contracts_map: dict = {}
    if needed_child_ids:
        for lc in db.query(Contract).filter(Contract.id.in_(needed_child_ids), Contract.is_deleted == False).all():
            linked_contracts_map[lc.id] = lc

    def _contract_dict(c, is_child=False, children=None):
        return {
            "id": c.id,
            "contract_number": c.contract_number,
            "title": c.title,
            "contract_type": c.contract_type,
            "department": c.department,
            "status": _calculate_contract_status(str(c.end_date)),
            "parties": c.parties or "",
            "amount": c.amount,
            "currency": c.currency,
            "signed_date": c.signed_date.isoformat() if c.signed_date else None,
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "file_path": c.file_path or "",
            "original_filename": c.original_filename if hasattr(c, 'original_filename') else "",
            "summary": c.summary if not is_child else None,
            "risk_level": c.risk_level if not is_child else None,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "source": c.source,
            "is_supplement_child": is_child,
            "supplement_children": children or [],
        }

    contracts_with_status = []
    for contract in contracts:
        child_ids = global_supplement_map.get(contract.id, [])
        children = [
            _contract_dict(linked_contracts_map[cid], is_child=True)
            for cid in child_ids if cid in linked_contracts_map
        ]
        contracts_with_status.append(_contract_dict(contract, is_child=False, children=children))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "contracts": contracts_with_status
    }

@router.get("/contract-types")
def get_contract_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取数据库中已有的合同类型列表（去重排序）"""
    rows = db.query(Contract.contract_type).filter(
        Contract.is_deleted == False,
        Contract.contract_type != None,
        Contract.contract_type != ""
    ).distinct().all()
    types = sorted(set(r[0] for r in rows if r[0]))
    return {"types": types}

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
        "parties": contract.parties or "",
        "amount": contract.amount,
        "currency": contract.currency,
        "signed_date": contract.signed_date.isoformat() if contract.signed_date else None,
        "start_date": contract.start_date.isoformat() if contract.start_date else None,
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "file_path": contract.file_path or "",
        "original_filename": contract.original_filename or "",
        "summary": contract.summary,
        "risk_level": contract.risk_level,
        "risk_analysis": contract.risk_analysis,
        "extracted_data": contract.extracted_data,
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
        # OA系统字段
        "source": contract.source,
        "oa_id": contract.oa_id,
        "applicant": contract.applicant,
        "position": contract.position,
        "company": contract.company,
        "counterparty": contract.counterparty,
        "counterparty_contact": contract.counterparty_contact,
        "counterparty_address": contract.counterparty_address,
        "payment_type": contract.payment_type,
        "copies": contract.copies,
        "raw_data": contract.raw_data,
    }

def _async_full_parse(contract_id: int, file_path: str, metadata_hint: str):
    """后台线程：完整的 OCR提取 + 正则解析 + LLM增强"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return

        print(f"[异步解析] 开始解析合同 {contract_id}, 文件: {file_path}")

        # 第1步：OCR + 正则解析
        parse_result = contract_parser.parse_contract(file_path, metadata_hint)
        extracted = parse_result["data"]
        raw_text = parse_result.get("raw_text", "")
        note = parse_result.get("note", "")

        # 更新基础字段
        contract.contract_number = extracted["contract_number"]
        contract.title = extracted["title"]
        contract.contract_type = extracted["contract_type"]
        contract.department = extracted["department"]
        contract.parties = json.dumps(extracted["parties"], ensure_ascii=False)
        contract.amount = extracted["amount"]
        contract.raw_text = raw_text
        contract.extracted_data = json.dumps(extracted, ensure_ascii=False)

        if extracted.get("signed_date"):
            try:
                contract.signed_date = datetime.strptime(extracted["signed_date"], "%Y-%m-%d")
            except Exception:
                pass
        if extracted.get("start_date"):
            try:
                contract.start_date = datetime.strptime(extracted["start_date"], "%Y-%m-%d")
            except Exception:
                pass
        if extracted.get("end_date"):
            try:
                contract.end_date = datetime.strptime(extracted["end_date"], "%Y-%m-%d")
            except Exception:
                pass

        # 生成基础摘要
        if note:
            contract.summary = "需要手动填写信息 - " + note
        else:
            contract.summary = _generate_contract_summary(extracted, raw_text)

        contract.updated_at = datetime.now()
        db.commit()
        print(f"[异步解析] 合同 {contract_id} OCR+正则解析完成, title={contract.title}, text_len={len(raw_text)}")

        # 第2步：LLM增强（如果有文本且非OCR失败）
        if raw_text and not note:
            _async_llm_process_with_db(db, contract, raw_text)

    except Exception as e:
        print(f"[异步解析] 合同 {contract_id} 解析失败: {e}")
        # 标记解析失败
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if contract and contract.title == "解析中...":
                contract.title = "解析失败"
                contract.summary = f"自动解析失败: {str(e)}"
                contract.updated_at = datetime.now()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _async_llm_process_with_db(db, contract, raw_text: str):
    """在已有db session中执行LLM增强（供_async_full_parse调用）"""
    try:
        # 提取结构化字段
        llm_result = llm_service.llm_service.parse_contract_with_llm(raw_text)
        if llm_result:
            llm_title = llm_result.get("合同名称", "")
            if _is_valid_llm_value(llm_title):
                contract.title = llm_title

            parties_list = []
            for key in ["甲方", "乙方"]:
                v = llm_result.get(key)
                if _is_valid_llm_value(v):
                    parties_list.append(v)
            if llm_result.get("丙方") and _is_valid_llm_value(llm_result["丙方"]):
                parties_list.append(llm_result["丙方"])
            if parties_list:
                contract.parties = json.dumps(parties_list, ensure_ascii=False)

            if llm_result.get("服务费用总额"):
                amount_str = str(llm_result["服务费用总额"])
                numbers = re.findall(r'[\d]+\.?\d*', amount_str.replace(',', '').replace('，', ''))
                if numbers:
                    try:
                        contract.amount = float(numbers[0])
                    except Exception:
                        pass

            def _try_parse_date(date_str):
                if not date_str or date_str in (None, "null", ""):
                    return None
                for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                    try:
                        return datetime.strptime(str(date_str), fmt)
                    except Exception:
                        continue
                return None

            if "签订日期" in llm_result:
                d = _try_parse_date(llm_result["签订日期"])
                if d:
                    contract.signed_date = d
            if "服务期限开始日期" in llm_result:
                d = _try_parse_date(llm_result["服务期限开始日期"])
                if d:
                    contract.start_date = d
            if "服务期限结束日期" in llm_result:
                d = _try_parse_date(llm_result["服务期限结束日期"])
                if d:
                    contract.end_date = d
    except Exception as e:
        print(f"[异步] LLM结构化字段提取失败: {e}")

    try:
        llm_summary = llm_service.llm_service.extract_full_summary(raw_text)
        if llm_summary:
            contract.summary = llm_summary
    except Exception as e:
        print(f"[异步] LLM摘要提取失败: {e}")

    contract.updated_at = datetime.now()
    db.commit()
    print(f"[异步] 合同 {contract.id} LLM处理完成")


def _async_llm_process(contract_id: int, raw_text: str):
    """后台线程：异步执行LLM摘要提取 + 结构化字段更新"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return

        # 1. 先提取结构化字段（标题、甲乙方、金额、日期等）—— 速度较快，先更新标题
        try:
            llm_result = llm_service.llm_service.parse_contract_with_llm(raw_text)
            if llm_result:
                # 合同名称（过滤无效值，兜底从原文提取）
                llm_title = llm_result.get("合同名称", "")
                if _is_valid_llm_value(llm_title):
                    contract.title = llm_title
                    print(f"[异步] 更新合同名称: {contract.title}")
                elif contract.title in _INVALID_LLM_VALUES or not contract.title:
                    fallback_title = _extract_title_from_text(raw_text)
                    if fallback_title:
                        contract.title = fallback_title
                        print(f"[异步] 从原文提取合同名称: {contract.title}")

                # 甲乙方（过滤无效值）
                parties_list = []
                for key in ["甲方", "乙方"]:
                    v = llm_result.get(key)
                    if _is_valid_llm_value(v):
                        parties_list.append(v)
                if llm_result.get("丙方") and _is_valid_llm_value(llm_result["丙方"]):
                    parties_list.append(llm_result["丙方"])
                if parties_list:
                    contract.parties = json.dumps(parties_list, ensure_ascii=False)
                    print(f"[异步] 更新甲乙方: {parties_list}")

                # 金额
                if llm_result.get("服务费用总额"):
                    amount_str = str(llm_result["服务费用总额"])
                    numbers = re.findall(r'[\d]+\.?\d*', amount_str.replace(',', '').replace('，', ''))
                    if numbers:
                        try:
                            contract.amount = float(numbers[0])
                            print(f"[异步] 更新金额: {contract.amount}")
                        except Exception:
                            pass

                # 日期字段
                def _try_parse_date(date_str):
                    if not date_str or date_str in (None, "null", ""):
                        return None
                    for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                        try:
                            return datetime.strptime(str(date_str), fmt)
                        except Exception:
                            continue
                    return None

                if "签订日期" in llm_result:
                    d = _try_parse_date(llm_result["签订日期"])
                    if d:
                        contract.signed_date = d
                if "服务期限开始日期" in llm_result:
                    d = _try_parse_date(llm_result["服务期限开始日期"])
                    if d:
                        contract.start_date = d
                if "服务期限结束日期" in llm_result:
                    d = _try_parse_date(llm_result["服务期限结束日期"])
                    if d:
                        contract.end_date = d
        except Exception as e:
            print(f"[异步] LLM结构化字段提取失败: {e}")

        # 2. 提取摘要（较慢，放在结构化字段之后）
        try:
            llm_summary = llm_service.llm_service.extract_full_summary(raw_text)
            if llm_summary:
                contract.summary = llm_summary
                print(f"[异步] LLM摘要提取成功，长度: {len(llm_summary)}")
        except Exception as e:
            print(f"[异步] LLM摘要提取失败: {e}")

        contract.updated_at = datetime.now()
        db.commit()
        print(f"[异步] 合同 {contract_id} LLM处理完成")
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
        
        # 生成临时合同编号
        contract_number = f"CT-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
        
        # 立即创建合同记录（标记为解析中），快速返回
        contract = Contract(
            contract_number=contract_number,
            title="解析中...",
            contract_type="其他",
            department="其他",
            status="待审核",
            parties="[]",
            amount=None,
            currency="CNY",
            file_path=relative_path,
            original_filename=file.filename,
            summary="正在进行OCR识别与智能解析，请稍候...",
            raw_text="",
            extracted_data=json.dumps({"parsing": True}, ensure_ascii=False)
        )
        
        db.add(contract)
        db.commit()
        db.refresh(contract)

        # OCR + 解析 + LLM 全部放到后台线程异步执行
        import threading
        t = threading.Thread(
            target=_async_full_parse,
            args=(contract.id, str(file_storage.get_file_path(relative_path)), metadata_hint or "")
        )
        t.daemon = False
        t.start()
        
        return UploadResponse(
            contract_id=contract.id,
            contract_number=contract.contract_number,
            file_path=relative_path,
            message="合同上传成功，正在后台解析中",
            note=None,
            extracted_data=ExtractData(
                contract_number=contract_number,
                title="解析中...",
                parties=[],
                amount=None,
                contract_type="其他",
                department="其他",
                start_date=None,
                end_date=None
            )
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


@router.post("/{contract_id}/attachments/upload")
async def upload_contract_attachment(
    contract_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为合同上传附件"""
    from app.services import file_storage
    from app.database import ContractAttachment

    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    content = await file.read()
    file_size = len(content)

    # 保存文件
    import uuid, os
    file_ext = os.path.splitext(file.filename or "")[1]
    stored_name = f"{uuid.uuid4()}{file_ext}"
    rel_path = f"contracts/{stored_name}"
    save_path = file_storage.get_file_path(rel_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(save_path), "wb") as f:
        f.write(content)

    attachment = ContractAttachment(
        contract_id=contract_id,
        file_name=file.filename,
        file_path=rel_path,
        file_size=file_size,
        attachment_type="uploaded",
        is_deleted=False,
        created_at=datetime.now(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return {
        "id": attachment.id,
        "file_name": attachment.file_name,
        "file_size": attachment.file_size,
        "attachment_type": attachment.attachment_type,
        "created_at": attachment.created_at.isoformat(),
    }

@router.get("/{contract_id}/attachments")
def get_contract_attachments(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同附件列表"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    attachments = db.query(ContractAttachment).filter(
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).order_by(ContractAttachment.is_primary.desc(), ContractAttachment.created_at.asc()).all()

    return {
        "attachments": [
            {
                "id": att.id,
                "file_name": att.file_name,
                "file_path": att.file_path,
                "file_size": att.file_size or 0,
                "file_url": att.file_url,
                "attachment_type": att.attachment_type,
                "is_primary": att.is_primary,
                "created_at": att.created_at.isoformat() if att.created_at else "",
            }
            for att in attachments
        ]
    }

@router.get("/{contract_id}/attachments/{attachment_id}/download")
def download_contract_attachment(
    contract_id: int,
    attachment_id: int,
    mode: str = Query("download"),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """下载或预览合同附件。mode=preview 时内嵌显示，mode=download 时下载。支持 token query 参数。"""
    # 认证
    current_user = None
    auth = request.headers.get("Authorization", "") if request else ""
    if auth.startswith("Bearer "):
        current_user = verify_token(auth[7:], db)
    if current_user is None and token:
        current_user = verify_token(token, db)
    if current_user is None:
        raise HTTPException(status_code=401, detail="未授权")

    attachment = db.query(ContractAttachment).filter(
        ContractAttachment.id == attachment_id,
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")

    if not attachment.file_path:
        raise HTTPException(status_code=404, detail="附件文件路径为空")

    full_path = file_storage.get_file_path(attachment.file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="附件文件不存在")

    import mimetypes
    ext = full_path.suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    media_type = mime_map.get(ext, mimetypes.guess_type(str(full_path))[0] or "application/octet-stream")

    if mode == "preview":
        from starlette.responses import FileResponse as StarletteFileResponse
        return StarletteFileResponse(
            path=str(full_path),
            media_type=media_type,
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "private, max-age=3600",
            }
        )

    return FileResponse(
        path=str(full_path),
        filename=attachment.file_name or f"attachment{ext}",
        media_type=media_type
    )

@router.put("/{contract_id}/attachments/{attachment_id}/set-primary")
def set_primary_attachment(
    contract_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """设置主附件"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 先清除该合同所有附件的主附件标记
    db.query(ContractAttachment).filter(
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).update({"is_primary": False})

    # 设置目标附件为主附件
    attachment = db.query(ContractAttachment).filter(
        ContractAttachment.id == attachment_id,
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")

    attachment.is_primary = True
    db.commit()

    return {"message": "主附件设置成功", "attachment_id": attachment_id}

@router.get("/{contract_id}/download")
def download_contract(
    contract_id: int,
    mode: str = Query("download"),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """下载或预览合同文件。mode=preview 时内嵌显示，mode=download 时下载。支持 token query 参数（用于 iframe 直接加载）"""
    # 优先用 Authorization header，其次用 query token
    current_user = None
    auth = request.headers.get("Authorization", "") if request else ""
    if auth.startswith("Bearer "):
        current_user = verify_token(auth[7:], db)
    if current_user is None and token:
        current_user = verify_token(token, db)
    if current_user is None:
        raise HTTPException(status_code=401, detail="未授权")
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    # OA导入的合同没有file_path
    if not contract.file_path:
        raise HTTPException(status_code=404, detail="OA导入的合同没有主文件，请从附件清单中选择要预览的文件")
    
    full_path = file_storage.get_file_path(contract.file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 根据文件扩展名确定 content-type
    import mimetypes
    ext = full_path.suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    media_type = mime_map.get(ext, mimetypes.guess_type(str(full_path))[0] or "application/octet-stream")
    
    if mode == "preview":
        from starlette.responses import FileResponse as StarletteFileResponse
        import os
        file_size = os.path.getsize(str(full_path))
        return StarletteFileResponse(
            path=str(full_path),
            media_type=media_type,
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "private, max-age=3600",
                "ETag": f'"{contract_id}-{int(full_path.stat().st_mtime)}"',
            }
        )
    
    # 下载时用原始文件扩展名
    download_name = f"{contract.contract_number or contract.title or 'contract'}{ext}"
    return FileResponse(
        path=str(full_path),
        filename=download_name,
        media_type=media_type
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
        llm_title = llm_result.get("合同名称", "")
        if _is_valid_llm_value(llm_title):
            contract.title = llm_title
            print(f"[异步重解析] 更新合同名称: {contract.title}")
        else:
            ocr_title = extracted.get("title", "")
            if _is_valid_llm_value(ocr_title):
                contract.title = ocr_title
            else:
                fallback_title = _extract_title_from_text(raw_text)
                if fallback_title:
                    contract.title = fallback_title
            print(f"[异步重解析] 使用兜底合同名称: {contract.title}")
        
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


def _async_reparse_oa_contract(contract_id: int, attachment_file_path: str):
    """后台线程：异步解析OA导入合同的附件"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            print(f"[OA重解析] 合同 {contract_id} 不存在")
            return

        print(f"[OA重解析] 开始解析合同 {contract_id}，附件路径: {attachment_file_path}")

        # 1. 提取文本（OCR / docx解析）
        raw_text = contract.raw_text
        extracted = {}

        if not raw_text or len(raw_text) < 100:
            print(f"[OA重解析] 从附件提取文本...")
            try:
                parse_result = contract_parser.parse_contract(attachment_file_path, "")
                extracted = parse_result.get("data", {})
                raw_text = parse_result.get("raw_text", "")
                print(f"[OA重解析] 文本提取完成，长度: {len(raw_text)}")
            except Exception as e:
                print(f"[OA重解析] 文本提取失败: {e}")
                import traceback
                traceback.print_exc()
                # 即使提取失败也继续，不要return
        else:
            print(f"[OA重解析] 使用已有文本，长度: {len(raw_text)}")
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

        if not raw_text or len(raw_text) < 50:
            print(f"[OA重解析] 文本太短或为空，无法解析")
            # 不覆盖OA原始summary，将错误信息存到extracted_data
            err_data = {"llm_summary": "附件文本提取失败，无法进行AI解析"}
            if contract.summary and not contract.summary.startswith("正在解析"):
                err_data["oa_original_summary"] = contract.summary
            contract.extracted_data = json.dumps(err_data, ensure_ascii=False)
            # 如果summary被临时状态覆盖，尝试恢复
            if contract.summary and contract.summary.startswith("正在解析"):
                contract.summary = ""  # 清空临时状态
            contract.updated_at = datetime.now()
            db.commit()
            return

        # 保存raw_text
        contract.raw_text = raw_text

        # 2. LLM增强解析（提取结构化字段）
        llm_result = {}
        try:
            llm_result = llm_service.llm_service.parse_contract_with_llm(raw_text)
            print(f"[OA重解析] LLM字段解析结果: {llm_result}")
        except Exception as e:
            print(f"[OA重解析] LLM字段解析失败: {e}")
            import traceback
            traceback.print_exc()

        if llm_result:
            extracted = _merge_llm_result(extracted, llm_result)

        # 3. LLM生成摘要
        summary = ""
        try:
            llm_summary = llm_service.llm_service.extract_full_summary(raw_text)
            if llm_summary:
                summary = llm_summary
                print(f"[OA重解析] LLM摘要生成成功，长度: {len(summary)}")
        except Exception as e:
            print(f"[OA重解析] LLM摘要生成失败: {e}")
            import traceback
            traceback.print_exc()

        if not summary:
            summary = _generate_contract_summary(extracted, raw_text)
            print(f"[OA重解析] 使用基础摘要，长度: {len(summary)}")

        # 4. 更新合同字段
        # 更新签约方（过滤无效值）
        if llm_result.get("甲方") or llm_result.get("乙方"):
            parties_list = []
            for key in ["甲方", "乙方"]:
                v = llm_result.get(key)
                if _is_valid_llm_value(v):
                    parties_list.append(v)
            if llm_result.get("丙方") and _is_valid_llm_value(llm_result["丙方"]):
                parties_list.append(llm_result["丙方"])
            contract.parties = json.dumps(parties_list, ensure_ascii=False)
        elif extracted.get("parties"):
            contract.parties = json.dumps(extracted.get("parties", []), ensure_ascii=False)

        # OA合同：LLM摘要存到extracted_data.llm_summary，不覆盖原始summary（OA申请摘要）
        # 保存原始OA摘要（如果当前summary是"正在解析..."的临时状态，恢复原始值）
        original_summary = None
        if contract.extracted_data:
            try:
                ed = json.loads(contract.extracted_data)
                original_summary = ed.get("oa_original_summary")
            except:
                pass
        
        # 第一次解析时，备份OA原始摘要
        if not original_summary and contract.summary and not contract.summary.startswith("正在解析"):
            original_summary = contract.summary
        
        # 将LLM摘要存入extracted_data
        extracted["llm_summary"] = summary
        if original_summary:
            extracted["oa_original_summary"] = original_summary
            contract.summary = original_summary  # 恢复OA原始摘要
        elif contract.summary and contract.summary.startswith("正在解析"):
            # 如果没有原始摘要且当前是临时状态，用LLM摘要作为summary（触发前端轮询完成判定）
            contract.summary = summary

        # 合同名称（过滤无效值）
        llm_title = llm_result.get("合同名称", "")
        if _is_valid_llm_value(llm_title):
            contract.title = llm_title
        elif contract.title in _INVALID_LLM_VALUES or not contract.title:
            fallback_title = _extract_title_from_text(raw_text)
            if fallback_title:
                contract.title = fallback_title

        # 合同类型
        if extracted.get("contract_type") and extracted["contract_type"] != "其他":
            contract.contract_type = extracted["contract_type"]

        # 金额
        if llm_result.get("服务费用总额"):
            amount_str = llm_result["服务费用总额"]
            # 先尝试阿拉伯数字
            numbers = re.findall(r'\d+\.?\d*', amount_str.replace(',', '').replace('，', ''))
            if numbers:
                try:
                    contract.amount = float(numbers[0])
                except:
                    pass
            else:
                # 尝试中文大写金额
                from app.routers.import_contracts import _cn_amount_to_float
                cn_amount = _cn_amount_to_float(amount_str)
                if cn_amount:
                    contract.amount = cn_amount
        elif extracted.get("amount"):
            contract.amount = extracted.get("amount")

        # 日期（支持从非标准LLM返回文本中提取日期）
        from app.routers.import_contracts import _extract_date_from_text
        for field_name, db_field in [
            ("签订日期", "signed_date"),
            ("服务期限开始日期", "start_date"),
            ("服务期限结束日期", "end_date"),
        ]:
            val = llm_result.get(field_name)
            if val and str(val) != "null":
                date_str = _extract_date_from_text(str(val))
                if date_str:
                    try:
                        setattr(contract, db_field, datetime.strptime(date_str, "%Y-%m-%d"))
                    except:
                        pass

        # 更新状态
        if contract.end_date:
            contract.status = _calculate_contract_status(contract.end_date)

        contract.extracted_data = json.dumps(extracted, ensure_ascii=False)
        contract.updated_at = datetime.now()
        db.commit()
        print(f"[OA重解析] 合同 {contract_id} 解析完成")
    except Exception as e:
        print(f"[OA重解析] 合同 {contract_id} 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@router.post("/{contract_id}/reparse")
def reparse_contract(
    contract_id: int,
    attachment_id: Optional[int] = Query(None, description="指定要解析的附件ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """重新解析合同，后台异步执行。支持普通合同和OA导入的合同。"""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    import threading

    if contract.source == 'oa_import' and not contract.file_path:
        # OA导入的合同：从附件中提取文本进行解析
        target_att = None
        
        # 如果指定了附件ID，直接使用
        if attachment_id:
            target_att = db.query(ContractAttachment).filter(
                ContractAttachment.id == attachment_id,
                ContractAttachment.contract_id == contract_id,
                ContractAttachment.is_deleted == False
            ).first()
            if not target_att:
                raise HTTPException(status_code=404, detail="指定的附件不存在")
        else:
            # 自动查找可解析的附件（优先Word/PDF）
            attachments = db.query(ContractAttachment).filter(
                ContractAttachment.contract_id == contract_id,
                ContractAttachment.is_deleted == False
            ).all()
            
            if not attachments:
                raise HTTPException(status_code=400, detail="OA合同没有附件，无法解析")
            
            for att in attachments:
                ext = (att.file_name or "").rsplit('.', 1)[-1].lower()
                if ext in ('docx', 'doc', 'pdf'):
                    target_att = att
                    break
            if not target_att:
                target_att = attachments[0]
        
        if not target_att.file_path:
            raise HTTPException(status_code=400, detail="附件文件路径不存在")
        
        att_path = file_storage.get_file_path(target_att.file_path)
        if not att_path.exists():
            raise HTTPException(status_code=404, detail=f"附件文件不存在: {target_att.file_name}")
        
        # 备份OA原始summary到extracted_data，再设置临时解析状态
        oa_original_summary = contract.summary or ""
        backup_data = {}
        if contract.extracted_data:
            try:
                backup_data = json.loads(contract.extracted_data)
            except:
                pass
        if oa_original_summary and not oa_original_summary.startswith("正在解析"):
            backup_data["oa_original_summary"] = oa_original_summary
        contract.extracted_data = json.dumps(backup_data, ensure_ascii=False)
        contract.summary = f"正在解析附件: {target_att.file_name}..."
        contract.updated_at = datetime.now()
        db.commit()
        
        t = threading.Thread(target=_async_reparse_oa_contract, args=(contract_id, str(att_path)))
        t.daemon = False
        t.start()
    else:
        # 普通上传的合同
        if not contract.file_path:
            raise HTTPException(status_code=400, detail="合同没有关联文件，无法解析")
        
        full_path = file_storage.get_file_path(contract.file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")

        # 先将摘要标记为基础版，触发前端轮询
        contract.summary = _generate_contract_summary({}, contract.raw_text or "")
        contract.updated_at = datetime.now()
        db.commit()

        t = threading.Thread(target=_async_reparse_process, args=(contract_id, str(full_path)))
        t.daemon = False
        t.start()

    return {
        "contract_id": contract_id,
        "message": "正在后台重新解析，请稍候刷新查看"
    }


@router.get("/{contract_id}/parse-stream")
async def parse_stream(
    contract_id: int,
    token: str = Query(..., description="认证token"),
    db: Session = Depends(get_db)
):
    """SSE流式输出合同解析进度和结果"""
    from fastapi.responses import StreamingResponse
    from app.auth import verify_token
    import asyncio

    # 验证token（SSE不能用Authorization header，改用query param）
    user = verify_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="未授权")

    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    raw_text = contract.raw_text or ""

    async def event_generator():
        import json as _json

        def send(event: str, data: dict):
            return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        if not raw_text or len(raw_text) < 100:
            yield send("error", {"message": "合同文本为空，无法解析"})
            return

        yield send("progress", {"step": "fields", "message": "正在提取合同基本信息..."})

        # Step 1: 结构化字段（在线程池中运行同步LLM调用）
        loop = asyncio.get_event_loop()
        try:
            llm_result = await loop.run_in_executor(
                None, llm_service.llm_service.parse_contract_with_llm, raw_text
            )
        except Exception as e:
            llm_result = {}
            yield send("progress", {"step": "fields", "message": f"字段提取失败: {e}"})

        if llm_result:
            # 更新数据库
            from app.database import SessionLocal
            _db = SessionLocal()
            try:
                c = _db.query(Contract).filter(Contract.id == contract_id).first()
                if c:
                    llm_title = llm_result.get("合同名称", "")
                    if _is_valid_llm_value(llm_title):
                        c.title = llm_title
                    elif c.title in _INVALID_LLM_VALUES or not c.title:
                        fallback_title = _extract_title_from_text(raw_text)
                        if fallback_title:
                            c.title = fallback_title
                    parties_list = []
                    for k in ["甲方", "乙方", "丙方"]:
                        v = llm_result.get(k)
                        if _is_valid_llm_value(v):
                            parties_list.append(v)
                    if parties_list:
                        c.parties = _json.dumps(parties_list, ensure_ascii=False)
                    if llm_result.get("服务费用总额"):
                        nums = re.findall(r'[\d]+\.?\d*', str(llm_result["服务费用总额"]).replace(',', ''))
                        if nums:
                            try:
                                c.amount = float(nums[0])
                            except Exception:
                                pass
                    def _pd(s):
                        if not s or str(s) in ("null", ""):
                            return None
                        for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d"]:
                            try:
                                return datetime.strptime(str(s), fmt)
                            except Exception:
                                continue
                        return None
                    if llm_result.get("签订日期"):
                        d = _pd(llm_result["签订日期"])
                        if d:
                            c.signed_date = d
                    if llm_result.get("服务期限开始日期"):
                        d = _pd(llm_result["服务期限开始日期"])
                        if d:
                            c.start_date = d
                    if llm_result.get("服务期限结束日期"):
                        d = _pd(llm_result["服务期限结束日期"])
                        if d:
                            c.end_date = d
                    c.updated_at = datetime.now()
                    _db.commit()
            finally:
                _db.close()

            yield send("fields", {
                "title": llm_result.get("合同名称", ""),
                "parties": [llm_result.get("甲方", ""), llm_result.get("乙方", ""), llm_result.get("丙方", "")],
                "signed_date": llm_result.get("签订日期", ""),
                "start_date": llm_result.get("服务期限开始日期", ""),
                "end_date": llm_result.get("服务期限结束日期", ""),
                "amount": llm_result.get("服务费用总额", ""),
            })

        yield send("progress", {"step": "summary", "message": "正在生成合同摘要..."})

        # Step 2: 流式摘要（逐块输出）
        import requests as _requests
        from app.config import config as _config

        ak = _config.BAIDUQIANFAN_API_KEY
        sk = _config.BAIDUQIANFAN_SECRET_KEY
        if ak and sk and ak.startswith("bce-v3/ALTAK-") and "/" not in ak.split("ALTAK-", 1)[-1]:
            api_key = f"{ak}/{sk}"
        else:
            api_key = ak

        # 构建摘要prompt（复用llm_service的逻辑，但用流式接口）
        text_sample = raw_text if len(raw_text) <= 8000 else raw_text[:3000] + "\n\n...[中间省略]...\n\n" + raw_text[-1500:]

        summary_prompt = f"""你是一个专业的合同分析助手。请仔细阅读以下合同全文，提取以下内容并用Markdown格式输出。

## 重要规则
只提取文本中实际存在的信息，不要添加任何虚构内容。如果某部分不存在，请说明"未找到相关内容"。

## 输出结构

### 主要合作内容
提取服务范围、合作内容、双方权利义务等。

### 产品/服务明细表
如有明细表，用标准Markdown表格格式完整输出。

### 付款方式
提取付款条件、付款比例、时间节点等。

合同文本：
{text_sample}

请直接输出Markdown格式内容。"""

        full_summary = ""
        try:
            url = "https://qianfan.baidubce.com/v2/chat/completions"
            payload = {
                "model": "ernie-3.5-8k",
                "messages": [{"role": "user", "content": summary_prompt}],
                "stream": True
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            def _stream_request():
                return _requests.post(url, json=payload, headers=headers, stream=True, timeout=180)

            response = await loop.run_in_executor(None, _stream_request)

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = _json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    full_summary += delta
                                    yield send("chunk", {"text": delta})
                            except Exception:
                                pass
            else:
                # 流式失败，回退到非流式
                fallback = await loop.run_in_executor(
                    None, llm_service.llm_service.extract_full_summary, raw_text
                )
                if fallback:
                    full_summary = fallback
                    yield send("chunk", {"text": fallback})
        except Exception as e:
            yield send("progress", {"step": "summary", "message": f"摘要生成失败: {e}"})

        # 保存摘要到数据库
        if full_summary:
            from app.database import SessionLocal
            _db = SessionLocal()
            try:
                c = _db.query(Contract).filter(Contract.id == contract_id).first()
                if c:
                    c.summary = full_summary
                    c.updated_at = datetime.now()
                    _db.commit()
            finally:
                _db.close()

        yield send("done", {"message": "解析完成"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


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



@router.post("/{contract_id}/import-oa-flow-pdf")
async def import_oa_flow_pdf(
    contract_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传OA流程表单PDF，解析后更新合同的OA流程信息字段"""
    import tempfile
    from app.services.payment_parser import PaymentParser

    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="请上传PDF文件")

    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted == False).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    content = await file.read()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp_path = tmp.name
            tmp.write(content)

        # 用OCR提取PDF文本
        from app.services.contract_parser import ContractParser
        parser = ContractParser()
        raw_text = parser.ocr.extract_text_from_file(tmp_path)

        if not raw_text or len(raw_text.strip()) < 10:
            raise HTTPException(status_code=422, detail="无法从PDF中提取文字，请确认PDF非扫描件或图片格式")

        # 用正则从OA流程表单文本中提取关键字段
        # OA表单格式：字段名单独一行，值在下一行（换行格式）
        oa_fields = {}
        import re as _re
        import json as _json

        def extract_field(text, *labels):
            """从换行格式或冒号格式提取字段值"""
            for label in labels:
                # 换行格式：字段名\n值
                m = _re.search('(?:^|\n)' + _re.escape(label) + r'\s*\n\s*([^\n\r]{1,100})', text)
                if m:
                    val = m.group(1).strip()
                    if val and val.lower() not in ('null', 'none', ''):
                        return val
                # 冒号格式：字段名：值
                m = _re.search(_re.escape(label) + r'[：:]\s*([^\n\r]{1,100})', text)
                if m:
                    val = m.group(1).strip()
                    if val and val.lower() not in ('null', 'none', ''):
                        return val
            return None

        # 提取7个核心字段 + 其他字段
        oa_fields['applicant']    = extract_field(raw_text, '申请人', '申请人姓名', '发起人', '经办人')
        oa_fields['doc_number']   = extract_field(raw_text, '申请单编号', '申请单号', '流程编号', '单据编号', '申请编号')
        oa_fields['cost_center']  = extract_field(raw_text, '归属成本中心', '成本中心', '费用归属')
        oa_fields['doc_subject']  = extract_field(raw_text, '主题', '合同名称', '流程主题', '事由', '合同主题')
        oa_fields['handler']      = extract_field(raw_text, '合同执行申请部门经办人', '部门经办人', '经办人', '联系人')
        oa_fields['contract_nature'] = extract_field(raw_text, '合同性质', '合同类型', '合同类别')
        oa_fields['department']   = extract_field(raw_text, '申请部门', '部门', '发起部门', '所属部门', '申请人部门')
        oa_fields['company']      = extract_field(raw_text, '我方公司', '甲方单位', '甲方公司', '甲方')
        oa_fields['counterparty'] = extract_field(raw_text, '对方单位', '乙方单位', '乙方公司', '乙方', '供应商', '服务商')
        oa_fields['counterparty_contact'] = extract_field(raw_text, '对方联系人', '乙方联系人', '联系方式')
        oa_fields['payment_type'] = extract_field(raw_text, '付款方式', '支付方式', '结算方式')
        oa_fields['copies']       = extract_field(raw_text, '合同份数', '份数', '合同正本份数')
        oa_fields['doc_status']   = extract_field(raw_text, '流程状态', '审批状态', '状态')
        # 去掉空值
        oa_fields = {k: v for k, v in oa_fields.items() if v}

        # 金额提取（支持多种格式）
        amount_match = _re.search(r'(?:合同金额|总金额|金额)[：:]\s*[¥￥]?\s*([\d,，.]+)', raw_text)
        if not amount_match:
            amount_match = _re.search(r'(?:合同金额|总金额|金额)\s*\n\s*[¥￥]?\s*([\d,，.]+)', raw_text)
        if amount_match:
            oa_fields['amount'] = amount_match.group(1).replace(',', '').replace('，', '')

        # 尝试用LLM补充解析（可选，失败不影响）
        llm_result_str = ''
        try:
            prompt_text = f"""从以下OA流程表单文本提取信息，JSON格式返回，字段：
- doc_subject: 合同主题/流程主题/主题
- applicant: 申请人姓名
- doc_number: 申请单编号/申请单号
- cost_center: 归属成本中心
- handler: 合同执行申请部门经办人
- contract_nature: 合同性质
- department: 申请部门
- company: 我方公司（甲方）
- counterparty: 对方单位（乙方）
- counterparty_contact: 对方联系人
- payment_type: 付款方式
- copies: 合同份数
- amount: 合同金额（纯数字）
- summary: 合同事由摘要（不超过150字，用自然语言描述合同目的）
只返回JSON，不要其他内容。\n\n{raw_text[:3000]}"""
            llm_result_str = llm_service.llm_service.call_llm(prompt_text, raw_text[:3000])
            if llm_result_str:
                json_match = _re.search(r'\{.*\}', llm_result_str, _re.DOTALL)
                if json_match:
                    llm_fields = _json.loads(json_match.group())
                    # LLM结果覆盖/补充字段（LLM优先级更高）
                    for k, v in llm_fields.items():
                        if v and str(v).lower() not in ('null', 'none', ''):
                            oa_fields[k] = str(v)
        except Exception as e:
            print(f"LLM辅助解析失败（已用正则兜底）: {e}")

        # 同时从 raw_data 已有的中文字段中补充（兼容旧数据）
        existing_raw_check = {}
        if contract.raw_data:
            try:
                existing_raw_check = json.loads(contract.raw_data)
            except Exception:
                pass
        cn_field_map = {
            '甲方': 'company', '乙方': 'counterparty',
            '申请人': 'applicant', '申请人姓名': 'applicant',
            '申请部门': 'department', '发起部门': 'department',
        }
        for cn_key, oa_key in cn_field_map.items():
            if cn_key in existing_raw_check and oa_key not in oa_fields:
                oa_fields[oa_key] = existing_raw_check[cn_key]

        # 更新合同字段（强制覆盖，以导入的PDF为准）
        updated_fields = []
        field_map = {
            'applicant': 'applicant',
            'department': 'department',
            'company': 'company',
            'counterparty': 'counterparty',
            'counterparty_contact': 'counterparty_contact',
            'payment_type': 'payment_type',
            'copies': 'copies',
        }
        for oa_key, db_field in field_map.items():
            val = oa_fields.get(oa_key)
            if val and str(val).lower() not in ('null', 'none', ''):
                setattr(contract, db_field, str(val))
                updated_fields.append(db_field)

        # amount 单独处理
        if oa_fields.get('amount'):
            try:
                amt_str = str(oa_fields['amount']).replace(',', '').replace('，', '')
                nums = _re.findall(r'\d+\.?\d*', amt_str)
                if nums:
                    contract.amount = float(nums[0])
                    updated_fields.append('amount')
            except Exception:
                pass

        # 将解析结果存入 raw_data（合并已有数据）
        existing_raw = {}
        if contract.raw_data:
            try:
                existing_raw = json.loads(contract.raw_data)
            except Exception:
                pass
        # 清除旧的 summary 原文垃圾数据
        existing_raw.pop('summary', None)
        existing_raw.update({k: v for k, v in oa_fields.items() if v and k != 'summary' and str(v).lower() not in ('null', 'none')})
        existing_raw['doc_subject'] = oa_fields.get('doc_subject') or existing_raw.get('doc_subject', '')
        # 只在LLM成功提取了有意义的摘要时才写入（避免把PDF原文存进去）
        llm_summary = oa_fields.get('summary', '')
        if llm_summary and len(llm_summary) < 300 and not llm_summary.startswith('合同编号') and not llm_summary.startswith('流程'):
            existing_raw['合同摘要'] = llm_summary
        contract.raw_data = json.dumps(existing_raw, ensure_ascii=False)

        # 标记为OA导入来源（仅当合同没有自己的文件时才改source，避免覆盖手动上传合同的source）
        if not contract.file_path and contract.source != 'oa_import':
            contract.source = 'oa_import'

        contract.updated_at = datetime.now()
        db.commit()

        return {
            "message": "OA流程信息导入成功",
            "updated_fields": updated_fields,
            "oa_fields": oa_fields,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if tmp_path:
            import os
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
