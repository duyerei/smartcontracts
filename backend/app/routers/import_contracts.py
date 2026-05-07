"""
OA合同导入路由
"""
from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import json
import codecs
import re

from app.database import get_db, Contract, ContractAttachment, User, SessionLocal
from app.auth import verify_token
from app.security.bootstrap import find_org_by_name, sync_contract_department_with_org
from app.security.permissions import ensure_entity_access, populate_ownership_fields, require_permission
from app.security.principal import Principal, build_principal

router = APIRouter(prefix="/contracts", tags=["合同导入"])


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return verify_token(token, db)
    return None


class AttachmentData(BaseModel):
    name: str
    path: str
    size: int
    url: Optional[str] = None


class ContractImportData(BaseModel):
    oa_id: str
    contract_number: str
    contract_name: str
    contract_type: Optional[str] = None
    create_date: str
    status: Optional[str] = None
    applicant: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None
    counterparty: Optional[str] = None
    counterparty_contact: Optional[str] = None
    counterparty_address: Optional[str] = None
    amount: Optional[str] = None
    payment_type: Optional[str] = None
    summary: Optional[str] = None
    copies: Optional[str] = None
    attachments_count: Optional[int] = 0
    attachments: List[AttachmentData] = []
    raw_data: Optional[Dict[str, Any]] = None


class ImportRequest(BaseModel):
    contracts: List[ContractImportData]
    skip_duplicates: bool = True
    update_existing: bool = False


class ImportResponse(BaseModel):
    success: bool
    imported: int
    skipped: int
    failed: int
    errors: List[Dict[str, Any]]
    details: Dict[str, Any]


def decode_unicode_filename(filename: str) -> str:
    """解码Unicode转义序列的文件名"""
    try:
        # 处理 \uXXXX 格式的Unicode转义
        decoded = codecs.decode(filename, 'unicode_escape')
        return decoded
    except Exception as e:
        print(f"文件名解码失败: {filename}, 错误: {e}")
        return filename


def parse_amount(amount_str: str) -> Optional[float]:
    """解析金额字符串（支持阿拉伯数字和中文大写）"""
    if not amount_str or amount_str.strip() == "":
        return None
    
    try:
        # 先尝试直接提取阿拉伯数字（如 ￥65000.00、130,000元）
        clean = amount_str.replace("元", "").replace(",", "").replace("¥", "").replace("人民币", "").strip()
        numbers = re.findall(r'[\d]+\.?\d*', clean)
        if numbers:
            return float(numbers[0].replace(",", ""))
        
        # 尝试中文大写数字转换
        return _cn_amount_to_float(amount_str)
    except Exception as e:
        print(f"金额解析失败: {amount_str}, 错误: {e}")
        return None


def _cn_amount_to_float(cn_str: str) -> Optional[float]:
    """中文大写金额转浮点数（如 壹拾叁万元整 -> 130000.0）"""
    cn_str = cn_str.replace("整", "").replace("元", "").replace("人民币", "").replace("（", "").replace("）", "").strip()
    
    cn_num = {
        '零': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4,
        '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9,
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9,
    }
    cn_unit = {
        '拾': 10, '佰': 100, '仟': 1000, '千': 1000,
        '万': 10000, '亿': 100000000,
        '十': 10, '百': 100,
    }
    
    # 检查是否包含中文数字字符
    if not any(c in cn_num or c in cn_unit for c in cn_str):
        return None
    
    total = 0
    current = 0
    wan_part = 0
    
    for char in cn_str:
        if char in cn_num:
            current = cn_num[char]
        elif char in cn_unit:
            unit = cn_unit[char]
            if unit == 10000:
                wan_part = (wan_part + total + (current if current else 0)) * unit
                total = 0
                current = 0
            elif unit == 100000000:
                wan_part = (wan_part + total + current) * unit
                total = 0
                current = 0
            else:
                if current == 0 and unit == 10:
                    current = 1
                total += current * unit
                current = 0
    
    total += current
    result = wan_part + total
    return float(result) if result > 0 else None


