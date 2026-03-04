from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
import os

from app.database import get_db, Payment, Contract, ContractAttachment, User
from app.auth import get_current_user
from app.services import file_storage

router = APIRouter(prefix="/payments", tags=["付款管理"])


# ========== 付款管理模块 API (放在动态路由之前) ==========

class PaymentManagementResponse(BaseModel):
    id: int
    payment_theme: str = None
    payment_date: str = None
    amount: float = None
    operator: str = None
    cost_center: str = None
    project_name: str = None
    contract_number: str = None
    application_number: str = None
    payment_reason: str = None
    contract_id: int = None
    description: str = None
    file_path: str = None
    file_size: int = None
    created_at: datetime = None
    
    class Config:
        from_attributes = True


@router.get("/management/list", response_model=dict)
def list_payments_management(
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """付款管理列表"""
    query = db.query(Payment).filter(Payment.is_deleted == False)
    
    if search:
        query = query.filter(
            (Payment.payment_theme.contains(search)) |
            (Payment.operator.contains(search)) |
            (Payment.contract_number.contains(search)) |
            (Payment.application_number.contains(search)) |
            (Payment.project_name.contains(search))
        )
    
    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    payment_list = []
    for p in payments:
        payment_list.append({
            "id": p.id,
            "payment_theme": p.payment_theme or p.description or "无主题",
            "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else None,
            "amount": p.amount,
            "operator": p.operator,
            "cost_center": p.cost_center,
            "project_name": p.project_name,
            "contract_number": p.contract_number,
            "application_number": p.application_number,
            "payment_reason": p.payment_reason,
            "contract_id": p.contract_id,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else None,
        })
    
    return {
        "payments": payment_list,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/by-contract/{contract_id}", response_model=dict)
def get_payments_by_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同关联的付款记录"""
    payments = db.query(Payment).filter(
        Payment.contract_id == contract_id,
        Payment.is_deleted == False
    ).order_by(Payment.created_at.desc()).all()
    
    payment_list = []
    for p in payments:
        payment_list.append({
            "id": p.id,
            "payment_theme": p.payment_theme or p.description or "无主题",
            "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else None,
            "amount": p.amount,
            "operator": p.operator,
            "contract_number": p.contract_number,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else None,
        })
    
    return {
        "payments": payment_list,
        "total": len(payment_list)
    }


@router.get("/management/{payment_id}", response_model=dict)
def get_payment_management(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """付款管理详情"""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    
    contract = None
    if payment.contract_id:
        contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()

    contract_data = None
    if contract:
        # 解析甲乙方
        parties_a, parties_b = [], []
        if contract.parties:
            import json as _json
            try:
                parties = _json.loads(contract.parties) if isinstance(contract.parties, str) else contract.parties
                for p in (parties if isinstance(parties, list) else []):
                    role = (p.get("role") or "").strip()
                    name = (p.get("name") or "").strip()
                    if "乙" in role:
                        parties_b.append(name)
                    else:
                        parties_a.append(name)
            except Exception:
                pass

        contract_data = {
            "id": contract.id,
            "title": contract.title,
            "contract_number": contract.contract_number,
            "amount": contract.amount,
            "status": contract.status,
            "department": contract.department,
            "contract_type": contract.contract_type,
            "start_date": contract.start_date.strftime("%Y-%m-%d") if contract.start_date else None,
            "end_date": contract.end_date.strftime("%Y-%m-%d") if contract.end_date else None,
            "parties_a": "、".join(parties_a) if parties_a else None,
            "parties_b": "、".join(parties_b) if parties_b else None,
        }

    return {
        "id": payment.id,
        "payment_theme": payment.payment_theme or payment.description or "无主题",
        "payment_date": payment.payment_date.strftime("%Y-%m-%d") if payment.payment_date else None,
        "amount": payment.amount,
        "operator": payment.operator,
        "cost_center": payment.cost_center,
        "project_name": payment.project_name,
        "contract_number": payment.contract_number,
        "application_number": payment.application_number,
        "payment_reason": payment.payment_reason,
        "contract_id": payment.contract_id,
        "description": payment.description,
        "file_path": payment.file_path,
        "file_size": payment.file_size,
        "created_at": payment.created_at.strftime("%Y-%m-%d %H:%M:%S") if payment.created_at else None,
        "updated_at": payment.updated_at.strftime("%Y-%m-%d %H:%M:%S") if payment.updated_at else None,
        "contract": contract_data,
    }


@router.put("/management/{payment_id}/link-contract", response_model=dict)
def link_payment_to_contract(
    payment_id: int,
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """将付款记录关联到合同"""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    
    # 验证合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    # 更新关联
    payment.contract_id = contract_id
    payment.contract_number = contract.contract_number
    payment.updated_at = datetime.now()
    db.commit()
    
    return {
        "message": "关联成功",
        "payment_id": payment_id,
        "contract_id": contract_id,
        "contract": {
            "id": contract.id,
            "title": contract.title,
            "contract_number": contract.contract_number
        }
    }


@router.get("/search")
def search_payments(
    q: str = "",
    exclude_contract_id: Optional[int] = None,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """搜索付款记录（用于关联到合同）"""
    query = db.query(Payment).filter(Payment.is_deleted == False)

    if q.strip():
        query = query.filter(
            (Payment.payment_theme.contains(q)) |
            (Payment.description.contains(q)) |
            (Payment.operator.contains(q)) |
            (Payment.contract_number.contains(q)) |
            (Payment.application_number.contains(q)) |
            (Payment.project_name.contains(q))
        )

    payments = query.order_by(Payment.created_at.desc()).limit(page_size).all()

    # 已关联到该合同的付款记录ID集合（用于前端过滤）
    linked_ids: set = set()
    if exclude_contract_id:
        linked = db.query(Payment.id).filter(
            Payment.contract_id == exclude_contract_id,
            Payment.is_deleted == False
        ).all()
        linked_ids = {r[0] for r in linked}

    result = []
    for p in payments:
        if p.id in linked_ids:
            continue
        result.append({
            "id": p.id,
            "payment_theme": p.payment_theme or p.description or "无主题",
            "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else None,
            "amount": p.amount,
            "operator": p.operator,
            "contract_number": p.contract_number,
            "application_number": p.application_number,
            "contract_id": p.contract_id,
        })

    return {"payments": result}


@router.post("/{contract_id}/link")
def link_payment(
    contract_id: int,
    payment_id: int = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """将已有付款记录关联到合同"""
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")

    if payment.contract_id == contract_id:
        raise HTTPException(status_code=400, detail="该付款记录已关联到此合同")

    payment.contract_id = contract_id
    payment.contract_number = contract.contract_number
    payment.updated_at = datetime.now()
    db.commit()

    return {"message": "关联成功", "payment_id": payment_id, "contract_id": contract_id}


# ========== 原有的动态路由 ==========

class PaymentUpdate(BaseModel):
    payment_date: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None


@router.post("/{contract_id}/upload")
async def upload_payment(
    contract_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传付款资料"""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    # 保存文件
    file_path, file_size = await file_storage.save_upload_file(
        file, 
        subfolder=f"payments/{contract_id}"
    )
    
    # 创建付款记录
    payment = Payment(
        contract_id=contract_id,
        description=description or file.filename,
        file_path=file_path,
        file_size=file_size
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    return {"message": "文件上传成功", "payment_id": payment.id}


@router.get("/{contract_id}/list")
def list_contract_payments(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同的付款记录列表"""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    payments = db.query(Payment).filter(
        Payment.contract_id == contract_id,
        Payment.is_deleted == False
    ).order_by(Payment.created_at.desc()).all()
    
    return {
        "payments": [{
            "id": p.id,
            "description": p.description,
            "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else None,
            "amount": p.amount,
            "file_path": p.file_path,
            "file_size": p.file_size,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else None,
        } for p in payments]
    }


@router.get("/{payment_id}/download")
def download_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载付款资料"""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    
    if not payment.file_path or not os.path.exists(payment.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        payment.file_path, 
        filename=payment.description or "payment_file",
        media_type="application/octet-stream"
    )


@router.delete("/{payment_id}")
def delete_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除付款记录"""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    
    payment.is_deleted = True
    db.commit()
    
    return {"message": "付款记录删除成功"}
