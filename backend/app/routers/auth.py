import re
from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_principal, hash_password, verify_password
from app.database import DingTalkLoginCandidate, OrgUnit, Role, User, UserRole, get_db
from app.security.bootstrap import ensure_department_org, ensure_root_org, find_org_by_name, is_selectable_primary_org
from app.security.permissions import require_permission
from app.security.principal import Principal, build_principal
from app.services.dingtalk_oauth_service import DingTalkUserIdentity, dingtalk_oauth_service

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


class DingTalkCallbackRequest(BaseModel):
    auth_code: Optional[str] = None
    code: Optional[str] = None
    state: str


class DingTalkLoginUrlResponse(BaseModel):
    login_url: str


class DingTalkLoginCandidateOut(BaseModel):
    id: int
    dingtalk_user_id: Optional[str] = None
    dingtalk_union_id: Optional[str] = None
    dingtalk_open_id: Optional[str] = None
    dingtalk_corp_id: Optional[str] = None
    nick: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    employee_no: Optional[str] = None
    department_name: Optional[str] = None
    position_name: Optional[str] = None
    visitor: bool = False
    status: str
    bound_user_id: Optional[int] = None
    seen_count: int = 0
    last_seen_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str = ""
    department: str = ""
    role: Literal["admin", "user"] = "user"
    primary_org_id: Optional[int] = None
    employee_no: Optional[str] = None
    position_name: Optional[str] = None
    dingtalk_user_id: Optional[str] = None
    dingtalk_union_id: Optional[str] = None
    dingtalk_open_id: Optional[str] = None
    role_ids: Optional[List[int]] = None


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[Literal["admin", "user"]] = None
    primary_org_id: Optional[int] = None
    employee_no: Optional[str] = None
    position_name: Optional[str] = None
    dingtalk_user_id: Optional[str] = None
    dingtalk_union_id: Optional[str] = None
    dingtalk_open_id: Optional[str] = None
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
    dingtalk_user_id: Optional[str] = None
    dingtalk_union_id: Optional[str] = None
    dingtalk_open_id: Optional[str] = None
    dingtalk_bound: bool = False
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
        "dingtalk_user_id": user.dingtalk_user_id,
        "dingtalk_union_id": user.dingtalk_union_id,
        "dingtalk_open_id": user.dingtalk_open_id,
        "dingtalk_bound": bool(user.dingtalk_user_id or user.dingtalk_union_id or user.dingtalk_open_id),
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
        if not is_selectable_primary_org(db, org):
            raise HTTPException(status_code=400, detail="主组织必须选择到具体部门，不能选择根节点或父级组织")
        return org.id

    if department and department.strip():
        org = find_org_by_name(db, department.strip())
        if not org:
            root = ensure_root_org(db)
            org = ensure_department_org(db, department.strip(), parent=root)
        if not is_selectable_primary_org(db, org):
            raise HTTPException(status_code=400, detail="主组织必须选择到具体部门，不能选择根节点或父级组织")
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


def _ensure_unique_dingtalk_bindings(
    db: Session,
    *,
    user_id: Optional[int] = None,
    dingtalk_user_id: Optional[str] = None,
    dingtalk_union_id: Optional[str] = None,
    dingtalk_open_id: Optional[str] = None,
):
    checks = [
        ("dingtalk_user_id", dingtalk_user_id, "钉钉UserId"),
        ("dingtalk_union_id", dingtalk_union_id, "钉钉UnionId"),
        ("dingtalk_open_id", dingtalk_open_id, "钉钉OpenId"),
    ]
    for field_name, value, label in checks:
        if not value:
            continue
        query = db.query(User).filter(getattr(User, field_name) == value)
        if user_id:
            query = query.filter(User.id != user_id)
        if query.first():
            raise HTTPException(status_code=400, detail=f"{label}已绑定其他用户")