def _extract_date_from_text(text: str) -> Optional[str]:
    """从LLM返回的非标准日期文本中提取第一个有效日期（YYYY-MM-DD格式）"""
    if not text or text.strip() == "" or text == "null":
        return None
    
    # 跳过明显无效的值
    skip_keywords = ["未知", "未提供", "未找到", "不明", "无法", "null"]
    if any(kw in text for kw in skip_keywords):
        # 但仍然尝试从中提取日期
        pass
    
    # 尝试提取 YYYY-MM-DD 格式
    match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
    if match:
        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
    
    # 尝试提取 YYYY年MM月DD日 格式
    match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    if match:
        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
    
    # 尝试提取 YYYY/MM/DD 格式
    match = re.search(r'(\d{4})/(\d{1,2})/(\d{1,2})', text)
    if match:
        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
    
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    """解析日期字符串"""
    if not date_str or date_str.strip() == "":
        return None
    
    try:
        # 支持多种日期格式
        formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    except Exception as e:
        print(f"日期解析失败: {date_str}, 错误: {e}")
        return None


def validate_contract_data(contract_data: ContractImportData) -> tuple[bool, Optional[str]]:
    """验证合同数据"""
    # 必填字段检查
    required_fields = {
        'oa_id': 'OA系统ID',
        'contract_number': '合同编号',
        'contract_name': '合同名称',
        'create_date': '创建日期'
    }
    
    for field, field_name in required_fields.items():
        value = getattr(contract_data, field, None)
        if not value or (isinstance(value, str) and value.strip() == ""):
            return False, f"缺少必填字段: {field_name}"
    
    # 日期格式验证
    if not parse_date(contract_data.create_date):
        return False, f"日期格式错误: {contract_data.create_date}"
    
    return True, None


def _detect_primary_attachment(attachments: List[AttachmentData]) -> int:
    """智能识别主附件（合同正文），返回索引。
    规则：
    1. 文件名含"合同"/"协议"且为docx/pdf的优先级最高
    2. 排除"请示"/"审批"/"保密"/"NDA"等非正文文件
    3. 同等条件下选文件最大的（合同正文通常比请示大）
    4. 都不匹配则选第一个
    """
    if not attachments:
        return 0
    
    contract_keywords = ["合同", "协议", "contract", "agreement"]
    exclude_keywords = ["请示", "审批", "保密", "NDA", "nda", "签报", "申请", "审签", "批复"]
    valid_exts = ["docx", "doc", "pdf"]
    
    best_idx = 0
    best_score = -1
    
    for idx, att in enumerate(attachments):
        name = decode_unicode_filename(att.name).lower()
        ext = name.rsplit('.', 1)[-1] if '.' in name else ''
        
        if ext not in valid_exts:
            continue
        
        score = 0
        
        # 排除非正文文件
        if any(kw in name for kw in exclude_keywords):
            score -= 10
        
        # 文件名含合同/协议关键词加分
        if any(kw in name for kw in contract_keywords):
            score += 20
        
        # 文件大小加分（越大越可能是正文）
        score += min(att.size / 100000, 10)  # 最多加10分
        
        # docx/pdf优先
        if ext in ["docx", "pdf"]:
            score += 5
        
        if score > best_score:
            best_score = score
            best_idx = idx
    
    return best_idx


