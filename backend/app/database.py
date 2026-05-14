from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.db_config import build_engine_options, is_sqlite, normalize_database_url

DATABASE_URL = normalize_database_url(config.DATABASE_URL)
engine = create_engine(DATABASE_URL, **build_engine_options(DATABASE_URL))

if is_sqlite(DATABASE_URL):

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
    signed_date = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    file_path = Column(String(500))
    original_filename = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    risk_level = Column(String(20), nullable=True)
    risk_analysis = Column(Text, nullable=True)
    extracted_data = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)

    oa_id = Column(String(50), unique=True, index=True, nullable=True)
    applicant = Column(String(50), nullable=True)
    position = Column(String(100), nullable=True)
    company = Column(String(200), nullable=True)
    counterparty = Column(String(200), nullable=True)
    counterparty_contact = Column(String(100), nullable=True)
    counterparty_address = Column(String(500), nullable=True)
    payment_type = Column(String(50), nullable=True)
    copies = Column(String(20), nullable=True)
    raw_data = Column(Text, nullable=True)
    source = Column(String(20), default="upload")

    owner_org_id = Column(Integer, index=True, nullable=True)
    owner_user_id = Column(Integer, index=True, nullable=True)
    created_by = Column(Integer, index=True, nullable=True)

    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Supplement(Base):
    __tablename__ = "supplements"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)
    linked_contract_id = Column(Integer, nullable=True, index=True)
    title = Column(String(500))
    signed_date = Column(DateTime, nullable=True)
    amount = Column(Float, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)
    payment_date = Column(DateTime, nullable=True)
    amount = Column(Float, nullable=True)
    description = Column(String(500))
    file_path = Column(String(500))
    file_size = Column(Integer, nullable=True)

    payment_theme = Column(String(200))
    operator = Column(String(100))
    department = Column(String(200))
    cost_center = Column(String(200))
    project_name = Column(String(200))
    contract_number = Column(String(100))
    application_number = Column(String(100))
    payment_reason = Column(Text)
    counterparty = Column(String(200))

    owner_org_id = Column(Integer, index=True, nullable=True)
    owner_user_id = Column(Integer, index=True, nullable=True)
    created_by = Column(Integer, index=True, nullable=True)

    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    contact_name = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    bank_name = Column(String(200), nullable=True)
    bank_account = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    owner_org_id = Column(Integer, index=True, nullable=True)
    owner_user_id = Column(Integer, index=True, nullable=True)
    created_by = Column(Integer, index=True, nullable=True)

    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class PartnerAttachment(Base):
    __tablename__ = "partner_attachments"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, index=True)
    file_name = Column(String(500))
    file_path = Column(String(500))
    file_size = Column(Integer, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


class ContractAttachment(Base):
    __tablename__ = "contract_attachments"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, index=True)
    file_name = Column(String(500))
    file_path = Column(String(500))
    file_size = Column(Integer, nullable=True)
    file_url = Column(String(500), nullable=True)
    attachment_type = Column(String(20), default="contract")
    is_primary = Column(Boolean, default=False)
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
    role = Column(String(20), default="user", index=True)
    primary_org_id = Column(Integer, index=True, nullable=True)
    employee_no = Column(String(50), nullable=True)
    position_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class OrgUnit(Base):
    __tablename__ = "org_units"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), index=True, nullable=False)
    parent_id = Column(Integer, index=True, nullable=True)
    path = Column(String(500), index=True, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    org_type = Column(String(30), default="department", nullable=False)
    manager_user_id = Column(Integer, nullable=True)
    status = Column(String(20), default="active", nullable=False)
    sort = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    module = Column(String(50), index=True, nullable=False)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    role_id = Column(Integer, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, index=True, nullable=False)
    permission_id = Column(Integer, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class RoleDataScope(Base):
    __tablename__ = "role_data_scopes"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, index=True, nullable=False)
    resource_type = Column(String(50), index=True, nullable=False)
    scope_type = Column(String(30), nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class RoleScopeOrg(Base):
    __tablename__ = "role_scope_orgs"

    id = Column(Integer, primary_key=True, index=True)
    role_data_scope_id = Column(Integer, index=True, nullable=False)
    org_unit_id = Column(Integer, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


_SQLITE_COMPAT_COLUMNS = {
    "users": {
        "primary_org_id": "INTEGER",
        "employee_no": "VARCHAR(50)",
        "position_name": "VARCHAR(100)",
    },
    "contracts": {
        "owner_org_id": "INTEGER",
        "owner_user_id": "INTEGER",
        "created_by": "INTEGER",
    },
    "payments": {
        "owner_org_id": "INTEGER",
        "owner_user_id": "INTEGER",
        "created_by": "INTEGER",
    },
    "partners": {
        "owner_org_id": "INTEGER",
        "owner_user_id": "INTEGER",
        "created_by": "INTEGER",
    },
}

_SQLITE_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_users_primary_org_id ON users(primary_org_id)",
    "CREATE INDEX IF NOT EXISTS idx_contracts_owner_org_id ON contracts(owner_org_id)",
    "CREATE INDEX IF NOT EXISTS idx_contracts_owner_user_id ON contracts(owner_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_contracts_created_by ON contracts(created_by)",
    "CREATE INDEX IF NOT EXISTS idx_payments_owner_org_id ON payments(owner_org_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_owner_user_id ON payments(owner_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_created_by ON payments(created_by)",
    "CREATE INDEX IF NOT EXISTS idx_partners_owner_org_id ON partners(owner_org_id)",
    "CREATE INDEX IF NOT EXISTS idx_partners_owner_user_id ON partners(owner_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_partners_created_by ON partners(created_by)",
]


def _get_existing_columns(conn, table_name: str):
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _ensure_sqlite_schema():
    with engine.begin() as conn:
        for table_name, columns in _SQLITE_COMPAT_COLUMNS.items():
            existing_columns = _get_existing_columns(conn, table_name)
            for column_name, column_sql in columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))

        for statement in _SQLITE_INDEX_STATEMENTS:
            conn.execute(text(statement))


def init_db():
    Base.metadata.create_all(bind=engine)
    if is_sqlite(DATABASE_URL):
        _ensure_sqlite_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
