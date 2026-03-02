from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.config import config

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in config.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    contract_number = Column(String(100), unique=True, index=True)
    title = Column(String(500))
    contract_type = Column(String(50), index=True)
    department = Column(String(50), index=True)
    status = Column(String(20), default="待审核", index=True)
    parties = Column(Text)
    amount = Column(Float, nullable=True)
    currency = Column(String(10), default="CNY")
    signed_date = Column(DateTime, nullable=True)  # 新增：合同签订时间
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    file_path = Column(String(500))
    summary = Column(Text, nullable=True)
    risk_level = Column(String(20), nullable=True)
    risk_analysis = Column(Text, nullable=True)
    extracted_data = Column(Text, nullable=True)
    # 新增：存储合同原始文本（JSON格式），避免重复调用OCR
    raw_text = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Supplement(Base):
    __tablename__ = "supplements"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)  # 关联的主合同ID
    title = Column(String(500))  # 补充协议名称
    signed_date = Column(DateTime, nullable=True)  # 签订时间
    amount = Column(Float, nullable=True)  # 补充协议金额
    file_path = Column(String(500))  # 文件路径
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)  # 关联的主合同ID
    payment_date = Column(DateTime, nullable=True)  # 付款时间
    amount = Column(Float, nullable=True)  # 付款金额
    description = Column(String(500))  # 付款资料描述
    file_path = Column(String(500))  # 文件路径
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    real_name = Column(String(100), default="")
    department = Column(String(50), default="")
    role = Column(String(20), default="user", index=True)  # admin / user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
