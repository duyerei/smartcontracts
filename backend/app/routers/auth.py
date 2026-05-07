import re
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_principal, hash_password, verify_password
from app.database import OrgUnit, Role, User, UserRole, get_db
from app.security.bootstrap import ensure_department_org, ensure_root_org, find_org_by_name
from app.security.permissions import require_permission
from app.security.principal import Principal, build_principal

router = APIRouter(prefix="/auth", tags=["认证"])

COMMON_WEAK_PASSWORDS = {
    "123456",
    "12345678",
    "123456789",
    "1234567890",
    "abcdefg",
    "abcdefgh",
    "abc12345",
    "abc123456",
    "password",
    "password123",
    "qwerty123",
    "admin123",
    "welcome123",
    "11111111",
    "00000000",
}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str = ""
    department: str = ""
    role: Literal["admin", "user"] = "user"
    primary_org_id: Optional[int] = None
    employee_no: Optional[str] = None
    position_name: Optional[str] = None
    role_ids: Optional[List[int]] = None


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[Literal["admin", "user"]] = None
    primary_org_id: Optional[int] = None
    employee_no: Optional[str] = None
    position_name: Optional[str] = None
    role_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    real_name: str
    department: str
    role: str
    primary_org_id: Optional[int] = None
    primary_org_name: Optional[str] = None
    employee_no: Optional[str] = None
    position_name: Optional[str] = None
    role_ids: List[int] = []
    roles: List[dict] = []
    permissions: List[str] = []
    data_scopes: Dict[str, dict] = {}
    is_active: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name}不能为空")
    return normalized


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_password_strength(password: str, username: Optional[str] = None, real_name: Optional[str] = None):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码至少8位")
    if any(char.isspace() for char in password):
        raise HTTPException(status_code=400, detail="密码不能包含空格")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="密码需包含大写字母")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="密码需包含小写字母")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="密码需包含数字")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(status_code=400, detail="密码需包含特殊字符")

    lowered = password.lower()
    if lowered in COMMON_WEAK_PASSWORDS or len(set(password)) == 1:
        raise HTTPException(status_code=400, detail="密码过于简单，请使用更复杂的密码")

    normalized_username = (username or "").strip().lower()
    if normalized_username and len(normalized_username) >= 3 and normalized_username in lowered:
        raise HTTPException(status_code=400, detail="密码不能包含用户名")

    normalized_real_name = (real_name or "").strip().lower()
    if normalized_real_name and len(normalized_real_name) >= 2 and normalized_real_name in lowered:
        raise HTTPException(status_code=400, detail="密码不能包含姓名")


def _serialize_data_scopes(principal: Principal):
    result = {}
    for resource_type, scope in principal.data_scopes.items():
        scope_types = sorted(scope.scope_types)
        result[resource_type] = {
            "scope_type": "ALL" if "ALL" in scope.scope_types else (scope_types[0] if scope_types else None),
            "scope_types": scope_types,
            "org_ids": sorted(scope.org_ids),
        }
    return result


def _user_dict(principal: Principal) -> dict:
    user = principal.user
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name or "",
        "department": user.department or "",
        "role": user.role,
        "primary_org_id": principal.primary_org.id if principal.primary_org else user.primary_org_id,
        "primary_org_name": principal.primary_org.name if principal.primary_org else None,
        "employee_no": user.employee_no,
        "position_name": user.position_name,
        "role_ids": [role.id for role in principal.roles],
        "roles": [{"id": role.id, "code": role.code, "name": role.name} for role in principal.roles],
        "permissions": sorted(principal.permission_codes),
        "data_scopes": _serialize_data_scopes(principal),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _resolve_primary_org_id(db: Session, primary_org_id: Optional[int], department: Optional[str]) -> Optional[int]:
    if primary_org_id:
        org = db.query(OrgUnit).filter(OrgUnit.id == primary_org_id).first()
        if not org:
            raise HTTPException(status_code=400, detail="所属组织不存在")
        return org.id

    if department and department.strip():
        org = find_org_by_name(db, department.strip())
        if not org:
            root = ensure_root_org(db)
            org = ensure_department_org(db, department.strip(), parent=root)
        return org.id if org else None

    return None


