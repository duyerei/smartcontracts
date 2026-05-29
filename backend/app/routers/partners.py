from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import json
import os
import uuid
from pathlib import Path
import re

from app.database import get_db, Partner, PartnerAttachment, Contract, User
from app.auth import get_current_user
from app.security.permissions import apply_data_scope, ensure_entity_access, populate_ownership_fields, require_permission
from app.security.principal import Principal

router = APIRouter(prefix="/partners", tags=["合作伙伴"])


def _normalize_name(name: str) -> str:
    """标准化合作伙伴名称：统一全角/半角括号等"""
    import re
    name = name.strip()
    name = name.replace('（', '(').replace('）', ')')
    name = re.sub(r'\s+', '', name)  # 去除所有空白
    return name


def _extract_partner_names(parties_json: str) -> list:
    """从合同parties字段提取合作伙伴名称列表（去重）"""
    if not parties_json:
        return []
    try:
        parties = json.loads(parties_json) if isinstance(parties_json, str) else parties_json
        if isinstance(parties, list):
            seen = set()
            result = []
            for p in parties:
                if not p or str(p).strip() in ("待填写", "null", "None", "未识别"):
                    continue
                normalized = _normalize_name(str(p))
                if normalized not in seen:
                    seen.add(normalized)
                    result.append(str(p).strip())
            return result
    except Exception:
        pass
    return []


def _valid_partner_value(value) -> str:
    """清理合同解析出的合作伙伴字段，过滤空值和占位符。"""
    if value is None:
        return ""
    text = str(value).strip()
    if text in ("", "-", "待填写", "null", "None", "未识别", "未知", "未提及", "暂无", "不详"):
        return ""
    return text


def _pick_raw_value(raw: dict, *keys: str) -> str:
    for key in keys:
        value = _valid_partner_value(raw.get(key))
        if value:
            return value
    return ""


def _extract_bank_info_from_text(text: str) -> dict:
    """从合同原文中兜底提取开户行和银行账号。"""
    result = {"bank_name": "", "bank_account": ""}
    if not text:
        return result
    bank_match = re.search(r"(?:开户行|开户银行)[：:\s]+([^\n\r，,；;]{2,80})", text)
    if bank_match:
        result["bank_name"] = _valid_partner_value(bank_match.group(1))
    account_match = re.search(r"(?:银行账号|账号|账户)[：:\s]+([0-9][0-9\s-]{8,40})", text)
    if account_match:
        result["bank_account"] = re.sub(r"\s+", "", account_match.group(1)).strip("-")
    return result


def _extract_partner_info_from_contract(contract: Contract, partner_name: str) -> dict:
    """从合同字段和 raw_data 中提取合作伙伴基础信息。"""
    raw = {}
    if contract.raw_data:
        try:
            raw = json.loads(contract.raw_data)
        except Exception:
            raw = {}

    is_counterparty = False
    normalized_partner = _normalize_name(partner_name)
    if contract.counterparty and _normalize_name(contract.counterparty) == normalized_partner:
        is_counterparty = True

    contact_name = ""
    contact_phone = ""
    address = ""
    if is_counterparty:
        contact_name = _valid_partner_value(contract.counterparty_contact)
        address = _valid_partner_value(contract.counterparty_address)
        contact_phone = _valid_partner_value(raw.get("_counterparty_phone"))

    if not contact_name:
        contact_name = _pick_raw_value(raw, "对方联系人", "乙方联系人", "counterparty_contact", "对方经办人")
    if not contact_phone:
        contact_phone = _pick_raw_value(raw, "_counterparty_phone", "对方电话", "乙方电话", "联系电话", "电话")
    if not address:
        address = _pick_raw_value(raw, "counterparty_address", "对方地址", "乙方地址", "地址", "服务地点")

    if contact_name and re.fullmatch(r"\d{7,13}", contact_name):
        contact_phone = contact_phone or contact_name
        contact_name = ""

    bank_name = _pick_raw_value(raw, "bank_name", "开户行", "开户银行", "乙方开户行", "收款银行", "收款方开户行")
    bank_account = _pick_raw_value(raw, "bank_account", "银行账号", "收款账号", "乙方银行账号", "账号")
    if not bank_name or not bank_account:
        text_bank = _extract_bank_info_from_text(contract.raw_text or "")
        bank_name = bank_name or text_bank["bank_name"]
        bank_account = bank_account or text_bank["bank_account"]

    return {
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "address": address,
        "bank_name": bank_name,
        "bank_account": bank_account,
    }


