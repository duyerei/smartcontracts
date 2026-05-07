from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import config
from app.database import User, get_db
from app.security.principal import Principal, build_principal

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=config.JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def _decode_user_from_token(token: str, db: Session) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_current_principal(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    user = _decode_user_from_token(token, db)
    return build_principal(db, user)


def get_current_user(
    principal: Principal = Depends(get_current_principal),
) -> User:
    return principal.user


def verify_token(token: str, db: Session) -> Optional[User]:
    try:
        user = _decode_user_from_token(token, db)
        return user if user.is_active else None
    except HTTPException:
        return None
    except JWTError as exc:
        print(f"[verify_token] JWTError: {exc}, token[:20]={token[:20]}...")
        return None


def require_admin(
    principal: Principal = Depends(get_current_principal),
) -> User:
    if principal.is_super_admin or principal.has_permission("user.view"):
        return principal.user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


def ensure_default_admin(db: Session):
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        return

    import secrets
    from pathlib import Path

    random_password = secrets.token_urlsafe(16)
    admin = User(
        username="admin",
        hashed_password=hash_password(random_password),
        real_name="系统管理员",
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()

    secure_dir = Path("./secure")
    secure_dir.mkdir(exist_ok=True)
    password_file = secure_dir / "admin_password.txt"

    with open(password_file, "w", encoding="utf-8") as file_obj:
        file_obj.write("管理员账号: admin\n")
        file_obj.write(f"初始密码: {random_password}\n")
        file_obj.write(f"创建时间: {datetime.now().isoformat()}\n")
        file_obj.write("\n重要提示：\n")
        file_obj.write("1. 请立即登录并修改密码\n")
        file_obj.write("2. 修改密码后请删除此文件\n")
        file_obj.write("3. 此文件包含敏感信息，请妥善保管\n")

    print("✅ 管理员账号已创建")
    print(f"📁 初始密码已保存到: {password_file.absolute()}")
    print("⚠️  请立即登录并修改密码！")
