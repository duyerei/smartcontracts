from datetime import datetime
from typing import Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.database import (
    Contract,
    OrgUnit,
    Partner,
    Payment,
    Permission,
    Role,
    RoleDataScope,
    RolePermission,
    RoleScopeOrg,
    User,
    UserRole,
)

ROOT_ORG_CODE = "ROOT"
ROOT_ORG_NAME = "组织架构"

RESOURCE_TYPES = ("contract", "payment", "partner")

DEFAULT_VALUE_ORG_UNITS = [
    {"code": "INCLUSIVE_FINANCE_BU", "name": "普惠金融事业部", "org_type": "business_unit", "sort": 10},
    {"code": "COMMUNITY_FINANCE_BU", "name": "社区金融事业部", "org_type": "business_unit", "sort": 20},
    {"code": "RISK_CONTROL_CENTER", "name": "风控中心", "org_type": "center", "sort": 30},
    {"code": "TECH_CENTER", "name": "科技中心", "org_type": "center", "sort": 40},
    {"code": "FINANCE_CENTER", "name": "财务中心", "org_type": "center", "sort": 50},
    {"code": "LEGAL_COMPLIANCE_CENTER", "name": "法务合规中心", "org_type": "center", "sort": 60},
    {"code": "HR_ADMIN_CENTER", "name": "人力行政中心", "org_type": "center", "sort": 70},
    {"code": "ASSISTANCE_OFFICE", "name": "助新办", "org_type": "office", "sort": 80},
    {"code": "SERVICE_GROUP", "name": "勤务组", "org_type": "group", "sort": 90},
    {"code": "PRESIDENT_OFFICE", "name": "总裁办", "org_type": "office", "sort": 100},
]
DEFAULT_VALUE_ORG_CODES = {item["code"] for item in DEFAULT_VALUE_ORG_UNITS}

