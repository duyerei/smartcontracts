from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import json
import os
import uuid
from pathlib import Path

from app.database import get_db, Partner, PartnerAttachment, Contract, User
from app.auth import get_current_user

router = APIRouter(prefix="/partners", tags=["合作伙伴"])


def _extract_partner_names(parties_json: str) -> list:
    """从合同parties字段提取合作伙伴名称列表"""
    if not parties_json:
        return []
    try:
        parties = json.loads(parties_json) if isinstance(parties_json, str) else parties_json
        if isinstance(parties, list):
            return [str(p).strip() for p in parties if p and str(p).strip() not in ("待填写", "null", "None", "未识别")]
    except Exception:
        pass
    return []


@router.get("")
def list_partners(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """合作伙伴列表"""
    query = db.query(Partner).filter(Partner.is_deleted == False)
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
        contract_count = db.query(Contract).filter(
            Contract.parties.contains(p.name),
            Contract.is_deleted == False
        ).count()
        result.append({
            "id": p.id,
            "name": p.name,
            "contact_name": p.contact_name,
            "contact_phone": p.contact_phone,
            "address": p.address,
            "contract_count": contract_count,
            "created_at": p.created_at.strftime("%Y-%m-%d") if p.created_at else None,
        })

    return {"partners": result, "total": total, "page": page, "page_size": page_size}


@router.post("")
def create_partner(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """新建合作伙伴"""
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="合作伙伴名称不能为空")

    existing = db.query(Partner).filter(Partner.name == name, Partner.is_deleted == False).first()
    if existing:
        raise HTTPException(status_code=400, detail="该合作伙伴已存在")

    partner = Partner(
        name=name,
        contact_name=data.get("contact_name"),
        contact_phone=data.get("contact_phone"),
        address=data.get("address"),
        bank_name=data.get("bank_name"),
        bank_account=data.get("bank_account"),
        notes=data.get("notes"),
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return {"id": partner.id, "message": "创建成功"}


@router.get("/sync-from-contracts")
def sync_partners_from_contracts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """从合同中自动提取合作伙伴（去重）"""
    contracts = db.query(Contract).filter(
        Contract.is_deleted == False,
        Contract.parties != None,
        Contract.parties != "",
        Contract.parties != "[]"
    ).all()

    created = 0
    for contract in contracts:
        names = _extract_partner_names(contract.parties)
        for name in names:
            if not name or len(name) < 2:
                continue
            existing = db.query(Partner).filter(
                Partner.name == name,
                Partner.is_deleted == False
            ).first()
            if not existing:
                db.add(Partner(name=name))
                created += 1

    db.commit()
    return {"message": f"同步完成，新增 {created} 个合作伙伴"}


@router.get("/{partner_id}")
def get_partner(
    partner_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """合作伙伴详情"""
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")

    # 关联合同
    contracts = db.query(Contract).filter(
        Contract.parties.contains(partner.name),
        Contract.is_deleted == False
    ).order_by(Contract.updated_at.desc()).all()

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新合作伙伴"""
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")

    for field in ("name", "contact_name", "contact_phone", "address", "bank_name", "bank_account", "notes"):
        if field in data:
            setattr(partner, field, data[field])

    partner.updated_at = datetime.now()
    db.commit()
    return {"message": "更新成功"}


@router.delete("/{partner_id}")
def delete_partner(
    partner_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")
    partner.is_deleted = True
    partner.updated_at = datetime.now()
    db.commit()
    return {"message": "删除成功"}


@router.post("/{partner_id}/attachments")
async def upload_partner_attachment(
    partner_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传合作伙伴附件"""
    partner = db.query(Partner).filter(Partner.id == partner_id, Partner.is_deleted == False).first()
    if not partner:
        raise HTTPException(status_code=404, detail="合作伙伴不存在")

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