def _sync_user_roles(db: Session, user: User, role_ids: Optional[List[int]], legacy_role: Optional[str] = None):
    roles_by_id = {item.id: item for item in db.query(Role).filter(Role.status == "active").all()}

    if role_ids is None:
        mapped_code = "super_admin" if (legacy_role or user.role) == "admin" else "contract_operator"
        mapped_role = db.query(Role).filter(Role.code == mapped_code).first()
        target_role_ids = [mapped_role.id] if mapped_role else []
    else:
        invalid_ids = [role_id for role_id in role_ids if role_id not in roles_by_id]
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"角色不存在: {invalid_ids}")
        target_role_ids = list(dict.fromkeys(role_ids))

    existing = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    existing_role_ids = {item.role_id for item in existing}
    target_role_ids_set = set(target_role_ids)

    for item in existing:
        if item.role_id not in target_role_ids_set:
            db.delete(item)

    for role_id in target_role_ids:
        if role_id not in existing_role_ids:
            db.add(UserRole(user_id=user.id, role_id=role_id))

    target_roles = [roles_by_id[role_id] for role_id in target_role_ids if role_id in roles_by_id]
    user.role = "admin" if any(role.code in ("super_admin", "system_admin") for role in target_roles) else "user"


def _principal_for_user(db: Session, user: User) -> Principal:
    return build_principal(db, user)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")

    token = create_access_token(data={"sub": user.username})
    principal = _principal_for_user(db, user)
    return TokenResponse(access_token=token, user=_user_dict(principal))


@router.get("/me")
def get_me(principal: Principal = Depends(get_current_principal)):
    return _user_dict(principal)


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    current_user = principal.user
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    _validate_password_strength(req.new_password, current_user.username, current_user.real_name)
    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.get("/users", response_model=List[UserOut])
def list_users(
    principal: Principal = Depends(require_permission("user.view")),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserOut(**_user_dict(_principal_for_user(db, user))) for user in users]


@router.post("/users", response_model=UserOut)
def create_user(
    req: UserCreate,
    principal: Principal = Depends(require_permission("user.create")),
    db: Session = Depends(get_db),
):
    username = _normalize_required_text(req.username, "用户名")
    real_name = _normalize_required_text(req.real_name, "姓名")
    position_name = _normalize_required_text(req.position_name or "", "岗位")
    employee_no = _normalize_optional_text(req.employee_no)

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail=f"用户名 '{username}' 已存在")
    if req.primary_org_id is None:
        raise HTTPException(status_code=400, detail="主组织不能为空")
    _validate_password_strength(req.password, username, real_name)

    primary_org_id = _resolve_primary_org_id(db, req.primary_org_id, req.department)
    user = User(
        username=username,
        hashed_password=hash_password(req.password),
        real_name=real_name,
        department=(req.department or "").strip(),
        role=req.role,
        primary_org_id=primary_org_id,
        employee_no=employee_no,
        position_name=position_name,
        is_active=True,
    )
    if primary_org_id and not user.department:
        org = db.query(OrgUnit).filter(OrgUnit.id == primary_org_id).first()
        if org:
            user.department = org.name

    db.add(user)
    db.commit()
    db.refresh(user)

    _sync_user_roles(db, user, req.role_ids, legacy_role=req.role)
    db.commit()
    db.refresh(user)

    return UserOut(**_user_dict(_principal_for_user(db, user)))


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    req: UserUpdate,
    principal: Principal = Depends(require_permission("user.edit")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if req.real_name is not None:
        user.real_name = _normalize_required_text(req.real_name, "姓名")
    if req.department is not None:
        user.department = (req.department or "").strip()
    if req.primary_org_id is not None or req.department is not None:
        user.primary_org_id = _resolve_primary_org_id(db, req.primary_org_id, req.department or user.department)
        if user.primary_org_id and not user.department:
            org = db.query(OrgUnit).filter(OrgUnit.id == user.primary_org_id).first()
            if org:
                user.department = org.name
    if req.employee_no is not None:
        user.employee_no = _normalize_optional_text(req.employee_no)
    if req.position_name is not None:
        user.position_name = _normalize_required_text(req.position_name, "岗位")
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.password is not None:
        _validate_password_strength(req.password, user.username, req.real_name or user.real_name)
        user.hashed_password = hash_password(req.password)

    if req.role_ids is not None or req.role is not None:
        _sync_user_roles(db, user, req.role_ids, legacy_role=req.role)

    db.commit()
    db.refresh(user)
    return UserOut(**_user_dict(_principal_for_user(db, user)))


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    principal: Principal = Depends(require_permission("user.delete")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="不能删除默认管理员")

    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    return {"message": f"用户 '{user.username}' 已删除"}