SYSTEM_PERMISSIONS = [
    {"code": "dashboard.view", "name": "查看工作台", "module": "dashboard", "action": "view", "resource_type": "dashboard"},
    {"code": "agent.view", "name": "使用AI助手", "module": "agent", "action": "view", "resource_type": "agent"},
    {"code": "settings.view", "name": "查看系统设置", "module": "settings", "action": "view", "resource_type": "settings"},
    {"code": "contract.view", "name": "查看合同", "module": "contract", "action": "view", "resource_type": "contract"},
    {"code": "contract.create", "name": "创建合同", "module": "contract", "action": "create", "resource_type": "contract"},
    {"code": "contract.edit", "name": "编辑合同", "module": "contract", "action": "edit", "resource_type": "contract"},
    {"code": "contract.delete", "name": "删除合同", "module": "contract", "action": "delete", "resource_type": "contract"},
    {"code": "contract.download", "name": "下载合同", "module": "contract", "action": "download", "resource_type": "contract"},
    {"code": "contract.reparse", "name": "重解析合同", "module": "contract", "action": "reparse", "resource_type": "contract"},
    {"code": "contract.import_oa", "name": "OA导入合同", "module": "contract", "action": "import_oa", "resource_type": "contract"},
    {"code": "supplement.view", "name": "查看补充协议", "module": "supplement", "action": "view", "resource_type": "contract"},
    {"code": "supplement.create", "name": "创建补充协议", "module": "supplement", "action": "create", "resource_type": "contract"},
    {"code": "supplement.edit", "name": "编辑补充协议", "module": "supplement", "action": "edit", "resource_type": "contract"},
    {"code": "supplement.delete", "name": "删除补充协议", "module": "supplement", "action": "delete", "resource_type": "contract"},
    {"code": "payment.view", "name": "查看付款", "module": "payment", "action": "view", "resource_type": "payment"},
    {"code": "payment.create", "name": "创建付款", "module": "payment", "action": "create", "resource_type": "payment"},
    {"code": "payment.edit", "name": "编辑付款", "module": "payment", "action": "edit", "resource_type": "payment"},
    {"code": "payment.delete", "name": "删除付款", "module": "payment", "action": "delete", "resource_type": "payment"},
    {"code": "payment.download", "name": "下载付款附件", "module": "payment", "action": "download", "resource_type": "payment"},
    {"code": "payment.import_pdf", "name": "导入付款PDF", "module": "payment", "action": "import_pdf", "resource_type": "payment"},
    {"code": "partner.view", "name": "查看合作伙伴", "module": "partner", "action": "view", "resource_type": "partner"},
    {"code": "partner.create", "name": "创建合作伙伴", "module": "partner", "action": "create", "resource_type": "partner"},
    {"code": "partner.edit", "name": "编辑合作伙伴", "module": "partner", "action": "edit", "resource_type": "partner"},
    {"code": "partner.delete", "name": "删除合作伙伴", "module": "partner", "action": "delete", "resource_type": "partner"},
    {"code": "partner.upload_attachment", "name": "上传合作伙伴附件", "module": "partner", "action": "upload_attachment", "resource_type": "partner"},
    {"code": "user.view", "name": "查看用户", "module": "user", "action": "view", "resource_type": "system"},
    {"code": "user.create", "name": "创建用户", "module": "user", "action": "create", "resource_type": "system"},
    {"code": "user.edit", "name": "编辑用户", "module": "user", "action": "edit", "resource_type": "system"},
    {"code": "user.delete", "name": "删除用户", "module": "user", "action": "delete", "resource_type": "system"},
    {"code": "org.view", "name": "查看组织", "module": "org", "action": "view", "resource_type": "system"},
    {"code": "org.create", "name": "创建组织", "module": "org", "action": "create", "resource_type": "system"},
    {"code": "org.edit", "name": "编辑组织", "module": "org", "action": "edit", "resource_type": "system"},
    {"code": "org.delete", "name": "删除组织", "module": "org", "action": "delete", "resource_type": "system"},
    {"code": "role.view", "name": "查看角色", "module": "role", "action": "view", "resource_type": "system"},
    {"code": "role.create", "name": "创建角色", "module": "role", "action": "create", "resource_type": "system"},
    {"code": "role.edit", "name": "编辑角色", "module": "role", "action": "edit", "resource_type": "system"},
    {"code": "role.delete", "name": "删除角色", "module": "role", "action": "delete", "resource_type": "system"},
    {"code": "role.assign_permission", "name": "分配角色权限", "module": "role", "action": "assign_permission", "resource_type": "system"},
]

SYSTEM_ROLES = [
    {"code": "super_admin", "name": "超级管理员", "description": "拥有全部功能权限和全部数据权限", "is_system": True},
    {"code": "system_admin", "name": "系统管理员", "description": "负责组织、角色、用户与系统配置", "is_system": True},
    {"code": "dept_manager", "name": "部门负责人", "description": "负责本组织及下级组织的业务数据", "is_system": True},
    {"code": "contract_operator", "name": "合同经办人", "description": "负责本组织合同与关联业务办理", "is_system": True},
    {"code": "finance_operator", "name": "财务经办人", "description": "负责本组织付款业务办理", "is_system": True},
    {"code": "readonly_auditor", "name": "只读审计员", "description": "只读查看审计数据", "is_system": True},
]