def _fill_missing_partner_info(partner: Partner, info: dict) -> bool:
    changed = False
    for field in ("contact_name", "contact_phone", "address", "bank_name", "bank_account"):
        value = _valid_partner_value(info.get(field))
        if value and not getattr(partner, field, None):
            setattr(partner, field, value)
            changed = True
    if changed:
        partner.updated_at = datetime.now()
    return changed


@router.get("")
def list_partners(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    principal: Principal = Depends(require_permission("partner.view")),
    db: Session = Depends(get_db)
):
    """合作伙伴列表"""
    query = db.query(Partner).filter(Partner.is_deleted == False)
    query = apply_data_scope(query, principal, "partner", db, Partner)
    if search:
        query = query.filter(
            (Partner.name.contains(search)) |
            (Partner.contact_name.contains(search)) |
            (Partner.contact_phone.contains(search))
        )
    total = query.count()
    partners = query.order_by(Partner.name.asc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for p in partners:
        # 统计关联合同数
        contract_query = db.query(Contract).filter(
            Contract.parties.contains(p.name),
            Contract.is_deleted == False
        )
        contract_query = apply_data_scope(contract_query, principal, "contract", db, Contract)
        contract_count = contract_query.count()
        result.append({
            "id": p.id,
            "name": p.name,
            "contact_name": p.contact_name,
            "contact_phone": p.contact_phone,
            "address": p.address,
            "bank_name": p.bank_name,
            "bank_account": p.bank_account,
            "contract_count": contract_count,
            "created_at": p.created_at.strftime("%Y-%m-%d") if p.created_at else None,
        })

    return {"partners": result, "total": total, "page": page, "page_size": page_size}


@router.post("/deduplicate")
def deduplicate_partners(
    principal: Principal = Depends(require_permission("partner.edit")),
    db: Session = Depends(get_db)
):
    """手动触发合作伙伴去重（直接SQL + Python双重去重）"""
    # 方法1：直接SQL删除完全相同名称的重复记录（保留最小id）
    sql_deleted = 0
    try:
        result = db.execute(
            """
            UPDATE partners SET is_deleted = 1
            WHERE is_deleted = 0
              AND id NOT IN (
                SELECT MIN(id) FROM partners
                WHERE is_deleted = 0
                GROUP BY name
              )
            """
        )
        sql_deleted = result.rowcount
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[去重] SQL去重失败: {e}")

    # 方法2：Python标准化名称去重（处理括号/空格差异）
    py_merged = _deduplicate_existing_partners(db)

    total = sql_deleted + py_merged
    return {"message": f"去重完成，共清理 {total} 个重复记录（精确匹配 {sql_deleted} 个，标准化匹配 {py_merged} 个）"}


@router.post("")
def create_partner(
    data: dict,
    principal: Principal = Depends(require_permission("partner.create")),
    db: Session = Depends(get_db)
):
    """新建合作伙伴"""
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="合作伙伴名称不能为空")

    # 用标准化名称做去重检查
    normalized = _normalize_name(name)
    existing_partners = db.query(Partner).filter(Partner.is_deleted == False).all()
    for p in existing_partners:
        if _normalize_name(p.name) == normalized:
            raise HTTPException(status_code=400, detail=f"该合作伙伴已存在（{p.name}）")

    partner = Partner(
        name=name,
        contact_name=data.get("contact_name"),
        contact_phone=data.get("contact_phone"),
        address=data.get("address"),
        bank_name=data.get("bank_name"),
        bank_account=data.get("bank_account"),
        notes=data.get("notes"),
    )
    populate_ownership_fields(partner, principal)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return {"id": partner.id, "message": "创建成功"}


