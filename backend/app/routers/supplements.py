from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db, Supplement, Contract
from app.security.permissions import ensure_entity_access, require_permission
from app.security.principal import Principal

router = APIRouter(prefix="/supplements", tags=["补充协议"])


class SupplementUpdate(BaseModel):
    title: Optional[str] = None
    signed_date: Optional[str] = None
    amount: Optional[float] = None


class LinkSupplementRequest(BaseModel):
    linked_contract_id: int


def _contract_to_supplement_dict(s: Supplement, linked_contract: Contract = None) -> dict:
    result = {
        "id": s.id,
        "contract_id": s.contract_id,
        "linked_contract_id": s.linked_contract_id,
        "title": s.title,
        "signed_date": s.signed_date.isoformat() if s.signed_date else None,
        "amount": s.amount,
        "file_path": s.file_path,
        "file_size": s.file_size,
        "created_at": s.created_at.isoformat(),
        "linked_contract": None,
    }
    if linked_contract:
        result["linked_contract"] = {
            "id": linked_contract.id,
            "contract_number": linked_contract.contract_number,
            "title": linked_contract.title,
            "amount": linked_contract.amount,
            "signed_date": linked_contract.signed_date.isoformat() if linked_contract.signed_date else None,
            "status": linked_contract.status,
        }
    return result


def _get_contract_or_404(db: Session, contract_id: int, detail: str) -> Contract:
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False,
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=detail)
    return contract


@router.post("/{contract_id}/link")
def link_supplement(
    contract_id: int,
    body: LinkSupplementRequest,
    principal: Principal = Depends(require_permission("supplement.create")),
    db: Session = Depends(get_db)
):
    """将另一份合同关联为当前合同的补充协议"""
    contract = _get_contract_or_404(db, contract_id, "主合同不存在")
    ensure_entity_access(contract, principal, "contract", db)

    linked = _get_contract_or_404(db, body.linked_contract_id, "关联合同不存在")
    ensure_entity_access(linked, principal, "contract", db)

    if body.linked_contract_id == contract_id:
        raise HTTPException(status_code=400, detail="不能将合同关联为自身的补充协议")

    # Check not already linked
    existing = db.query(Supplement).filter(
        Supplement.contract_id == contract_id,
        Supplement.linked_contract_id == body.linked_contract_id,
        Supplement.is_deleted == False
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该合同已关联为补充协议")

    supplement = Supplement(
        contract_id=contract_id,
        linked_contract_id=body.linked_contract_id,
        title=linked.title or linked.contract_number or f"补充协议-{linked.id}",
        signed_date=linked.signed_date,
        amount=linked.amount,
        file_path=None,
        file_size=None,
    )
    db.add(supplement)
    db.commit()
    db.refresh(supplement)

    return _contract_to_supplement_dict(supplement, linked)


@router.get("/{contract_id}/list")
def list_supplements(
    contract_id: int,
    principal: Principal = Depends(require_permission("supplement.view")),
    db: Session = Depends(get_db)
):
    """获取合同的所有补充协议"""
    contract = _get_contract_or_404(db, contract_id, "主合同不存在")
    ensure_entity_access(contract, principal, "contract", db)

    supplements = db.query(Supplement).filter(
        Supplement.contract_id == contract_id,
        Supplement.is_deleted == False
    ).order_by(Supplement.created_at.desc()).all()

    result = []
    for s in supplements:
        linked_contract = None
        if s.linked_contract_id:
            linked_contract = db.query(Contract).filter(
                Contract.id == s.linked_contract_id,
                Contract.is_deleted == False
            ).first()
            if linked_contract and not linked_contract.is_deleted:
                try:
                    ensure_entity_access(linked_contract, principal, "contract", db)
                except HTTPException:
                    continue
        result.append(_contract_to_supplement_dict(s, linked_contract))

    return {"supplements": result}


@router.delete("/{supplement_id}")
def delete_supplement(
    supplement_id: int,
    principal: Principal = Depends(require_permission("supplement.delete")),
    db: Session = Depends(get_db)
):
    """删除补充协议关联"""
    supplement = db.query(Supplement).filter(
        Supplement.id == supplement_id,
        Supplement.is_deleted == False
    ).first()
    if not supplement:
        raise HTTPException(status_code=404, detail="补充协议不存在")

    contract = _get_contract_or_404(db, supplement.contract_id, "主合同不存在")
    ensure_entity_access(contract, principal, "contract", db)
    if supplement.linked_contract_id:
        linked_contract = _get_contract_or_404(db, supplement.linked_contract_id, "关联合同不存在")
        ensure_entity_access(linked_contract, principal, "contract", db)

    supplement.is_deleted = True
    db.commit()
    return {"message": "补充协议删除成功"}


@router.patch("/{supplement_id}")
def update_supplement(
    supplement_id: int,
    update_data: SupplementUpdate = Body(...),
    principal: Principal = Depends(require_permission("supplement.edit")),
    db: Session = Depends(get_db)
):
    """更新补充协议信息"""
    supplement = db.query(Supplement).filter(
        Supplement.id == supplement_id,
        Supplement.is_deleted == False
    ).first()
    if not supplement:
        raise HTTPException(status_code=404, detail="补充协议不存在")

    contract = _get_contract_or_404(db, supplement.contract_id, "主合同不存在")
    ensure_entity_access(contract, principal, "contract", db)
    linked_contract = None
    if supplement.linked_contract_id:
        linked_contract = _get_contract_or_404(db, supplement.linked_contract_id, "关联合同不存在")
        ensure_entity_access(linked_contract, principal, "contract", db)

    if update_data.title is not None:
        supplement.title = update_data.title

    if update_data.signed_date is not None:
        if update_data.signed_date:
            try:
                supplement.signed_date = datetime.strptime(update_data.signed_date, "%Y-%m-%d")
            except Exception:
                raise HTTPException(status_code=400, detail="日期格式错误")
        else:
            supplement.signed_date = None

    if update_data.amount is not None:
        supplement.amount = update_data.amount if update_data.amount else None

    db.commit()
    db.refresh(supplement)

    return _contract_to_supplement_dict(supplement, linked_contract)