ROLE_PERMISSION_CODES = {
    "super_admin": "__ALL__",
    "system_admin": [
        "dashboard.view",
        "settings.view",
        "agent.view",
        "user.view",
        "user.create",
        "user.edit",
        "user.delete",
        "org.view",
        "org.create",
        "org.edit",
        "org.delete",
        "role.view",
        "role.create",
        "role.edit",
        "role.delete",
        "role.assign_permission",
        "contract.view",
        "contract.download",
        "payment.view",
        "partner.view",
    ],
    "dept_manager": [
        "dashboard.view",
        "agent.view",
        "contract.view",
        "contract.create",
        "contract.edit",
        "contract.download",
        "contract.reparse",
        "supplement.view",
        "supplement.create",
        "supplement.edit",
        "payment.view",
        "payment.create",
        "payment.edit",
        "payment.download",
        "payment.import_pdf",
        "partner.view",
        "partner.create",
        "partner.edit",
        "partner.upload_attachment",
    ],
    "contract_operator": [
        "dashboard.view",
        "agent.view",
        "contract.view",
        "contract.create",
        "contract.edit",
        "contract.download",
        "contract.reparse",
        "supplement.view",
        "supplement.create",
        "supplement.edit",
        "payment.view",
        "partner.view",
    ],
    "finance_operator": [
        "dashboard.view",
        "payment.view",
        "payment.create",
        "payment.edit",
        "payment.download",
        "payment.import_pdf",
        "contract.view",
        "contract.download",
        "partner.view",
    ],
    "readonly_auditor": [
        "dashboard.view",
        "contract.view",
        "contract.download",
        "payment.view",
        "payment.download",
        "partner.view",
        "org.view",
        "role.view",
        "user.view",
    ],
}

ROLE_DATA_SCOPES = {
    "super_admin": {resource_type: "ALL" for resource_type in RESOURCE_TYPES},
    "system_admin": {resource_type: "ALL" for resource_type in RESOURCE_TYPES},
    "dept_manager": {resource_type: "ORG_AND_CHILDREN" for resource_type in RESOURCE_TYPES},
    "contract_operator": {"contract": "ORG_ONLY", "payment": "ORG_ONLY", "partner": "ORG_ONLY"},
    "finance_operator": {"contract": "ORG_ONLY", "payment": "ORG_ONLY", "partner": "ORG_ONLY"},
    "readonly_auditor": {resource_type: "ALL" for resource_type in RESOURCE_TYPES},
}


def _now():
    return datetime.now()


def _next_org_code(db: Session) -> str:
    count = db.query(OrgUnit).count() + 1
    return f"ORG_{count:04d}"


def _rebuild_org_subtree_paths(db: Session, org: OrgUnit):
    children = db.query(OrgUnit).filter(OrgUnit.parent_id == org.id).all()
    for child in children:
        child.path = f"{org.path}/{child.code}"
        child.level = org.level + 1
        _rebuild_org_subtree_paths(db, child)


