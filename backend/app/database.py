from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.config import config

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in config.DATABASE_URL else {},
    pool_pre_ping=True,
)

# SQLite WAL 模式：提升并发读写性能
if "sqlite" in config.DATABASE_URL:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
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
    original_filename = Column(String(500), nullable=True)  # 上传时的原始文件名
    summary = Column(Text, nullable=True)
    risk_level = Column(String(20), nullable=True)
    risk_analysis = Column(Text, nullable=True)
    extracted_data = Column(Text, nullable=True)
    # 新增：存储合同原始文本（JSON格式），避免重复调用OCR
    raw_text = Column(Text, nullable=True)
    
    # OA系统导入字段
    oa_id = Column(String(50), unique=True, index=True, nullable=True)  # OA系统ID（唯一标识）
    applicant = Column(String(50), nullable=True)  # 申请人
    position = Column(String(100), nullable=True)  # 岗位
    company = Column(String(200), nullable=True)  # 我方公司
    counterparty = Column(String(200), nullable=True)  # 对方单位
    counterparty_contact = Column(String(100), nullable=True)  # 对方联系人
    counterparty_address = Column(String(500), nullable=True)  # 对方地址
    payment_type = Column(String(50), nullable=True)  # 付款类型
    copies = Column(String(20), nullable=True)  # 合同份数
    raw_data = Column(Text, nullable=True)  # 原始OA数据(JSON)
    source = Column(String(20), default="upload")  # 来源: upload/oa_import
    
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Supplement(Base):
    __tablename__ = "supplements"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)  # 关联的主合同ID
    linked_contract_id = Column(Integer, nullable=True, index=True)  # 关联的补充协议合同ID
    title = Column(String(500))  # 补充协议名称
    signed_date = Column(DateTime, nullable=True)  # 签订时间
    amount = Column(Float, nullable=True)  # 补充协议金额
    file_path = Column(String(500), nullable=True)  # 文件路径（文件上传方式）
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)  # 关联的主合同ID
    payment_date = Column(DateTime, nullable=True)  # 付款时间/申请日期
    amount = Column(Float, nullable=True)  # 付款金额
    description = Column(String(500))  # 付款主题/付款事由
    file_path = Column(String(500))  # 文件路径
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）
    
    # 新增字段
    payment_theme = Column(String(200))  # 付款主题
    operator = Column(String(100))  # 经办人
    department = Column(String(200))  # 部门
    cost_center = Column(String(200))  # 归属成本中心
    project_name = Column(String(200))  # 项目名称
    contract_number = Column(String(100))  # 合同编号（冗余存储）
    application_number = Column(String(100))  # 申请单号
    payment_reason = Column(Text)  # 付款事由
    counterparty = Column(String(200))  # 对方单位
    
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ContractAttachment(Base):
    __tablename__ = "contract_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)  # 关联的合同ID
    file_name = Column(String(500))  # 文件名
    file_path = Column(String(500))  # 文件路径
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）
    file_url = Column(String(500), nullable=True)  # 原始URL
    attachment_type = Column(String(20), default="contract")  # contract/supplement/payment
    is_primary = Column(Boolean, default=False)  # 是否为主附件（默认解析的附件）
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
