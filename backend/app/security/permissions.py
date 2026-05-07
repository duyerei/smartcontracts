from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import false, or_
from sqlalchemy.orm import Session

from app.auth import get_current_principal
from app.database import OrgUnit, get_db
from app.security.principal import Principal


def require_permission(permission_code: str):
    def _checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.has_permission(permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {permission_code}",
            )
        return principal

    return _checker


def get_accessible_org_ids(db: Session, principal: Principal, resource_type: str):
    if principal.is_super_admin:
        return None

    scope = principal.scope_for(resource_type)
    if not scope:
        return set()
    if scope.is_all():
        return None

    org_ids = set()
    if "ORG_ONLY" in scope.scope_types and principal.primary_org:
        org_ids.add(principal.primary_org.id)

    seed_org_ids = set(scope.org_ids)
    if "ORG_AND_CHILDREN" in scope.scope_types and principal.primary_org:
        seed_org_ids.add(principal.primary_org.id)

    if seed_org_ids:
        seed_orgs = db.query(OrgUnit).filter(OrgUnit.id.in_(seed_org_ids)).all()
        for org in seed_orgs:
            descendants = (
                db.query(OrgUnit.id)
                .filter(or_(OrgUnit.id == org.id, OrgUnit.path.like(f"{org.path}/%")))
                .all()
            )
            org_ids.update(item[0] for item in descendants)

    return org_ids


def apply_data_scope(
    query,
    principal: Principal,
    resource_type: str,
    db: Session,
    model,
    org_field: str = "owner_org_id",
    owner_user_field: str = "owner_user_id",
    created_by_field: str = "created_by",
    department_field: Optional[str] = "department",
):
    if principal.is_super_admin:
        return query

    scope = principal.scope_for(resource_type)
    if not scope:
        return query.filter(false())
    if scope.is_all():
        return query

    org_ids = get_accessible_org_ids(db, principal, resource_type)
    conditions = []

    if org_ids:
        conditions.append(getattr(model, org_field).in_(org_ids))
    if "SELF" in scope.scope_types:
        self_conditions = []
        if hasattr(model, owner_user_field):
            self_conditions.append(getattr(model, owner_user_field) == principal.user.id)
        if hasattr(model, created_by_field):
            self_conditions.append(getattr(model, created_by_field) == principal.user.id)
        if self_conditions:
            conditions.append(or_(*self_conditions))

    if not conditions:
        return query.filter(false())
    return query.filter(or_(*conditions))


def can_access_entity(
    entity,
    principal: Principal,
    resource_type: str,
    db: Session,
    org_attr: str = "owner_org_id",
    owner_user_attr: str = "owner_user_id",
    created_by_attr: str = "created_by",
    department_attr: Optional[str] = "department",
) -> bool:
    if principal.is_super_admin:
        return True

    scope = principal.scope_for(resource_type)
    if not scope:
        return False
    if scope.is_all():
        return True

    org_ids = get_accessible_org_ids(db, principal, resource_type)
    if org_ids is not None:
        entity_org_id = getattr(entity, org_attr, None)
        if entity_org_id in org_ids:
            return True

    if "SELF" in scope.scope_types:
        entity_owner_user_id = getattr(entity, owner_user_attr, None)
        entity_created_by = getattr(entity, created_by_attr, None)
        if entity_owner_user_id == principal.user.id or entity_created_by == principal.user.id:
            return True

    return False


def ensure_entity_access(
    entity,
    principal: Principal,
    resource_type: str,
    db: Session,
    org_attr: str = "owner_org_id",
    owner_user_attr: str = "owner_user_id",
    created_by_attr: str = "created_by",
    department_attr: Optional[str] = "department",
):
    if not can_access_entity(
        entity,
        principal,
        resource_type,
        db,
        org_attr=org_attr,
        owner_user_attr=owner_user_attr,
        created_by_attr=created_by_attr,
        department_attr=department_attr,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该数据")
    return entity


def populate_ownership_fields(entity, principal: Principal, fallback_department: Optional[str] = None):
    if hasattr(entity, "owner_org_id") and principal.primary_org and not getattr(entity, "owner_org_id", None):
        entity.owner_org_id = principal.primary_org.id
    if hasattr(entity, "owner_user_id") and not getattr(entity, "owner_user_id", None):
        entity.owner_user_id = principal.user.id
    if hasattr(entity, "created_by") and not getattr(entity, "created_by", None):
        entity.created_by = principal.user.id
    if hasattr(entity, "department") and not getattr(entity, "department", None):
        entity.department = fallback_department or (principal.primary_org.name if principal.primary_org else "")
    return entity