def ensure_root_org(db: Session) -> OrgUnit:
    root = db.query(OrgUnit).filter(OrgUnit.code == ROOT_ORG_CODE).first()
    if root:
        return root

    root = OrgUnit(
        code=ROOT_ORG_CODE,
        name=ROOT_ORG_NAME,
        parent_id=None,
        path=ROOT_ORG_CODE,
        level=1,
        org_type="root",
        status="active",
        sort=0,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(root)
    db.commit()
    db.refresh(root)
    return root


def find_org_by_name(db: Session, name: str) -> Optional[OrgUnit]:
    normalized = (name or "").strip()
    if not normalized:
        return None
    return db.query(OrgUnit).filter(OrgUnit.name == normalized).order_by(OrgUnit.level.asc(), OrgUnit.id.asc()).first()


def find_org_by_id(db: Session, org_id: Optional[int]) -> Optional[OrgUnit]:
    if not org_id:
        return None
    return db.query(OrgUnit).filter(OrgUnit.id == org_id).first()


def is_selectable_primary_org(db: Session, org: Optional[OrgUnit]) -> bool:
    """用户主组织必须落到启用的具体组织，不能停留在根节点或父级节点。"""
    if not org or org.status != "active" or org.org_type == "root":
        return False

    has_active_child = (
        db.query(OrgUnit.id)
        .filter(OrgUnit.parent_id == org.id, OrgUnit.status == "active")
        .first()
        is not None
    )
    return not has_active_child


def first_selectable_primary_org(db: Session) -> Optional[OrgUnit]:
    active_orgs = (
        db.query(OrgUnit)
        .filter(OrgUnit.status == "active", OrgUnit.org_type != "root")
        .order_by(OrgUnit.level.desc(), OrgUnit.sort.asc(), OrgUnit.id.asc())
        .all()
    )
    for org in active_orgs:
        if is_selectable_primary_org(db, org):
            return org
    return None


def resolve_org_unit(
    db: Session,
    *,
    org_id: Optional[int] = None,
    name: Optional[str] = None,
    create_missing: bool = False,
) -> Optional[OrgUnit]:
    org = find_org_by_id(db, org_id)
    if org:
        return org

    normalized = (name or "").strip()
    if not normalized:
        return None

    org = find_org_by_name(db, normalized)
    if org or not create_missing:
        return org

    root = ensure_root_org(db)
    return ensure_department_org(db, normalized, parent=root)


def sync_contract_department_with_org(
    db: Session,
    contract: Contract,
    *,
    preferred_org_id: Optional[int] = None,
    preferred_department: Optional[str] = None,
    create_missing_org: bool = False,
) -> Optional[OrgUnit]:
    target_org = resolve_org_unit(
        db,
        org_id=preferred_org_id,
        name=preferred_department,
        create_missing=create_missing_org,
    )

    if not target_org and contract.owner_org_id:
        target_org = find_org_by_id(db, contract.owner_org_id)
    if not target_org and contract.department:
        target_org = resolve_org_unit(db, name=contract.department, create_missing=create_missing_org)

    if target_org:
        contract.owner_org_id = target_org.id
        contract.department = target_org.name
    elif preferred_department is not None:
        contract.department = (preferred_department or "").strip()

    return target_org


def ensure_department_org(db: Session, name: str, parent: Optional[OrgUnit] = None) -> Optional[OrgUnit]:
    normalized = (name or "").strip()
    if not normalized:
        return None

    existing = find_org_by_name(db, normalized)
    if existing:
        return existing

    if parent is None:
        parent = ensure_root_org(db)

    code = _next_org_code(db)
    org = OrgUnit(
        code=code,
        name=normalized,
        parent_id=parent.id,
        path=f"{parent.path}/{code}",
        level=parent.level + 1,
        org_type="department",
        status="active",
        sort=0,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _seed_default_value_org_units(db: Session, root: OrgUnit):
    changed = False
    for definition in DEFAULT_VALUE_ORG_UNITS:
        org = db.query(OrgUnit).filter(OrgUnit.code == definition["code"]).first()
        if not org:
            org = find_org_by_name(db, definition["name"])

        if not org:
            org = OrgUnit(
                code=definition["code"],
                name=definition["name"],
                parent_id=root.id,
                path=f"{root.path}/{definition['code']}",
                level=root.level + 1,
                org_type=definition["org_type"],
                status="active",
                sort=definition["sort"],
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(org)
            changed = True
            continue

        expected_path = f"{root.path}/{definition['code']}"
        org_changed = False
        updates = {
            "code": definition["code"],
            "name": definition["name"],
            "parent_id": root.id,
            "path": expected_path,
            "level": root.level + 1,
            "org_type": definition["org_type"],
            "status": "active",
            "sort": definition["sort"],
        }
        for field_name, value in updates.items():
            if getattr(org, field_name) != value:
                setattr(org, field_name, value)
                org_changed = True
                changed = True
        if org_changed:
            org.updated_at = _now()
            _rebuild_org_subtree_paths(db, org)

    if changed:
        db.commit()


def _archive_non_value_org_units(db: Session, root: OrgUnit):
    changed = False
    orgs = db.query(OrgUnit).filter(OrgUnit.id != root.id).all()
    for org in orgs:
        if org.code in DEFAULT_VALUE_ORG_CODES:
            continue
        if org.status != "inactive":
            org.status = "inactive"
            org.updated_at = _now()
            changed = True
    if changed:
        db.commit()


def _iter_legacy_departments(db: Session) -> Iterable[str]:
    seen = set()

    user_departments = db.query(User.department).filter(User.department != None, User.department != "").all()
    contract_departments = db.query(Contract.department).filter(Contract.department != None, Contract.department != "").all()
    payment_departments = db.query(Payment.department).filter(Payment.department != None, Payment.department != "").all()

    for rows in (user_departments, contract_departments, payment_departments):
        for item in rows:
            value = (item[0] or "").strip()
            if value and value not in seen:
                seen.add(value)
                yield value


def _seed_permissions(db: Session):
    existing = {item.code: item for item in db.query(Permission).all()}
    created = False
    for definition in SYSTEM_PERMISSIONS:
        if definition["code"] in existing:
            continue
        db.add(Permission(created_at=_now(), **definition))
        created = True
    if created:
        db.commit()


def _seed_roles(db: Session):
    existing = {item.code: item for item in db.query(Role).all()}
    created = False
    for definition in SYSTEM_ROLES:
        if definition["code"] in existing:
            continue
        db.add(Role(created_at=_now(), updated_at=_now(), status="active", **definition))
        created = True
    if created:
        db.commit()


def _seed_role_permissions(db: Session):
    permissions = {item.code: item for item in db.query(Permission).all()}
    roles = {item.code: item for item in db.query(Role).all()}
    existing_pairs = {(item.role_id, item.permission_id) for item in db.query(RolePermission).all()}
    created = False

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role = roles.get(role_code)
        if not role:
            continue
        target_codes = permissions.keys() if permission_codes == "__ALL__" else permission_codes
        for permission_code in target_codes:
            permission = permissions.get(permission_code)
            if not permission:
                continue
            pair = (role.id, permission.id)
            if pair in existing_pairs:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=permission.id, created_at=_now()))
            existing_pairs.add(pair)
            created = True

    if created:
        db.commit()


def _seed_role_data_scopes(db: Session):
    roles = {item.code: item for item in db.query(Role).all()}
    existing = {(item.role_id, item.resource_type): item for item in db.query(RoleDataScope).all()}
    created = False

    for role_code, scopes in ROLE_DATA_SCOPES.items():
        role = roles.get(role_code)
        if not role:
            continue
        for resource_type, scope_type in scopes.items():
            key = (role.id, resource_type)
            if key in existing:
                scope = existing[key]
                if scope.scope_type != scope_type:
                    scope.scope_type = scope_type
                    created = True
                continue
            db.add(
                RoleDataScope(
                    role_id=role.id,
                    resource_type=resource_type,
                    scope_type=scope_type,
                    created_at=_now(),
                )
            )
            created = True

    if created:
        db.commit()


def _assign_default_roles(db: Session):
    roles = {item.code: item for item in db.query(Role).all()}
    existing_user_ids = {item.user_id for item in db.query(UserRole.user_id).distinct().all()}
    created = False

    for user in db.query(User).all():
        if user.id in existing_user_ids:
            continue
        role_code = "super_admin" if user.role == "admin" else "contract_operator"
        role = roles.get(role_code)
        if not role:
            continue
        db.add(UserRole(user_id=user.id, role_id=role.id, created_at=_now()))
        created = True

    if created:
        db.commit()


def _backfill_user_orgs(db: Session, root: OrgUnit):
    changed = False
    fallback_org = first_selectable_primary_org(db) or root

    for user in db.query(User).all():
        if user.primary_org_id:
            current_org = find_org_by_id(db, user.primary_org_id)
            if is_selectable_primary_org(db, current_org):
                continue

        target_org = None
        if user.department:
            target_org = find_org_by_name(db, user.department)
            if not is_selectable_primary_org(db, target_org):
                target_org = None

        if not target_org:
            target_org = fallback_org

        if target_org:
            user.primary_org_id = target_org.id
            if not user.department or user.department == root.name:
                user.department = target_org.name
            changed = True

    if changed:
        db.commit()


def _backfill_contract_ownership(db: Session, root: OrgUnit):
    admin_user = db.query(User).filter(User.username == "admin").first()
    fallback_user_id = admin_user.id if admin_user else None
    fallback_org_id = admin_user.primary_org_id if admin_user and admin_user.primary_org_id else root.id
    changed = False

    for contract in db.query(Contract).all():
        target_org = find_org_by_name(db, contract.department) if contract.department else None
        if not contract.owner_org_id:
            contract.owner_org_id = target_org.id if target_org else fallback_org_id
            changed = True
        if not contract.owner_user_id and fallback_user_id:
            contract.owner_user_id = fallback_user_id
            changed = True
        if not contract.created_by and fallback_user_id:
            contract.created_by = fallback_user_id
            changed = True

    if changed:
        db.commit()


def _sync_contract_departments_with_owner_org(db: Session):
    changed = False

    for contract in db.query(Contract).all():
        target_org = find_org_by_id(db, contract.owner_org_id)
        if not target_org:
            continue
        if contract.department != target_org.name:
            contract.department = target_org.name
            changed = True

    if changed:
        db.commit()


def _backfill_payment_ownership(db: Session, root: OrgUnit):
    admin_user = db.query(User).filter(User.username == "admin").first()
    fallback_user_id = admin_user.id if admin_user else None
    fallback_org_id = admin_user.primary_org_id if admin_user and admin_user.primary_org_id else root.id
    contracts = {item.id: item for item in db.query(Contract).all()}
    changed = False

    for payment in db.query(Payment).all():
        contract = contracts.get(payment.contract_id) if payment.contract_id else None
        target_org = None
        if payment.department:
            target_org = find_org_by_name(db, payment.department)
        if not target_org and contract and contract.owner_org_id:
            target_org = db.query(OrgUnit).filter(OrgUnit.id == contract.owner_org_id).first()

        if not payment.owner_org_id:
            payment.owner_org_id = target_org.id if target_org else fallback_org_id
            changed = True
        if not payment.owner_user_id:
            payment.owner_user_id = contract.owner_user_id if contract and contract.owner_user_id else fallback_user_id
            changed = True
        if not payment.created_by:
            payment.created_by = contract.created_by if contract and contract.created_by else fallback_user_id
            changed = True

    if changed:
        db.commit()


def _backfill_partner_ownership(db: Session, root: OrgUnit):
    admin_user = db.query(User).filter(User.username == "admin").first()
    fallback_user_id = admin_user.id if admin_user else None
    fallback_org_id = admin_user.primary_org_id if admin_user and admin_user.primary_org_id else root.id
    changed = False

    for partner in db.query(Partner).all():
        linked_contract = (
            db.query(Contract)
            .filter(Contract.parties.contains(partner.name), Contract.is_deleted == False)
            .order_by(Contract.updated_at.desc())
            .first()
        )
        if not partner.owner_org_id:
            if linked_contract and linked_contract.owner_org_id:
                partner.owner_org_id = linked_contract.owner_org_id
            else:
                partner.owner_org_id = fallback_org_id
            changed = True
        if not partner.owner_user_id:
            partner.owner_user_id = linked_contract.owner_user_id if linked_contract and linked_contract.owner_user_id else fallback_user_id
            changed = True
        if not partner.created_by:
            partner.created_by = linked_contract.created_by if linked_contract and linked_contract.created_by else fallback_user_id
            changed = True

    if changed:
        db.commit()


def bootstrap_security_data(db: Session):
    root = ensure_root_org(db)
    _seed_default_value_org_units(db, root)
    _archive_non_value_org_units(db, root)

    _seed_permissions(db)
    _seed_roles(db)
    _seed_role_permissions(db)
    _seed_role_data_scopes(db)
    _backfill_user_orgs(db, root)
    _assign_default_roles(db)
    _backfill_contract_ownership(db, root)
    _sync_contract_departments_with_owner_org(db)
    _backfill_payment_ownership(db, root)
    _backfill_partner_ownership(db, root)