def _parse_counterparty_from_raw(raw_data: dict, counterparty_name: str = '') -> dict:
    """从OA原始数据的复合key中解析对方经办人、地址、电话"""
    result = {'contact': '', 'address': '', 'phone': ''}
    if not raw_data:
        return result
    for key in raw_data.keys():
        if key.endswith('_2'):
            continue
        if '对方名称' in key and '对方经办人' in key and '地址' in key and '电话' in key:
            brace_idx = key.find('{1}')
            data_str = key[brace_idx + 3:].strip() if brace_idx >= 0 else key
            stripped = re.sub(r'^\d+\s*', '', data_str).strip()
            # 1. 电话在末尾
            phone_match = re.search(r'(\d{7,13})\s*$', stripped)
            phone = phone_match.group(1) if phone_match else ''
            without_phone = stripped[:stripped.rfind(phone)].strip() if phone else stripped
            # 2. 切掉公司名，剩余是"经办人+地址"
            after_company = ''
            if counterparty_name and counterparty_name in without_phone:
                after_company = without_phone[without_phone.index(counterparty_name) + len(counterparty_name):].strip()
            else:
                co_match = re.match(r'^(.+(?:公司|集团|有限|股份|机构|中心|部门|局|院|所))\s*(.*)', without_phone)
                if co_match:
                    after_company = co_match.group(2).strip()
            if not after_company:
                result = {'contact': '', 'address': '', 'phone': phone}
                break
            # 3. 用已知省市名列表定位地址起点，避免误匹配姓名中的字
            known_regions = [
                '北京市', '上海市', '天津市', '重庆市',
                '广东省', '广州市', '深圳市', '佛山市', '珠海市', '东莞市', '惠州市', '中山市',
                '浙江省', '杭州市', '宁波市', '温州市',
                '江苏省', '南京市', '苏州市', '无锡市',
                '山东省', '济南市', '青岛市',
                '四川省', '成都市',
                '湖北省', '武汉市',
                '湖南省', '长沙市',
                '河南省', '郑州市',
                '河北省', '石家庄市',
                '陕西省', '西安市',
                '甘肃省', '兰州市',
                '云南省', '昆明市',
                '贵州省', '贵阳市',
                '福建省', '福州市', '厦门市',
                '安徽省', '合肥市',
                '江西省', '南昌市',
                '辽宁省', '沈阳市', '大连市',
                '吉林省', '长春市',
                '黑龙江省', '哈尔滨市',
                '内蒙古', '新疆', '西藏', '宁夏', '广西', '海南省',
            ]
            addr_idx = -1
            for region in known_regions:
                idx = after_company.find(region)
                if idx >= 0 and (addr_idx < 0 or idx < addr_idx):
                    addr_idx = idx
            if addr_idx > 0:
                contact = after_company[:addr_idx].strip()
                address = after_company[addr_idx:].strip()
            elif addr_idx == 0:
                contact = ''
                address = after_company.strip()
            else:
                # 没找到省市名，尝试路/街/道
                addr_start2 = re.search(r'[\u4e00-\u9fa5]{1,10}(?:路|街|道|大道)', after_company)
                if addr_start2:
                    contact = after_company[:addr_start2.start()].strip()
                    address = after_company[addr_start2.start():].strip()
                else:
                    contact = after_company
                    address = ''
            result = {'contact': contact, 'address': address, 'phone': phone}
            break
    return result