def _find_user_by_dingtalk_identity(db: Session, identity: DingTalkUserIdentity) -> Optional[User]:
    filters = []
    if identity.union_id:
        filters.append(User.dingtalk_union_id == identity.union_id)
    if identity.user_id:
        filters.append(User.dingtalk_user_id == identity.user_id)
    if identity.open_id:
        filters.append(User.dingtalk_open_id == identity.open_id)

    for condition in filters:
        user = db.query(User).filter(condition).first()
        if user:
            if identity.corp_id and not user.dingtalk_corp_id:
                user.dingtalk_corp_id = identity.corp_id
            if identity.union_id and not user.dingtalk_union_id:
                user.dingtalk_union_id = identity.union_id
            if identity.user_id and not user.dingtalk_user_id:
                user.dingtalk_user_id = identity.user_id
            if identity.open_id and not user.dingtalk_open_id:
                user.dingtalk_open_id = identity.open_id
            db.commit()
            db.refresh(user)
            return user
    return None


def _candidate_dict(candidate: DingTalkLoginCandidate) -> dict:
    return {
        "id": candidate.id,
        "dingtalk_user_id": candidate.dingtalk_user_id,
        "dingtalk_union_id": candidate.dingtalk_union_id,
        "dingtalk_open_id": candidate.dingtalk_open_id,
        "dingtalk_corp_id": candidate.dingtalk_corp_id,
        "nick": candidate.nick,
        "avatar_url": candidate.avatar_url,
        "email": candidate.email,
        "employee_no": candidate.employee_no,
        "department_name": candidate.department_name,
        "position_name": candidate.position_name,
        "visitor": bool(candidate.visitor),
        "status": candidate.status,
        "bound_user_id": candidate.bound_user_id,
        "seen_count": candidate.seen_count or 0,
        "last_seen_at": candidate.last_seen_at.isoformat() if candidate.last_seen_at else None,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
    }


def _find_dingtalk_candidate(db: Session, identity: DingTalkUserIdentity) -> Optional[DingTalkLoginCandidate]:
    checks = [
        ("dingtalk_union_id", identity.union_id),
        ("dingtalk_user_id", identity.user_id),
        ("dingtalk_open_id", identity.open_id),
    ]
    for field_name, value in checks:
        if not value:
            continue
        candidate = db.query(DingTalkLoginCandidate).filter(getattr(DingTalkLoginCandidate, field_name) == value).first()
        if candidate:
            return candidate
    return None


def _record_dingtalk_candidate(db: Session, identity: DingTalkUserIdentity):
    now = datetime.now()
    candidate = _find_dingtalk_candidate(db, identity)
    if not candidate:
        candidate = DingTalkLoginCandidate(created_at=now)
        db.add(candidate)

    candidate.dingtalk_user_id = identity.user_id or candidate.dingtalk_user_id
    candidate.dingtalk_union_id = identity.union_id or candidate.dingtalk_union_id
    candidate.dingtalk_open_id = identity.open_id or candidate.dingtalk_open_id
    candidate.dingtalk_corp_id = identity.corp_id or candidate.dingtalk_corp_id
    candidate.nick = identity.nick or candidate.nick
    candidate.avatar_url = identity.avatar_url or candidate.avatar_url
    candidate.email = identity.email or candidate.email
    candidate.employee_no = identity.employee_no or candidate.employee_no
    candidate.department_name = identity.department_name or candidate.department_name
    candidate.position_name = identity.position_name or candidate.position_name
    candidate.visitor = bool(identity.visitor)
    candidate.status = "pending"
    candidate.bound_user_id = None
    candidate.seen_count = (candidate.seen_count or 0) + 1
    candidate.last_seen_at = now
    candidate.updated_at = now
    db.commit()


def _mark_dingtalk_candidate_bound(db: Session, user: User):
    identity = DingTalkUserIdentity(
        user_id=user.dingtalk_user_id,
        union_id=user.dingtalk_union_id,
        open_id=user.dingtalk_open_id,
        corp_id=user.dingtalk_corp_id,
        nick=user.real_name,
        avatar_url=None,
        email=None,
        employee_no=user.employee_no,
        department_name=user.department,
        position_name=user.position_name,
        visitor=False,
    )
    candidate = _find_dingtalk_candidate(db, identity)
    if not candidate:
        return
    candidate.status = "bound"
    candidate.bound_user_id = user.id
    candidate.updated_at = datetime.now()
    db.commit()


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


