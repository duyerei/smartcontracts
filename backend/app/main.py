from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import contracts_router, agent_router, auth_router, supplements_router, payments_router, import_contracts_router, partners_router
from app.config import config
from app.database import init_db, SessionLocal
from app.auth import ensure_default_admin
import os

config.init_storage()

# 初始化速率限制器
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="AI智能合同管理系统API",
    description="提供合同上传、解析、管理等功能",
    version="1.0.0"
)

# 添加速率限制器到app状态
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS配置 - 从环境变量读取允许的源
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # 仅允许配置的源
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # 明确指定方法
    allow_headers=["Content-Type", "Authorization"],  # 明确指定头
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(contracts_router, prefix="/api/v1")
app.include_router(supplements_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(import_contracts_router, prefix="/api/v1")
app.include_router(partners_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "AI智能合同管理系统API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