@router.get("/sync-from-contracts")
def sync_partners_from_contracts(
    principal: Principal = Depends(require_permission("partner.create")),
    db: Session = Depends(get_db)
):
    """从合同中自动提取合作伙伴（去重），同时清理已有重复"""
    # 第1步：SQL精确去重（完全相同名称）
    sql_deleted = 0
    try:
        result = db.execute(
            """
            UPDATE partners SET is_deleted = 1
            WHERE is_deleted = 0
              AND id NOT IN (
                SELECT MIN(id) FROM partners
                WHERE is_deleted = 0
                GROUP BY name
              )
            """
        )
        sql_deleted = result.rowcount
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[同步] SQL去重失败: {e}")

    # 第2步：Python标准化名称去重（括号/空格差异）
    merged = _deduplicate_existing_partners(db)

    # 第3步：从合同中提取新合作伙伴
    contracts_query = db.query(Contract).filter(
        Contract.is_deleted == False,
        Contract.parties != None,
        Contract.parties != "",
        Contract.parties != "[]"
    )
    contracts = apply_data_scope(contracts_query, principal, "contract", db, Contract).all()

    created = 0
    existing_query = db.query(Partner).filter(Partner.is_deleted == False)
    existing_partners = apply_data_scope(existing_query, principal, "partner", db, Partner).all()
    existing_normalized = {_normalize_name(p.name): p for p in existing_partners}

    for contract in contracts:
        names = _extract_partner_names(contract.parties)
        for name in names:
            if not name or len(name) < 2:
                continue
            normalized = _normalize_name(name)
            info = _extract_partner_info_from_contract(contract, name)
            if normalized not in existing_normalized:
                partner = Partner(
                    name=name,
                    contact_name=info["contact_name"],
                    contact_phone=info["contact_phone"],
                    address=info["address"],
                    bank_name=info["bank_name"],
                    bank_account=info["bank_account"],
                    owner_org_id=contract.owner_org_id,
                    owner_user_id=contract.owner_user_id,
                    created_by=contract.created_by,
                )
                db.add(partner)
                existing_normalized[normalized] = partner
                created += 1
            else:
                _fill_missing_partner_info(existing_normalized[normalized], info)

    db.commit()
    total_dedup = sql_deleted + merged
    msg = f"同步完成，新增 {created} 个合作伙伴"
    if total_dedup > 0:
        msg += f"，合并去重 {total_dedup} 个"
    return {"message": msg}


def _deduplicate_existing_partners(db: Session) -> int:
    """清理数据库中已有的重复合作伙伴，保留最早创建的那条"""
    partners = db.query(Partner).filter(Partner.is_deleted == False).order_by(Partner.created_at.asc()).all()

    # 按标准化名称分组
    groups: dict[str, list] = {}
    for p in partners:
        key = _normalize_name(p.name)
        groups.setdefault(key, []).append(p)

    merged = 0
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        # 保留第一个（最早创建），其余标记删除
        keep = group[0]
        for dup in group[1:]:
            # 把重复记录的附件转移到保留记录
            db.query(PartnerAttachment).filter(
                PartnerAttachment.partner_id == dup.id,
                PartnerAttachment.is_deleted == False
            ).update({"partner_id": keep.id})
            # 合并联系信息（如果保留记录没有的话）
            if not keep.contact_name and dup.contact_name:
                keep.contact_name = dup.contact_name
            if not keep.contact_phone and dup.contact_phone:
                keep.contact_phone = dup.contact_phone
            if not keep.address and dup.address:
                keep.address = dup.address
            if not keep.bank_name and dup.bank_name:
                keep.bank_name = dup.bank_name
            if not keep.bank_account and dup.bank_account:
                keep.bank_account = dup.bank_account
            if not keep.notes and dup.notes:
                keep.notes = dup.notes
            dup.is_deleted = True
            merged += 1

    if merged > 0:
        db.commit()
    return merged