@router.get("/dingtalk/login-url", response_model=DingTalkLoginUrlResponse)
def get_dingtalk_login_url():
    return DingTalkLoginUrlResponse(login_url=dingtalk_oauth_service.build_login_url())


@router.post("/dingtalk/callback", response_model=TokenResponse)
def dingtalk_login(req: DingTalkCallbackRequest, db: Session = Depends(get_db)):
    dingtalk_oauth_service.validate_state(req.state)
    identity = dingtalk_oauth_service.fetch_identity(req.auth_code or req.code or "")
    user = _find_user_by_dingtalk_identity(db, identity)
    if not user:
        _record_dingtalk_candidate(db, identity)
        raise HTTPException(status_code=403, detail="钉钉账号未授权登录，请联系管理员授权")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")

    token = create_access_token(data={"sub": user.username})
    principal = _principal_for_user(db, user)
    return TokenResponse(access_token=token, user=_user_dict(principal))


@router.get("/dingtalk/candidates", response_model=List[DingTalkLoginCandidateOut])
def list_dingtalk_candidates(
    principal: Principal = Depends(require_permission("user.edit")),
    db: Session = Depends(get_db),
):
    candidates = (
        db.query(DingTalkLoginCandidate)
        .filter(DingTalkLoginCandidate.status == "pending")
        .order_by(DingTalkLoginCandidate.last_seen_at.desc(), DingTalkLoginCandidate.created_at.desc())
        .all()
    )
    return [DingTalkLoginCandidateOut(**_candidate_dict(candidate)) for candidate in candidates]


@router.delete("/dingtalk/candidates/{candidate_id}")
def ignore_dingtalk_candidate(
    candidate_id: int,
    principal: Principal = Depends(require_permission("user.edit")),
    db: Session = Depends(get_db),
):
    candidate = db.query(DingTalkLoginCandidate).filter(DingTalkLoginCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="钉钉待绑定身份不存在")
    candidate.status = "ignored"
    candidate.updated_at = datetime.now()
    db.commit()
    return {"message": "已忽略该钉钉身份"}


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
    dingtalk_user_id = _normalize_optional_text(req.dingtalk_user_id)
    dingtalk_union_id = _normalize_optional_text(req.dingtalk_union_id)
    dingtalk_open_id = _normalize_optional_text(req.dingtalk_open_id)

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail=f"用户名 '{username}' 已存在")
    if req.primary_org_id is None:
        raise HTTPException(status_code=400, detail="主组织不能为空")
    _validate_password_strength(req.password, username, real_name)
    _ensure_unique_dingtalk_bindings(
        db,
        dingtalk_user_id=dingtalk_user_id,
        dingtalk_union_id=dingtalk_union_id,
        dingtalk_open_id=dingtalk_open_id,
    )

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
        dingtalk_user_id=dingtalk_user_id,
        dingtalk_union_id=dingtalk_union_id,
        dingtalk_open_id=dingtalk_open_id,
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
    _mark_dingtalk_candidate_bound(db, user)

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
    if req.dingtalk_user_id is not None:
        user.dingtalk_user_id = _normalize_optional_text(req.dingtalk_user_id)
    if req.dingtalk_union_id is not None:
        user.dingtalk_union_id = _normalize_optional_text(req.dingtalk_union_id)
    if req.dingtalk_open_id is not None:
        user.dingtalk_open_id = _normalize_optional_text(req.dingtalk_open_id)
    _ensure_unique_dingtalk_bindings(
        db,
        user_id=user.id,
        dingtalk_user_id=user.dingtalk_user_id,
        dingtalk_union_id=user.dingtalk_union_id,
        dingtalk_open_id=user.dingtalk_open_id,
    )
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.password is not None:
        _validate_password_strength(req.password, user.username, req.real_name or user.real_name)
        user.hashed_password = hash_password(req.password)

    if req.role_ids is not None or req.role is not None:
        _sync_user_roles(db, user, req.role_ids, legacy_role=req.role)

    db.commit()
    db.refresh(user)
    _mark_dingtalk_candidate_bound(db, user)
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