def import_single_contract(
    contract_data: ContractImportData,
    principal: Principal,
    db: Session,
    skip_duplicates: bool = True,
    update_existing: bool = False
) -> tuple[bool, Optional[str], Optional[Contract]]:
    """导入单个合同"""
    
    # 1. 验证数据
    is_valid, error_msg = validate_contract_data(contract_data)
    if not is_valid:
        return False, error_msg, None
    
    # 2. 检查是否已存在
    existing = db.query(Contract).filter(
        Contract.oa_id == contract_data.oa_id
    ).first()
    
    if existing:
        if skip_duplicates and not update_existing:
            return False, f"合同已存在（跳过）: {contract_data.contract_number}", None
        elif update_existing:
            # 更新现有合同
            contract = existing
            ensure_entity_access(contract, principal, "contract", db)
        else:
            return False, f"合同已存在: {contract_data.contract_number}", None
    else:
        # 创建新合同
        contract = Contract()
    
    # 3. 填充合同数据
    try:
        contract.oa_id = contract_data.oa_id
        contract.contract_number = contract_data.contract_number
        contract.title = contract_data.contract_name
        contract.contract_type = contract_data.contract_type
        contract.status = contract_data.status or "待审核"
        contract.department = contract_data.department
        contract.applicant = contract_data.applicant
        contract.position = contract_data.position
        contract.company = contract_data.company
        contract.counterparty = contract_data.counterparty
        # counterparty_contact: OA插件有时把我方申请人电话存在这个字段里
        # 如果是纯数字，不要存为对方联系人（后面会从复合key或已有数据处理）
        incoming_cc = contract_data.counterparty_contact or ''
        if incoming_cc and not re.match(r'^\d{7,13}$', incoming_cc.strip()):
            contract.counterparty_contact = incoming_cc
        elif not existing:
            # 新合同且 counterparty_contact 是纯数字，留空
            contract.counterparty_contact = ''
        # 如果是更新已有合同，保留已有的 counterparty_contact（可能已被修复过）
        
        contract.counterparty_address = contract_data.counterparty_address or (existing.counterparty_address if existing else None)
        contract.payment_type = contract_data.payment_type
        contract.copies = contract_data.copies
        contract.summary = contract_data.summary
        contract.source = "oa_import"
        contract.updated_at = datetime.now()

        # 解析金额
        contract.amount = parse_amount(contract_data.amount) if contract_data.amount else None
        
        # 解析日期
        create_date = parse_date(contract_data.create_date)
        if create_date:
            contract.signed_date = create_date
            contract.created_at = create_date
        
        # 保存原始数据，并从复合key中解析对方联系人/地址/电话
        if contract_data.raw_data:
            raw = contract_data.raw_data
            # 把申请时间存入raw_data，前端用 doc_create_time 字段显示
            if contract_data.create_date and not raw.get('doc_create_time'):
                raw['doc_create_time'] = contract_data.create_date
            # 从复合key解析对方信息（覆盖导入JSON里可能不准确的字段）
            cp_info = _parse_counterparty_from_raw(raw, contract_data.counterparty or '')
            if cp_info['contact']:
                contract.counterparty_contact = cp_info['contact']
            if cp_info['address']:
                contract.counterparty_address = cp_info['address']
            # 如果还没有地址，尝试从 raw_data 的 服务地点 字段获取
            if not contract.counterparty_address:
                service_loc = raw.get('服务地点', '')
                if service_loc and str(service_loc) not in ['null', 'None', '', 'null（合同文本中未明确提及服务地点）', 'null（合同文本中未提及）']:
                    contract.counterparty_address = str(service_loc)
            # 电话单独存入raw_data，前端可以读取
            phone = cp_info['phone']
            # 同时清理 raw_data 里的 counterparty_contact（如果是纯数字电话号码）
            # 注意：这个字段可能是我方申请人的电话，不是对方的，所以不要存为对方电话
            raw_cc = raw.get('counterparty_contact', '')
            if raw_cc and re.match(r'^\d{7,13}$', str(raw_cc).strip()):
                del raw['counterparty_contact']
            # 只在有新电话时更新，避免覆盖已有的正确电话
            if phone:
                raw['_counterparty_phone'] = phone
            elif '_counterparty_phone' not in raw:
                raw['_counterparty_phone'] = ''
            contract.raw_data = json.dumps(raw, ensure_ascii=False)

        fallback_department = contract.department or (principal.primary_org.name if principal.primary_org else "其他")
        populate_ownership_fields(contract, principal, fallback_department=fallback_department)
        sync_contract_department_with_org(
            db,
            contract,
            preferred_org_id=None if contract.department else (principal.primary_org.id if principal.primary_org else None),
            preferred_department=fallback_department,
            create_missing_org=False,
        )

        # 保存合同
        if not existing:
            db.add(contract)
        db.flush()  # 获取contract.id
        
        # 4. 导入附件
        if contract_data.attachments:
            # 智能识别主附件：优先选文件名含"合同"的docx/pdf，其次选最大的docx/pdf
            primary_idx = _detect_primary_attachment(contract_data.attachments)
            
            for idx, att_data in enumerate(contract_data.attachments):
                # 检查附件是否已存在
                existing_att = db.query(ContractAttachment).filter(
                    ContractAttachment.contract_id == contract.id,
                    ContractAttachment.file_name == decode_unicode_filename(att_data.name)
                ).first()
                
                if not existing_att:
                    attachment = ContractAttachment(
                        contract_id=contract.id,
                        file_name=decode_unicode_filename(att_data.name),
                        file_path=att_data.path,
                        file_size=att_data.size,
                        file_url=att_data.url,
                        attachment_type="contract",
                        is_primary=(idx == primary_idx)
                    )
                    db.add(attachment)
        
        db.commit()
        db.refresh(contract)
        
        return True, None, contract
        
    except Exception as e:
        db.rollback()
        return False, f"导入失败: {str(e)}", None


