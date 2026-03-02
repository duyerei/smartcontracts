from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import config
from app.database import User, get_db

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


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
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


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def ensure_default_admin(db: Session):
    """启动时确保存在默认管理员账号。"""
    import secrets
    from pathlib import Path
    
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        # 生成强随机密码
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
        
        # 将密码保存到安全位置
        secure_dir = Path("./secure")
        secure_dir.mkdir(exist_ok=True)
        password_file = secure_dir / "admin_password.txt"
        
        with open(password_file, "w") as f:
            f.write(f"管理员账号: admin\n")
            f.write(f"初始密码: {random_password}\n")
            f.write(f"创建时间: {datetime.now().isoformat()}\n")
            f.write(f"\n重要提示：\n")
            f.write(f"1. 请立即登录并修改密码\n")
            f.write(f"2. 修改密码后请删除此文件\n")
            f.write(f"3. 此文件包含敏感信息，请妥善保管\n")
        
        print(f"✅ 管理员账号已创建")
        print(f"📁 初始密码已保存到: {password_file.absolute()}")
        print(f"⚠️  请立即登录并修改密码！")
