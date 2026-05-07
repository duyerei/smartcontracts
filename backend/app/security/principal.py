from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.database import OrgUnit, Permission, Role, RoleDataScope, RolePermission, RoleScopeOrg, User, UserRole


@dataclass
class PrincipalOrg:
    id: int
    name: str
    code: str
    path: str
    level: int


@dataclass
class PrincipalRole:
    id: int
    code: str
    name: str


@dataclass
class PrincipalDataScope:
    resource_type: str
    scope_types: Set[str] = field(default_factory=set)
    org_ids: Set[int] = field(default_factory=set)

    def is_all(self) -> bool:
        return "ALL" in self.scope_types


@dataclass
class Principal:
    user: User
    primary_org: Optional[PrincipalOrg]
    roles: List[PrincipalRole]
    permission_codes: Set[str]
    data_scopes: Dict[str, PrincipalDataScope]

    @property
    def is_super_admin(self) -> bool:
        return any(role.code == "super_admin" for role in self.roles) or self.user.role == "admin"

    def has_permission(self, permission_code: str) -> bool:
        return self.is_super_admin or permission_code in self.permission_codes

    def has_any_permission(self, permission_codes: List[str]) -> bool:
        return self.is_super_admin or any(code in self.permission_codes for code in permission_codes)

    def scope_for(self, resource_type: str) -> Optional[PrincipalDataScope]:
        return self.data_scopes.get(resource_type)


def _build_primary_org(org: Optional[OrgUnit]) -> Optional[PrincipalOrg]:
    if not org:
        return None
    return PrincipalOrg(
        id=org.id,
        name=org.name,
        code=org.code,
        path=org.path,
        level=org.level,
    )


def build_principal(db: Session, user: User) -> Principal:
    primary_org = None
    if user.primary_org_id:
        primary_org = _build_primary_org(db.query(OrgUnit).filter(OrgUnit.id == user.primary_org_id).first())

    user_role_rows = (
        db.query(UserRole, Role)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == user.id, Role.status == "active")
        .all()
    )
    roles = [PrincipalRole(id=role.id, code=role.code, name=role.name) for _, role in user_role_rows]
    role_ids = [role.id for _, role in user_role_rows]

    permission_codes: Set[str] = set()
    data_scopes: Dict[str, PrincipalDataScope] = {}

    if role_ids:
        permission_rows = (
            db.query(RolePermission, Permission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(RolePermission.role_id.in_(role_ids))
            .all()
        )
        for _, permission in permission_rows:
            permission_codes.add(permission.code)

        scope_rows = db.query(RoleDataScope).filter(RoleDataScope.role_id.in_(role_ids)).all()
        scope_ids = [item.id for item in scope_rows]
        scope_org_rows = db.query(RoleScopeOrg).filter(RoleScopeOrg.role_data_scope_id.in_(scope_ids)).all() if scope_ids else []
        scope_org_map: Dict[int, Set[int]] = {}
        for item in scope_org_rows:
            scope_org_map.setdefault(item.role_data_scope_id, set()).add(item.org_unit_id)

        for item in scope_rows:
            scope = data_scopes.setdefault(
                item.resource_type,
                PrincipalDataScope(resource_type=item.resource_type),
            )
            scope.scope_types.add(item.scope_type)
            scope.org_ids.update(scope_org_map.get(item.id, set()))

    if user.role == "admin" and not roles:
        roles.append(PrincipalRole(id=0, code="super_admin", name="超级管理员"))

    if user.role == "admin" and not permission_codes:
        permission_codes = {item.code for item in db.query(Permission.code).all()}

    return Principal(
        user=user,
        primary_org=primary_org,
        roles=roles,
        permission_codes=permission_codes,
        data_scopes=data_scopes,
    )