@router.post("/import", response_model=ImportResponse)
async def import_contracts(
    request: ImportRequest = Body(...),
    principal: Principal = Depends(require_permission("contract.import_oa")),
    db: Session = Depends(get_db)
):
    """
    批量导入OA合同
    
    - **contracts**: 合同数据列表
    - **skip_duplicates**: 跳过重复的合同（默认True）
    - **update_existing**: 更新已存在的合同（默认False）
    """
    
    imported = 0
    skipped = 0
    failed = 0
    errors = []
    imported_contracts = []
    total_attachments = 0
    
    for contract_data in request.contracts:
        success, error_msg, contract = import_single_contract(
            contract_data,
            principal,
            db,
            request.skip_duplicates,
            request.update_existing
        )
        
        if success:
            imported += 1
            imported_contracts.append({
                "id": contract.id,
                "contract_number": contract.contract_number,
                "title": contract.title
            })
            total_attachments += len(contract_data.attachments)
        elif "跳过" in (error_msg or ""):
            skipped += 1
        else:
            failed += 1
            errors.append({
                "contract_number": contract_data.contract_number,
                "contract_name": contract_data.contract_name,
                "error": error_msg
            })
    
    return ImportResponse(
        success=failed == 0,
        imported=imported,
        skipped=skipped,
        failed=failed,
        errors=errors,
        details={
            "contracts": imported_contracts,
            "attachments": total_attachments
        }
    )


@router.get("/{contract_id}/attachments")
async def get_contract_attachments(
    contract_id: int,
    principal: Principal = Depends(require_permission("contract.view")),
    db: Session = Depends(get_db)
):
    """获取合同的所有附件"""
    
    # 验证合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    ensure_entity_access(contract, principal, "contract", db)
    
    # 查询附件
    attachments = db.query(ContractAttachment).filter(
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).all()
    
    return {
        "contract_id": contract_id,
        "contract_number": contract.contract_number,
        "attachments": [
            {
                "id": att.id,
                "file_name": att.file_name,
                "file_path": att.file_path,
                "file_size": att.file_size,
                "file_url": att.file_url,
                "attachment_type": att.attachment_type,
                "is_primary": att.is_primary if hasattr(att, 'is_primary') else False,
                "created_at": att.created_at.isoformat()
            }
            for att in attachments
        ]
    }


