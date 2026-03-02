from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Literal

from app.database import User, get_db
from app.auth import (
    verify_password, hash_password, create_access_token,
    get_current_user, require_admin,
)

router = APIRouter(prefix="/auth", tags=["认证"])


# ---------- Schemas ----------

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


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[Literal["admin", "user"]] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    real_name: str
    department: str
    role: str
    is_active: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- 辅助 ----------

def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "real_name": u.real_name or "",
        "department": u.department or "",
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ---------- 登录 ----------

@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")

    token = create_access_token(data={"sub": user.username})
    return TokenResponse(access_token=token, user=_user_dict(user))


# ---------- 当前用户 ----------

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)


# ---------- 修改密码 ----------

@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少6位")
    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}


# ---------- 管理员：用户列表 ----------

@router.get("/users", response_model=List[UserOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserOut(**_user_dict(u)) for u in users]


# ---------- 管理员：创建用户 ----------

@router.post("/users", response_model=UserOut)
def create_user(req: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail=f"用户名 '{req.username}' 已存在")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        real_name=req.real_name,
        department=req.department,
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(**_user_dict(user))


# ---------- 管理员：更新用户 ----------

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, req: UserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.real_name is not None:
        user.real_name = req.real_name
    if req.department is not None:
        user.department = req.department
    if req.role is not None:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.password is not None:
        if len(req.password) < 6:
            raise HTTPException(status_code=400, detail="密码至少6位")
        user.hashed_password = hash_password(req.password)
    db.commit()
    db.refresh(user)
    return UserOut(**_user_dict(user))


# ---------- 管理员：删除用户 ----------

@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="不能删除默认管理员")
    db.delete(user)
    db.commit()
    return {"message": f"用户 '{user.username}' 已删除"}