@router.get("/{partner_id}")
def get_partner(
    partner_id: int,
    principal: Principal = Depends(require_permission("partner.view")),
    db: Session = Depends(get_db)
):
    """合作伙伴详情"""
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")
    ensure_entity_access(partner, principal, "partner", db)

    # 关联合同
    contracts_query = db.query(Contract).filter(
        Contract.parties.contains(partner.name),
        Contract.is_deleted == False
    )
    contracts = apply_data_scope(
        contracts_query,
        principal,
        "contract",
        db,
        Contract,
    ).order_by(Contract.updated_at.desc()).all()

    info_changed = False
    for c in contracts:
        info_changed = _fill_missing_partner_info(partner, _extract_partner_info_from_contract(c, partner.name)) or info_changed
    if info_changed:
        db.commit()
        db.refresh(partner)

    contract_list = []
    for c in contracts:
        contract_list.append({
            "id": c.id,
            "title": c.title,
            "contract_number": c.contract_number,
            "contract_type": c.contract_type,
            "amount": c.amount,
            "status": c.status,
            "start_date": c.start_date.strftime("%Y-%m-%d") if c.start_date else None,
            "end_date": c.end_date.strftime("%Y-%m-%d") if c.end_date else None,
            "signed_date": c.signed_date.strftime("%Y-%m-%d") if c.signed_date else None,
        })

    # 附件
    attachments = db.query(PartnerAttachment).filter(
        PartnerAttachment.partner_id == partner_id,
        PartnerAttachment.is_deleted == False
    ).all()

    return {
        "id": partner.id,
        "name": partner.name,
        "contact_name": partner.contact_name,
        "contact_phone": partner.contact_phone,
        "address": partner.address,
        "bank_name": partner.bank_name,
        "bank_account": partner.bank_account,
        "notes": partner.notes,
        "created_at": partner.created_at.strftime("%Y-%m-%d %H:%M:%S") if partner.created_at else None,
        "updated_at": partner.updated_at.strftime("%Y-%m-%d %H:%M:%S") if partner.updated_at else None,
        "contracts": contract_list,
        "attachments": [
            {
                "id": a.id,
                "file_name": a.file_name,
                "file_size": a.file_size,
                "created_at": a.created_at.strftime("%Y-%m-%d") if a.created_at else None,
            }
            for a in attachments
        ],
    }


@router.put("/{partner_id}")
def update_partner(
    partner_id: int,
    data: dict,
    principal: Principal = Depends(require_permission("partner.edit")),
    db: Session = Depends(get_db)
):
    """更新合作伙伴"""
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")
    ensure_entity_access(partner, principal, "partner", db)

    for field in ("name", "contact_name", "contact_phone", "address", "bank_name", "bank_account", "notes"):
        if field in data:
            setattr(partner, field, data[field])

    partner.updated_at = datetime.now()
    db.commit()
    return {"message": "更新成功"}


@router.delete("/{partner_id}")
def delete_partner(
    partner_id: int,
    principal: Principal = Depends(require_permission("partner.delete")),
    db: Session = Depends(get_db)
):
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")
    ensure_entity_access(partner, principal, "partner", db)
    partner.is_deleted = True
    partner.updated_at = datetime.now()
    db.commit()
    return {"message": "删除成功"}


@router.post("/{partner_id}/attachments")
async def upload_partner_attachment(
    partner_id: int,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_permission("partner.upload_attachment")),
    db: Session = Depends(get_db)
):
    """上传合作伙伴附件"""
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")
    ensure_entity_access(partner, principal, "partner", db)

    content = await file.read()
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    save_dir = Path("/app/storage/partners")
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{file_id}{ext}"
    with open(save_path, "wb") as f:
        f.write(content)

    att = PartnerAttachment(
        partner_id=partner_id,
        file_name=file.filename,
        file_path=str(save_path),
        file_size=len(content),
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "message": "上传成功"}


@router.get("/{partner_id}/attachments/{att_id}/download")
def download_partner_attachment(
    partner_id: int,
    att_id: int,
    principal: Principal = Depends(require_permission("partner.view")),
    db: Session = Depends(get_db)
):
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")
    ensure_entity_access(partner, principal, "partner", db)

    att = db.query(PartnerAttachment).filter(
        PartnerAttachment.id == att_id,
        PartnerAttachment.partner_id == partner_id,
        PartnerAttachment.is_deleted == False
    ).first()
    if not att or not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="附件不存在")
    return FileResponse(att.file_path, filename=att.file_name)


@router.delete("/{partner_id}/attachments/{att_id}")
def delete_partner_attachment(
    partner_id: int,
    att_id: int,
    principal: Principal = Depends(require_permission("partner.edit")),
    db: Session = Depends(get_db)
):
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")
    ensure_entity_access(partner, principal, "partner", db)

    att = db.query(PartnerAttachment).filter(
        PartnerAttachment.id == att_id,
        PartnerAttachment.partner_id == partner_id,
        PartnerAttachment.is_deleted == False
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    att.is_deleted = True
    db.commit()
    return {"message": "删除成功"}