@router.get("/{contract_id}/attachments/{attachment_id}/download")
async def download_attachment(
    contract_id: int,
    attachment_id: int,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """下载或预览合同附件。支持 token query 参数（用于 iframe 直接加载）"""
    from starlette.responses import Response, RedirectResponse
    from app.services import file_storage

    # 优先用 Authorization header，其次用 query token
    current_user = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        current_user = verify_token(auth[7:], db)
    if current_user is None and token:
        current_user = verify_token(token, db)
    if current_user is None:
        raise HTTPException(status_code=401, detail="未授权")
    principal = build_principal(db, current_user)
    if not principal.has_permission("contract.download"):
        raise HTTPException(status_code=403, detail="缺少权限: contract.download")

    # 验证合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()

    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    ensure_entity_access(contract, principal, "contract", db)
    
    # 查询附件
    attachment = db.query(ContractAttachment).filter(
        ContractAttachment.id == attachment_id,
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    # 优先使用本地文件路径
    if attachment.file_path:
        try:
            # 获取文件路径（file_storage会处理OA附件的特殊路径）
            full_path = file_storage.get_file_path(attachment.file_path)
            
            if not full_path.exists():
                raise HTTPException(status_code=404, detail=f"附件文件不存在: {attachment.file_name}")
            
            # 根据文件扩展名设置media_type
            file_ext = attachment.file_name.lower().split('.')[-1]
            media_type_map = {
                'pdf': 'application/pdf',
                'doc': 'application/msword',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'bmp': 'image/bmp',
                'webp': 'image/webp',
            }
            media_type = media_type_map.get(file_ext, 'application/octet-stream')
            
            # 使用URL编码的文件名以支持中文
            from urllib.parse import quote
            encoded_filename = quote(attachment.file_name)
            import os
            
            from starlette.responses import FileResponse as StarletteFileResponse
            return StarletteFileResponse(
                path=str(full_path),
                media_type=media_type,
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
                    "Cache-Control": "private, max-age=3600",
                    "ETag": f'"{attachment_id}-{int(full_path.stat().st_mtime)}"',
                }
            )
        except Exception as e:
            print(f"附件下载失败: {e}")
            raise HTTPException(status_code=500, detail=f"附件下载失败: {str(e)}")
    
    # 如果没有本地文件，尝试使用OA系统的URL
    if attachment.file_url:
        # 检查是否为OA内部链接
        if attachment.file_url.startswith('/') or 'oa.bijiangtech.com' in attachment.file_url or 'localhost' in attachment.file_url:
            # OA内部链接，需要通过代理获取
            # 这里简化处理，实际应该通过OA API获取文件
            # 暂时返回错误，提示需要配置OA代理
            raise HTTPException(
                status_code=501, 
                detail="OA内部链接暂不支持直接下载，请联系管理员配置OA代理"
            )
        else:
            # 公网URL，重定向到原始URL
            return RedirectResponse(url=attachment.file_url)
    
    raise HTTPException(status_code=404, detail="附件文件不存在")


@router.get("/{contract_id}/attachments/{attachment_id}/preview-pdf")
async def preview_attachment_as_pdf(
    contract_id: int,
    attachment_id: int,
    principal: Principal = Depends(require_permission("contract.view")),
    db: Session = Depends(get_db)
):
    """将 .doc 附件转换为 PDF 后返回，用于浏览器内嵌预览"""
    from starlette.responses import Response
    from app.services import file_storage
    from app.services.baidu_ocr import baidu_ocr

    contract = db.query(Contract).filter(
        Contract.id == contract_id, Contract.is_deleted == False
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    ensure_entity_access(contract, principal, "contract", db)

    attachment = db.query(ContractAttachment).filter(
        ContractAttachment.id == attachment_id,
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")

    if not attachment.file_path:
        raise HTTPException(status_code=400, detail="附件无本地文件")

    full_path = file_storage.get_file_path(attachment.file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="附件文件不存在")

    import os
    abs_path = os.path.abspath(str(full_path))
    ext = (attachment.file_name or "").rsplit('.', 1)[-1].lower()

    if ext == 'pdf':
        # 已经是 PDF，直接返回
        with open(abs_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type="application/pdf")

    if ext not in ('doc', 'docx'):
        raise HTTPException(status_code=400, detail="仅支持 doc/docx 文件转 PDF 预览")

    # 调用 baidu_ocr 的转换方法
    pdf_path = baidu_ocr._convert_doc_to_pdf(abs_path)
    if not pdf_path:
        raise HTTPException(status_code=500, detail=".doc 转 PDF 失败，请下载后查看")

    try:
        with open(pdf_path, "rb") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"}
        )
    finally:
        # 清理临时文件
        try:
            os.remove(pdf_path)
            os.rmdir(os.path.dirname(pdf_path))
        except:
            pass


@router.post("/{contract_id}/attachments/{attachment_id}/analyze")
async def analyze_attachment(
    contract_id: int,
    attachment_id: int,
    principal: Principal = Depends(require_permission("contract.reparse")),
    db: Session = Depends(get_db)
):
    """分析OA导入合同的附件，提取合同信息并进行LLM解析"""
    from app.services import file_storage, contract_parser, llm_service
    from datetime import datetime
    import threading
    
    # 验证合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    ensure_entity_access(contract, principal, "contract", db)
    
    # 查询附件
    attachment = db.query(ContractAttachment).filter(
        ContractAttachment.id == attachment_id,
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    # 获取附件文件
    if not attachment.file_path:
        raise HTTPException(status_code=400, detail="附件文件路径不存在")
    
    try:
        full_path = file_storage.get_file_path(attachment.file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="附件文件不存在")
        
        # 提取文本
        raw_text = contract_parser.ocr.extract_text_from_file(str(full_path))
        if not raw_text:
            raise HTTPException(status_code=400, detail="无法从附件中提取文本")
        
        # 更新合同的raw_text
        contract.raw_text = raw_text
        contract.updated_at = datetime.now()
        db.commit()
        
        # 后台异步执行LLM解析
        def _async_analyze_attachment():
            try:
                print(f"[OA附件解析] 开始解析附件，文本长度: {len(raw_text)}")
                
                # LLM智能解析字段
                print("[OA附件解析] 调用LLM解析合同字段...")
                llm_result = llm_service.llm_service.parse_contract_with_llm(raw_text)
                print(f"[OA附件解析] LLM字段解析结果: {llm_result}")
                
                # 生成详细摘要
                print("[OA附件解析] 开始生成详细摘要...")
                parsed_summary = llm_service.llm_service.extract_full_summary(raw_text)
                
                if not parsed_summary:
                    print("[OA附件解析] LLM摘要生成失败，使用简单版本")
                    parsed_summary = "由AI自动解析提取"
                    if llm_result and llm_result.get("甲方"):
                        parsed_summary = f"甲方：{llm_result.get('甲方', '')}\n乙方：{llm_result.get('乙方', '')}"
                else:
                    print(f"[OA附件解析] LLM摘要生成成功，长度: {len(parsed_summary)}")
                
                # 更新合同 - 使用独立的数据库会话
                db_session = SessionLocal()
                try:
                    contract_to_update = db_session.query(Contract).filter(
                        Contract.id == contract_id
                    ).first()
                    
                    if contract_to_update:
                        # 从LLM结果更新字段
                        if llm_result:
                            if llm_result.get("甲方") and llm_result.get("乙方"):
                                parties = [llm_result["甲方"], llm_result["乙方"]]
                                if llm_result.get("丙方") and str(llm_result["丙方"]) not in ["null", "None", ""]:
                                    parties.append(llm_result["丙方"])
                                contract_to_update.parties = json.dumps(parties, ensure_ascii=False)
                            
                            # 解析签订日期（从非标准文本中提取）
                            date_str = _extract_date_from_text(str(llm_result.get("签订日期", "")))
                            if date_str:
                                try:
                                    from datetime import datetime as dt
                                    contract_to_update.signed_date = dt.strptime(date_str, "%Y-%m-%d")
                                    print(f"[OA附件解析] 签订日期: {date_str}")
                                except:
                                    pass
                            
                            # 解析服务期限开始日期
                            start_str = _extract_date_from_text(str(llm_result.get("服务期限开始日期", "")))
                            if start_str:
                                try:
                                    from datetime import datetime as dt
                                    contract_to_update.start_date = dt.strptime(start_str, "%Y-%m-%d")
                                    print(f"[OA附件解析] 开始日期: {start_str}")
                                except:
                                    pass
                            
                            # 解析服务期限结束日期
                            end_str = _extract_date_from_text(str(llm_result.get("服务期限结束日期", "")))
                            if end_str:
                                try:
                                    from datetime import datetime as dt
                                    contract_to_update.end_date = dt.strptime(end_str, "%Y-%m-%d")
                                    print(f"[OA附件解析] 结束日期: {end_str}")
                                except:
                                    pass
                            
                            # 解析金额（支持中文大写和阿拉伯数字）
                            # 尝试多个可能的字段名
                            amount_val = (
                                llm_result.get("服务费用总额") or
                                llm_result.get("合同金额") or
                                llm_result.get("合同标额") or
                                llm_result.get("合同总金额") or
                                llm_result.get("合同价款") or
                                llm_result.get("总金额") or
                                ""
                            )
                            if amount_val and str(amount_val) not in ["null", "未知", "未提及", "None", ""]:
                                parsed_amount = parse_amount(str(amount_val))
                                if parsed_amount and parsed_amount > 0:
                                    contract_to_update.amount = parsed_amount
                                    print(f"[OA附件解析] 金额: {parsed_amount}")
                            
                            # 如果LLM字段没提取到金额，尝试从raw_text正则提取
                            if not (contract_to_update.amount and contract_to_update.amount > 0):
                                from app.services.contract_parser import contract_parser as cp
                                regex_amount = cp._extract_amount(raw_text)
                                if regex_amount and regex_amount > 0:
                                    contract_to_update.amount = regex_amount
                                    print(f"[OA附件解析] 正则提取金额: {regex_amount}")
                        
                        # 存储解析摘要
                        if contract_to_update.source == 'oa_import':
                            extracted_data = {}
                            try:
                                if contract_to_update.extracted_data:
                                    extracted_data = json.loads(contract_to_update.extracted_data)
                            except:
                                pass
                            extracted_data['parsed_summary'] = parsed_summary
                            extracted_data['llm_summary'] = parsed_summary
                            contract_to_update.extracted_data = json.dumps(extracted_data, ensure_ascii=False)
                        else:
                            contract_to_update.summary = parsed_summary
                        
                        contract_to_update.updated_at = datetime.now()
                        db_session.commit()
                        print(f"[OA附件解析] 合同 {contract_id} 解析完成")
                finally:
                    db_session.close()
            except Exception as e:
                print(f"附件LLM解析失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 启动后台线程
        t = threading.Thread(target=_async_analyze_attachment)
        t.daemon = False
        t.start()
        
        return {
            "contract_id": contract_id,
            "attachment_id": attachment_id,
            "message": "正在后台分析附件，请稍候刷新查看"
        }
    
    except Exception as e:
        print(f"分析附件失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析附件失败: {str(e)}")




@router.put("/{contract_id}/attachments/{attachment_id}/set-primary")
async def set_primary_attachment(
    contract_id: int,
    attachment_id: int,
    principal: Principal = Depends(require_permission("contract.edit")),
    db: Session = Depends(get_db)
):
    """设置主附件（默认解析的附件）"""
    
    # 验证合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    ensure_entity_access(contract, principal, "contract", db)
    
    # 验证附件是否存在
    attachment = db.query(ContractAttachment).filter(
        ContractAttachment.id == attachment_id,
        ContractAttachment.contract_id == contract_id,
        ContractAttachment.is_deleted == False
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    try:
        # 将该合同的所有附件的is_primary设置为False
        db.query(ContractAttachment).filter(
            ContractAttachment.contract_id == contract_id,
            ContractAttachment.is_deleted == False
        ).update({"is_primary": False})
        
        # 将选中的附件设置为主附件
        attachment.is_primary = True
        
        db.commit()
        
        return {
            "contract_id": contract_id,
            "attachment_id": attachment_id,
            "message": "主附件设置成功"
        }
    
    except Exception as e:
        db.rollback()
        print(f"设置主附件失败: {e}")
        raise HTTPException(status_code=500, detail=f"设置主附件失败: {str(e)}")
