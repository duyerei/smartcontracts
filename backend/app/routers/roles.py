from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Permission, Role, RoleDataScope, RolePermission, RoleScopeOrg, UserRole, get_db
from app.security.permissions import require_permission
from app.security.principal import Principal

router = APIRouter(prefix="/roles", tags=["角色权限"])


class RoleCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    status: str = "active"


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class PermissionAssignment(BaseModel):
    permission_codes: List[str]


class DataScopeItem(BaseModel):
    resource_type: str
    scope_type: str
    org_ids: List[int] = []


class DataScopeAssignment(BaseModel):
    scopes: List[DataScopeItem]


def _serialize_role(db: Session, role: Role):
    permission_rows = (
        db.query(Permission.code, Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .filter(RolePermission.role_id == role.id)
        .all()
    )
    scopes = db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).all()
    scope_org_rows = db.query(RoleScopeOrg).filter(RoleScopeOrg.role_data_scope_id.in_([item.id for item in scopes])).all() if scopes else []
    scope_org_map: Dict[int, List[int]] = {}
    for item in scope_org_rows:
        scope_org_map.setdefault(item.role_data_scope_id, []).append(item.org_unit_id)

    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "status": role.status,
        "is_system": role.is_system,
        "permissions": [{"code": code, "name": name} for code, name in permission_rows],
        "data_scopes": [
            {
                "resource_type": item.resource_type,
                "scope_type": item.scope_type,
                "org_ids": sorted(scope_org_map.get(item.id, [])),
            }
            for item in scopes
        ],
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


@router.get("")
def list_roles(
    principal: Principal = Depends(require_permission("role.view")),
    db: Session = Depends(get_db),
):
    roles = db.query(Role).order_by(Role.is_system.desc(), Role.created_at.asc()).all()
    return {"items": [_serialize_role(db, item) for item in roles]}


@router.get("/permissions")
def list_permissions(
    principal: Principal = Depends(require_permission("role.view")),
    db: Session = Depends(get_db),
):
    items = db.query(Permission).order_by(Permission.module.asc(), Permission.code.asc()).all()
    return {
        "items": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "module": item.module,
                "action": item.action,
                "resource_type": item.resource_type,
            }
            for item in items
        ]
    }


@router.get("/{role_id}")
def get_role(
    role_id: int,
    principal: Principal = Depends(require_permission("role.view")),
    db: Session = Depends(get_db),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _serialize_role(db, role)


@router.post("")
def create_role(
    req: RoleCreate,
    principal: Principal = Depends(require_permission("role.create")),
    db: Session = Depends(get_db),
):
    if db.query(Role).filter(Role.code == req.code.strip()).first():
        raise HTTPException(status_code=400, detail="角色编码已存在")

    role = Role(
        code=req.code.strip(),
        name=req.name.strip(),
        description=req.description,
        status=req.status,
        is_system=False,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return _serialize_role(db, role)


@router.put("/{role_id}")
def update_role(
    role_id: int,
    req: RoleUpdate,
    principal: Principal = Depends(require_permission("role.edit")),
    db: Session = Depends(get_db),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if req.name is not None:
        role.name = req.name.strip()
    if req.description is not None:
        role.description = req.description
    if req.status is not None:
        role.status = req.status

    db.commit()
    db.refresh(role)
    return _serialize_role(db, role)


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    principal: Principal = Depends(require_permission("role.delete")),
    db: Session = Depends(get_db),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统角色不允许删除")
    if db.query(UserRole).filter(UserRole.role_id == role.id).first():
        raise HTTPException(status_code=400, detail="该角色仍被用户使用，无法删除")

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    scope_ids = [item.id for item in db.query(RoleDataScope.id).filter(RoleDataScope.role_id == role.id).all()]
    if scope_ids:
        db.query(RoleScopeOrg).filter(RoleScopeOrg.role_data_scope_id.in_(scope_ids)).delete(synchronize_session=False)
    db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).delete()
    db.delete(role)
    db.commit()
    return {"message": "删除成功"}


@router.put("/{role_id}/permissions")
def update_role_permissions(
    role_id: int,
    req: PermissionAssignment,
    principal: Principal = Depends(require_permission("role.assign_permission")),
    db: Session = Depends(get_db),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    permissions = db.query(Permission).filter(Permission.code.in_(req.permission_codes)).all()
    found_codes = {item.code for item in permissions}
    missing_codes = [code for code in req.permission_codes if code not in found_codes]
    if missing_codes:
        raise HTTPException(status_code=400, detail=f"权限不存在: {missing_codes}")

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    for permission in permissions:
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))

    db.commit()
    return _serialize_role(db, role)


@router.get("/{role_id}/data-scopes")
def get_role_data_scopes(
    role_id: int,
    principal: Principal = Depends(require_permission("role.view")),
    db: Session = Depends(get_db),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"item": _serialize_role(db, role)["data_scopes"]}


@router.put("/{role_id}/data-scopes")
def update_role_data_scopes(
    role_id: int,
    req: DataScopeAssignment,
    principal: Principal = Depends(require_permission("role.assign_permission")),
    db: Session = Depends(get_db),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    existing_scopes = db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).all()
    existing_scope_ids = [item.id for item in existing_scopes]
    if existing_scope_ids:
        db.query(RoleScopeOrg).filter(RoleScopeOrg.role_data_scope_id.in_(existing_scope_ids)).delete(synchronize_session=False)
    db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).delete()

    for item in req.scopes:
        scope = RoleDataScope(role_id=role.id, resource_type=item.resource_type, scope_type=item.scope_type)
        db.add(scope)
        db.flush()
        for org_id in list(dict.fromkeys(item.org_ids)):
            db.add(RoleScopeOrg(role_data_scope_id=scope.id, org_unit_id=org_id))

    db.commit()
    return _serialize_role(db, role)
