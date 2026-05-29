from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Contract, OrgUnit, Partner, Payment, User, get_db
from app.security.bootstrap import is_selectable_primary_org
from app.security.permissions import require_permission
from app.security.principal import Principal

router = APIRouter(prefix="/orgs", tags=["组织架构"])


class OrgCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    code: Optional[str] = None
    org_type: str = "department"
    sort: int = 0
    status: str = "active"


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    org_type: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[str] = None


def _serialize_org(org: OrgUnit):
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "parent_id": org.parent_id,
        "path": org.path,
        "level": org.level,
        "org_type": org.org_type,
        "manager_user_id": org.manager_user_id,
        "status": org.status,
        "sort": org.sort,
        "is_selectable": org.status == "active" and org.org_type != "root",
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
    }


def _serialize_org_with_selectable(db: Session, org: OrgUnit):
    data = _serialize_org(org)
    data["is_selectable"] = is_selectable_primary_org(db, org)
    return data


def _next_org_code(db: Session) -> str:
    return f"ORG_{db.query(OrgUnit).count() + 1:04d}"


def _rebuild_subtree_paths(db: Session, org: OrgUnit):
    children = db.query(OrgUnit).filter(OrgUnit.parent_id == org.id).order_by(OrgUnit.sort.asc(), OrgUnit.id.asc()).all()
    for child in children:
        child.path = f"{org.path}/{child.code}"
        child.level = org.level + 1
        _rebuild_subtree_paths(db, child)


@router.get("")
def list_orgs(
    principal: Principal = Depends(require_permission("org.view")),
    db: Session = Depends(get_db),
):
    orgs = (
        db.query(OrgUnit)
        .filter(OrgUnit.status == "active")
        .order_by(OrgUnit.level.asc(), OrgUnit.sort.asc(), OrgUnit.id.asc())
        .all()
    )
    return {"items": [_serialize_org_with_selectable(db, item) for item in orgs]}


@router.get("/tree")
def get_org_tree(
    principal: Principal = Depends(require_permission("org.view")),
    db: Session = Depends(get_db),
):
    orgs = (
        db.query(OrgUnit)
        .filter(OrgUnit.status == "active")
        .order_by(OrgUnit.level.asc(), OrgUnit.sort.asc(), OrgUnit.id.asc())
        .all()
    )
    nodes = {}
    for org in orgs:
        nodes[org.id] = {**_serialize_org_with_selectable(db, org), "children": []}

    roots = []
    for org in orgs:
        node = nodes[org.id]
        if org.parent_id and org.parent_id in nodes:
            nodes[org.parent_id]["children"].append(node)
        else:
            roots.append(node)

    return {"items": roots}


@router.get("/{org_id}")
def get_org(
    org_id: int,
    principal: Principal = Depends(require_permission("org.view")),
    db: Session = Depends(get_db),
):
    org = db.query(OrgUnit).filter(OrgUnit.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    return _serialize_org_with_selectable(db, org)


@router.post("")
def create_org(
    req: OrgCreate,
    principal: Principal = Depends(require_permission("org.create")),
    db: Session = Depends(get_db),
):
    parent = None
    if req.parent_id is not None:
        parent = db.query(OrgUnit).filter(OrgUnit.id == req.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="上级组织不存在")

    code = (req.code or "").strip() or _next_org_code(db)
    if db.query(OrgUnit).filter(OrgUnit.code == code).first():
        raise HTTPException(status_code=400, detail="组织编码已存在")

    if parent:
        path = f"{parent.path}/{code}"
        level = parent.level + 1
    else:
        path = code
        level = 1

    org = OrgUnit(
        code=code,
        name=req.name.strip(),
        parent_id=req.parent_id,
        path=path,
        level=level,
        org_type=req.org_type,
        status=req.status,
        sort=req.sort,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return _serialize_org_with_selectable(db, org)


@router.put("/{org_id}")
def update_org(
    org_id: int,
    req: OrgUpdate,
    principal: Principal = Depends(require_permission("org.edit")),
    db: Session = Depends(get_db),
):
    org = db.query(OrgUnit).filter(OrgUnit.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if org.code == "ROOT" and req.parent_id is not None:
        raise HTTPException(status_code=400, detail="根组织不允许调整上级")

    if req.name is not None:
        org.name = req.name.strip()
    if req.org_type is not None:
        org.org_type = req.org_type
    if req.sort is not None:
        org.sort = req.sort
    if req.status is not None:
        org.status = req.status
    if req.parent_id is not None and req.parent_id != org.parent_id:
        if req.parent_id == org.id:
            raise HTTPException(status_code=400, detail="不能将组织挂到自己下面")
        new_parent = db.query(OrgUnit).filter(OrgUnit.id == req.parent_id).first()
        if not new_parent:
            raise HTTPException(status_code=400, detail="新的上级组织不存在")
        if new_parent.path.startswith(f"{org.path}/"):
            raise HTTPException(status_code=400, detail="不能将组织挂到自己的子节点下")
        org.parent_id = new_parent.id
        org.path = f"{new_parent.path}/{org.code}"
        org.level = new_parent.level + 1
        _rebuild_subtree_paths(db, org)

    db.commit()
    db.refresh(org)
    return _serialize_org_with_selectable(db, org)


@router.delete("/{org_id}")
def delete_org(
    org_id: int,
    principal: Principal = Depends(require_permission("org.delete")),
    db: Session = Depends(get_db),
):
    org = db.query(OrgUnit).filter(OrgUnit.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if org.code == "ROOT":
        raise HTTPException(status_code=400, detail="不能删除根组织")

    if db.query(OrgUnit).filter(OrgUnit.parent_id == org.id).first():
        raise HTTPException(status_code=400, detail="请先删除或迁移子组织")
    if db.query(User).filter(User.primary_org_id == org.id).first():
        raise HTTPException(status_code=400, detail="该组织下仍有关联用户")
    if db.query(Contract).filter(Contract.owner_org_id == org.id, Contract.is_deleted == False).first():
        raise HTTPException(status_code=400, detail="该组织下仍有关联合同")
    if db.query(Payment).filter(Payment.owner_org_id == org.id, Payment.is_deleted == False).first():
        raise HTTPException(status_code=400, detail="该组织下仍有关联付款")
    if db.query(Partner).filter(Partner.owner_org_id == org.id, Partner.is_deleted == False).first():
        raise HTTPException(status_code=400, detail="该组织下仍有关联合作伙伴")

    db.delete(org)
    db.commit()
    return {"message": "删除成功"}
