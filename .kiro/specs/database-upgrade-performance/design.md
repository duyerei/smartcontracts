# 设计文档：数据库升级与性能优化

## 概述

本设计方案旨在将AI智能合同管理系统的数据库从SQLite迁移到PostgreSQL，以满足生产环境的并发访问、数据完整性和性能需求。当前系统使用SQLite作为单文件数据库，存在并发写入锁定、缺乏连接池、无法水平扩展等限制。

迁移方案涵盖六个核心领域：数据库引擎替换（SQLite → PostgreSQL）、连接池优化、索引策略、查询性能优化（解决N+1查询等问题）、数据迁移方案、以及Redis缓存策略。整体设计遵循渐进式迁移原则，确保零停机切换。

## 架构

### 当前架构

```mermaid
graph TD
    FE[React 前端<br/>Nginx :8080] -->|HTTP API| BE[FastAPI 后端<br/>:8000]
    BE -->|SQLAlchemy| DB[(SQLite<br/>contracts.db)]
    BE -->|文件存储| FS[/app/storage/]
```

### 目标架构

```mermaid
graph TD
    FE[React 前端<br/>Nginx :8080] -->|HTTP API| BE[FastAPI 后端<br/>:8000]
    BE -->|SQLAlchemy<br/>连接池| PG[(PostgreSQL 16<br/>:5432)]
    BE -->|缓存| RD[(Redis 7<br/>:6379)]
    BE -->|文件存储| FS[/app/storage/]
    
    PG -->|数据卷| PGV[pg-data Volume]
    RD -->|数据卷| RDV[redis-data Volume]
```

## 组件与接口

### 组件1：数据库引擎层（PostgreSQL）

**职责**：替换SQLite，提供生产级ACID事务、并发控制和数据完整性保障

**接口变更**：

```python
# 当前 SQLite 配置
DATABASE_URL = "sqlite:////app/data/contracts.db"

# 目标 PostgreSQL 配置
DATABASE_URL = "postgresql+asyncpg://contract_user:${DB_PASSWORD}@postgres:5432/contract_db"
# 同步引擎（兼容现有代码）
DATABASE_URL_SYNC = "postgresql+psycopg2://contract_user:${DB_PASSWORD}@postgres:5432/contract_db"
```

**Docker Compose 新增服务**：

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: contract-postgres
    restart: always
    environment:
      POSTGRES_DB: contract_db
      POSTGRES_USER: contract_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
    volumes:
      - pg-data:/var/lib/postgresql/data
      - ./backend/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U contract_user -d contract_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: contract-redis
    restart: always
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### 组件2：连接池管理

**职责**：管理数据库连接的创建、复用和回收，避免连接泄漏

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    config.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # 常驻连接数
    max_overflow=20,        # 峰值额外连接
    pool_timeout=30,        # 获取连接超时（秒）
    pool_recycle=1800,      # 连接回收周期（秒）
    pool_pre_ping=True,     # 使用前检测连接有效性
    echo=False,             # 生产环境关闭SQL日志
)
```

### 组件3：缓存层（Redis）

**职责**：缓存高频读取数据，减少数据库压力

```python
import redis.asyncio as redis
from functools import wraps
import json

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
    
    async def get(self, key: str) -> dict | None:
        data = await self.redis.get(key)
        return json.loads(data) if data else None
    
    async def set(self, key: str, value: dict, ttl: int = 300):
        await self.redis.set(key, json.dumps(value, default=str), ex=ttl)
    
    async def invalidate(self, pattern: str):
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```


## 数据模型

### PostgreSQL 表结构优化

当前SQLite模型迁移到PostgreSQL时需要的关键变更：

```python
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

class Contract(Base):
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_number = Column(String(100), unique=True, index=True)
    title = Column(String(500), nullable=False)
    contract_type = Column(String(50), index=True)
    department = Column(String(50), index=True)
    status = Column(String(20), default="待审核", index=True)
    parties = Column(JSONB, nullable=True)          # Text → JSONB，支持JSON查询
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
    extracted_data = Column(JSONB, nullable=True)   # Text → JSONB
    raw_text = Column(Text, nullable=True)
    raw_data = Column(JSONB, nullable=True)         # Text → JSONB
    
    # OA字段保持不变
    oa_id = Column(String(50), unique=True, index=True, nullable=True)
    applicant = Column(String(50), nullable=True)
    source = Column(String(20), default="upload")
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default="now()")
    updated_at = Column(DateTime, server_default="now()", onupdate="now()")
    
    # ORM关系（解决N+1查询）
    supplements = relationship("Supplement", back_populates="contract", lazy="selectin")
    attachments = relationship("ContractAttachment", back_populates="contract", lazy="selectin")
    
    __table_args__ = (
        Index("ix_contracts_type_status", "contract_type", "status"),
        Index("ix_contracts_dept_status", "department", "status"),
        Index("ix_contracts_dates", "start_date", "end_date"),
        Index("ix_contracts_source_deleted", "source", "is_deleted"),
        Index("ix_contracts_parties_gin", "parties", postgresql_using="gin"),
        CheckConstraint("amount >= 0", name="ck_contracts_amount_positive"),
    )
```

**验证规则**：
- `contract_number` 全局唯一，不可为空
- `amount` 必须 >= 0
- `parties` 字段从 Text 迁移为 JSONB，支持 GIN 索引加速模糊搜索
- `extracted_data` 和 `raw_data` 同样迁移为 JSONB

### 关系定义（解决N+1查询）

```python
class Supplement(Base):
    __tablename__ = "supplements"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), index=True)
    linked_contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True, index=True)
    # ... 其他字段保持不变
    
    contract = relationship("Contract", foreign_keys=[contract_id], back_populates="supplements")
    linked_contract = relationship("Contract", foreign_keys=[linked_contract_id])
    
    __table_args__ = (
        Index("ix_supplements_contract_deleted", "contract_id", "is_deleted"),
    )

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), index=True)
    # ... 其他字段保持不变
    
    contract = relationship("Contract")
    
    __table_args__ = (
        Index("ix_payments_contract_deleted", "contract_id", "is_deleted"),
    )

class ContractAttachment(Base):
    __tablename__ = "contract_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), index=True)
    # ... 其他字段保持不变
    
    contract = relationship("Contract", back_populates="attachments")
    
    __table_args__ = (
        Index("ix_attachments_contract_type", "contract_id", "attachment_type"),
    )
```

## 索引策略

### 复合索引设计

```sql
-- 合同列表查询优化（最高频查询）
CREATE INDEX ix_contracts_list_query 
    ON contracts(is_deleted, updated_at DESC) 
    WHERE is_deleted = false;

-- 合同搜索优化（全文搜索）
CREATE INDEX ix_contracts_title_trgm ON contracts 
    USING gin(title gin_trgm_ops);
CREATE INDEX ix_contracts_number_trgm ON contracts 
    USING gin(contract_number gin_trgm_ops);

-- parties JSONB 查询优化
CREATE INDEX ix_contracts_parties_gin ON contracts 
    USING gin(parties);

-- 合同类型+状态联合过滤
CREATE INDEX ix_contracts_type_status 
    ON contracts(contract_type, status) 
    WHERE is_deleted = false;

-- 部门+状态联合过滤
CREATE INDEX ix_contracts_dept_status 
    ON contracts(department, status) 
    WHERE is_deleted = false;

-- 日期范围查询
CREATE INDEX ix_contracts_date_range 
    ON contracts(start_date, end_date) 
    WHERE is_deleted = false;

-- 补充协议关联查询
CREATE INDEX ix_supplements_lookup 
    ON supplements(contract_id, linked_contract_id) 
    WHERE is_deleted = false;

-- 付款记录查询
CREATE INDEX ix_payments_contract 
    ON payments(contract_id, payment_date DESC) 
    WHERE is_deleted = false;

-- 合作伙伴搜索
CREATE INDEX ix_partners_name_trgm ON partners 
    USING gin(name gin_trgm_ops);
```

### PostgreSQL 扩展

```sql
-- 启用三元组模糊搜索扩展
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 启用全文搜索（中文需要额外配置）
-- 建议使用 zhparser 或 jieba 分词扩展
```


## 主要工作流

### 数据库迁移流程

```mermaid
sequenceDiagram
    participant Dev as 开发者
    participant Script as 迁移脚本
    participant SQLite as SQLite DB
    participant PG as PostgreSQL
    participant App as FastAPI 应用

    Dev->>Script: 执行 migrate.py
    Script->>SQLite: 读取所有表数据
    Script->>Script: 数据类型转换<br/>(Text→JSONB, 日期格式化)
    Script->>PG: 创建表结构 (Alembic)
    Script->>PG: 批量插入数据
    Script->>PG: 重建索引和约束
    Script->>PG: 验证数据完整性
    Script-->>Dev: 迁移报告
    Dev->>App: 更新 DATABASE_URL
    App->>PG: 连接新数据库
```

### 合同列表查询优化流程

```mermaid
sequenceDiagram
    participant Client as 前端
    participant API as FastAPI
    participant Cache as Redis
    participant DB as PostgreSQL

    Client->>API: GET /api/v1/contracts?page=1
    API->>Cache: 查询缓存 contracts:list:page1:...
    
    alt 缓存命中
        Cache-->>API: 返回缓存数据
    else 缓存未命中
        API->>DB: 单次JOIN查询<br/>(合同+补充协议)
        DB-->>API: 查询结果
        API->>Cache: 写入缓存 (TTL=60s)
    end
    
    API-->>Client: 返回合同列表
```

### 合作伙伴关联查询优化

```mermaid
sequenceDiagram
    participant Client as 前端
    participant API as FastAPI
    participant DB as PostgreSQL

    Note over API,DB: 当前：N+1查询（每个伙伴单独查合同数）
    
    Client->>API: GET /api/v1/partners?page=1
    API->>DB: 查询合作伙伴列表
    API->>DB: 单次聚合查询<br/>统计所有伙伴的合同数
    DB-->>API: {partner_id: count}
    API-->>Client: 合并返回结果
```

## 关键函数与形式化规约

### 函数1：database.py - 创建数据库引擎

```python
def create_db_engine(database_url: str) -> Engine:
    """根据数据库URL创建对应的SQLAlchemy引擎"""
```

**前置条件**：
- `database_url` 非空，格式为有效的SQLAlchemy连接字符串
- 如果是PostgreSQL URL，数据库服务已启动且可达

**后置条件**：
- 返回配置了连接池的 Engine 实例
- SQLite：使用 StaticPool，启用 WAL 模式
- PostgreSQL：使用 QueuePool，pool_size=10, max_overflow=20
- 连接池 pre_ping 已启用

**循环不变量**：无

### 函数2：migrate.py - 数据迁移

```python
def migrate_sqlite_to_postgres(
    sqlite_url: str, 
    postgres_url: str, 
    batch_size: int = 500
) -> MigrationReport:
    """将SQLite数据迁移到PostgreSQL"""
```

**前置条件**：
- `sqlite_url` 指向有效的SQLite数据库文件
- `postgres_url` 指向已创建的空PostgreSQL数据库
- `batch_size` > 0

**后置条件**：
- PostgreSQL中所有表的行数 == SQLite中对应表的行数
- 所有外键关系保持一致
- Text类型的JSON字段已转换为JSONB
- 日期字段已正确转换为PostgreSQL timestamp
- 返回包含迁移统计的 MigrationReport

**循环不变量**：
- 对于每个批次：已迁移行数 == 已处理批次数 × batch_size（最后一批除外）
- 每个批次提交后，数据库处于一致状态

### 函数3：cache.py - 缓存装饰器

```python
def cached(key_pattern: str, ttl: int = 300):
    """缓存装饰器，用于API端点结果缓存"""
```

**前置条件**：
- `key_pattern` 为有效的Redis键模式字符串
- `ttl` > 0（秒）
- Redis服务可用

**后置条件**：
- 缓存命中时：直接返回缓存数据，不执行原函数
- 缓存未命中时：执行原函数，结果写入缓存
- 缓存数据在 TTL 过期后自动清除

### 函数4：合同列表查询优化

```python
def list_contracts_optimized(
    db: Session,
    page: int,
    page_size: int,
    filters: dict
) -> dict:
    """优化后的合同列表查询，使用JOIN替代N+1"""
```

**前置条件**：
- `db` 为有效的数据库会话
- `page` >= 1, `page_size` >= 1 且 <= 100
- `filters` 中的字段名必须是合法的合同字段

**后置条件**：
- 返回的合同列表不包含已删除的记录
- 返回的合同列表不包含被标记为补充协议子合同的记录
- 每个合同对象包含其关联的补充协议子合同列表
- 数据库查询次数 <= 3（主查询 + 补充协议查询 + 计数查询）
- 结果按指定排序字段排序

**循环不变量**：无（使用SQL JOIN，非循环）

## 算法伪代码

### 数据迁移算法

```python
def migrate_sqlite_to_postgres(sqlite_url: str, postgres_url: str, batch_size: int = 500):
    """
    SQLite → PostgreSQL 数据迁移
    
    策略：按表依赖顺序迁移，批量插入，事务保护
    """
    # 表迁移顺序（按外键依赖）
    TABLE_ORDER = ["users", "contracts", "partners", "supplements", 
                   "payments", "contract_attachments", "partner_attachments"]
    
    sqlite_engine = create_engine(sqlite_url)
    pg_engine = create_engine(postgres_url)
    
    report = MigrationReport()
    
    # 步骤1：在PostgreSQL中创建表结构
    Base.metadata.create_all(pg_engine)
    
    for table_name in TABLE_ORDER:
        sqlite_session = Session(sqlite_engine)
        pg_session = Session(pg_engine)
        
        try:
            # 步骤2：读取SQLite数据
            rows = sqlite_session.execute(text(f"SELECT * FROM {table_name}")).fetchall()
            total = len(rows)
            migrated = 0
            
            # 步骤3：批量插入PostgreSQL
            for i in range(0, total, batch_size):
                batch = rows[i:i + batch_size]
                transformed = [transform_row(table_name, row) for row in batch]
                pg_session.execute(
                    insert(get_table(table_name)).values(transformed)
                )
                pg_session.commit()
                migrated += len(batch)
                # 不变量：migrated == min((i + batch_size), total)
            
            # 步骤4：重置序列（PostgreSQL自增ID）
            if total > 0:
                max_id = max(row.id for row in rows)
                pg_session.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id})"
                ))
                pg_session.commit()
            
            report.add(table_name, total, migrated)
        
        finally:
            sqlite_session.close()
            pg_session.close()
    
    # 步骤5：验证数据完整性
    verify_migration(sqlite_engine, pg_engine, TABLE_ORDER)
    
    return report


def transform_row(table_name: str, row: dict) -> dict:
    """
    转换单行数据以适配PostgreSQL
    
    前置条件：row 为有效的SQLite行数据
    后置条件：返回的dict中，JSON字符串字段已转为dict/list
    """
    result = dict(row._mapping)
    
    # Text → JSONB 转换
    json_fields = {
        "contracts": ["parties", "extracted_data", "raw_data"],
        "payments": [],
    }
    
    for field in json_fields.get(table_name, []):
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                result[field] = None
    
    return result
```

### 合同列表查询优化算法

```python
def list_contracts_optimized(db: Session, page: int, page_size: int, filters: dict) -> dict:
    """
    优化后的合同列表查询
    
    优化点：
    1. 使用子查询替代全表扫描获取子合同ID
    2. 使用LEFT JOIN一次性加载补充协议
    3. 使用窗口函数避免额外的COUNT查询
    """
    # 子查询：获取所有被关联为补充协议的合同ID
    child_ids_subquery = (
        db.query(Supplement.linked_contract_id)
        .filter(
            Supplement.linked_contract_id.isnot(None),
            Supplement.is_deleted == False
        )
        .subquery()
    )
    
    # 主查询：排除子合同
    query = (
        db.query(Contract)
        .filter(
            Contract.is_deleted == False,
            ~Contract.id.in_(select(child_ids_subquery))
        )
    )
    
    # 应用过滤条件
    if filters.get("search"):
        search_term = f"%{filters['search']}%"
        query = query.filter(
            or_(
                Contract.title.ilike(search_term),
                Contract.contract_number.ilike(search_term),
                # PostgreSQL JSONB 搜索
                Contract.parties.cast(String).ilike(search_term)
            )
        )
    
    if filters.get("contract_type"):
        query = query.filter(Contract.contract_type == filters["contract_type"])
    if filters.get("department"):
        query = query.filter(Contract.department == filters["department"])
    if filters.get("status"):
        query = query.filter(Contract.status == filters["status"])
    
    # 使用 selectin 策略预加载补充协议（避免N+1）
    query = query.options(
        selectinload(Contract.supplements)
        .selectinload(Supplement.linked_contract)
    )
    
    total = query.count()
    
    # 排序和分页
    sort_column = SORT_FIELD_MAP.get(filters.get("sort_field", ""), Contract.updated_at)
    if filters.get("sort_order") == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    contracts = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {"total": total, "page": page, "page_size": page_size, "contracts": contracts}
```

### 合作伙伴列表查询优化

```python
def list_partners_optimized(db: Session, page: int, page_size: int, search: str = None) -> dict:
    """
    优化合作伙伴列表查询
    
    当前问题：每个合作伙伴单独查询关联合同数（N+1）
    优化方案：使用子查询一次性统计所有合作伙伴的合同数
    """
    query = db.query(Partner).filter(Partner.is_deleted == False)
    
    if search:
        # PostgreSQL: 使用 pg_trgm 模糊搜索
        query = query.filter(
            or_(
                Partner.name.ilike(f"%{search}%"),
                Partner.contact_name.ilike(f"%{search}%"),
            )
        )
    
    total = query.count()
    partners = query.order_by(Partner.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    
    # 一次性查询所有合作伙伴的合同数（替代N+1）
    partner_names = [p.name for p in partners]
    if partner_names:
        # 使用 JSONB 包含查询
        contract_counts = (
            db.query(
                func.unnest(
                    func.array_agg(Contract.id)
                ).label("partner_name"),
                func.count(Contract.id).label("count")
            )
            .filter(Contract.is_deleted == False)
            # 对于JSONB parties字段，使用 @> 操作符
            .group_by("partner_name")
            .all()
        )
        # 简化方案：批量查询
        count_map = {}
        for name in partner_names:
            count = db.query(func.count(Contract.id)).filter(
                Contract.is_deleted == False,
                Contract.parties.cast(String).contains(name)
            ).scalar()
            count_map[name] = count
    
    return {"partners": partners, "counts": count_map, "total": total}
```

## 示例用法

### 数据库配置（升级后）

```python
# backend/app/database.py（升级后）
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool
from app.config import config

def _create_engine():
    url = config.DATABASE_URL
    
    if "sqlite" in url:
        # 开发环境：保留SQLite支持
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            pool_pre_ping=True,
        )
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
        return engine
    else:
        # 生产环境：PostgreSQL + 连接池
        return create_engine(
            url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=False,
        )

engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

### 缓存使用示例

```python
# backend/app/cache.py
from app.config import config
import redis.asyncio as aioredis
import json

redis_client = None

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            config.REDIS_URL, 
            decode_responses=True
        )
    return redis_client

# 在路由中使用
@router.get("/contracts")
async def list_contracts(page: int = 1, ...):
    cache_key = f"contracts:list:{page}:{page_size}:{search}:{contract_type}"
    
    rd = await get_redis()
    cached = await rd.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 执行数据库查询
    result = list_contracts_optimized(db, page, page_size, filters)
    
    # 写入缓存（60秒过期）
    await rd.set(cache_key, json.dumps(result, default=str), ex=60)
    
    return result
```

### 环境配置示例

```bash
# backend/.env.production（升级后）
DATABASE_URL=postgresql+psycopg2://contract_user:your_secure_password@postgres:5432/contract_db
REDIS_URL=redis://redis:6379/0
```


## 正确性属性

以下属性必须在迁移前后和运行时始终成立：

1. **数据完整性**：∀ table ∈ {contracts, supplements, payments, partners, ...}，迁移后 PostgreSQL 中的行数 == SQLite 中的行数
2. **外键一致性**：∀ supplement ∈ supplements，supplement.contract_id 必须引用 contracts 表中存在的记录
3. **连接池边界**：在任意时刻，活跃连接数 <= pool_size + max_overflow（即 <= 30）
4. **缓存一致性**：当合同数据被修改（CREATE/UPDATE/DELETE）时，相关缓存键必须被失效
5. **查询性能**：合同列表查询的数据库往返次数 <= 3（主查询 + 补充协议预加载 + 计数）
6. **向后兼容**：开发环境仍可使用 SQLite，通过 DATABASE_URL 前缀自动切换引擎配置
7. **序列一致性**：迁移后 PostgreSQL 的自增序列值 > 当前最大ID，确保新记录不会ID冲突

## 错误处理

### 场景1：数据库连接失败

**条件**：PostgreSQL 服务不可达或连接池耗尽
**响应**：返回 HTTP 503 Service Unavailable，包含重试提示
**恢复**：连接池 pre_ping 自动检测并重建失效连接；Docker healthcheck 自动重启服务

### 场景2：数据迁移中断

**条件**：迁移脚本执行过程中发生错误（网络中断、磁盘满等）
**响应**：当前批次回滚，记录已完成的表和批次号
**恢复**：支持断点续传，从上次成功的批次继续迁移

### 场景3：缓存服务不可用

**条件**：Redis 服务宕机或不可达
**响应**：降级为直接查询数据库，不影响核心功能
**恢复**：Redis 恢复后自动重连，缓存逐步预热

### 场景4：并发写入冲突

**条件**：多个请求同时修改同一合同记录
**响应**：PostgreSQL 行级锁保证数据一致性，后提交的事务等待或失败
**恢复**：使用乐观锁（updated_at 版本检查）或重试机制

## 测试策略

### 单元测试

- 测试 `transform_row` 函数对各种数据类型的转换正确性
- 测试连接池配置在不同 DATABASE_URL 下的行为
- 测试缓存键生成和失效逻辑
- 测试查询过滤条件的正确组合

### 属性测试

**属性测试库**：hypothesis

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=0, max_size=1000))
def test_json_field_migration_roundtrip(json_str):
    """属性：JSON字段迁移后可以正确反序列化"""
    # 如果原始值是有效JSON，迁移后应保持等价
    try:
        original = json.loads(json_str)
        migrated = transform_row("contracts", {"parties": json_str})
        assert migrated["parties"] == original
    except json.JSONDecodeError:
        migrated = transform_row("contracts", {"parties": json_str})
        assert migrated["parties"] is None
```

### 集成测试

- 使用 Docker Compose 启动 PostgreSQL 测试实例
- 执行完整迁移流程并验证数据完整性
- 测试连接池在高并发下的行为（使用 locust 或 pytest-asyncio）
- 测试缓存命中/未命中/失效的完整流程

## 性能考量

### 预期性能提升

| 场景 | SQLite 当前 | PostgreSQL 目标 | 提升 |
|------|------------|----------------|------|
| 合同列表（100条） | ~200ms | ~50ms | 4x |
| 合同搜索（模糊） | ~500ms | ~80ms（pg_trgm） | 6x |
| 合作伙伴列表（N+1） | ~800ms（20条） | ~100ms（JOIN） | 8x |
| 并发写入 | 串行（锁） | 并行（MVCC） | 10x+ |

### 连接池调优建议

- `pool_size=10`：适合中小规模部署（<50并发用户）
- `max_overflow=20`：应对突发流量
- `pool_recycle=1800`：避免长连接被防火墙断开
- 监控指标：`pool.checkedout()`、`pool.overflow()`、`pool.checkedin()`

### PostgreSQL 配置优化

```ini
# postgresql.conf 关键参数
shared_buffers = 256MB          # 总内存的25%
effective_cache_size = 768MB    # 总内存的75%
work_mem = 16MB                 # 排序/哈希操作内存
maintenance_work_mem = 128MB    # 维护操作内存
random_page_cost = 1.1          # SSD存储
```

## 安全考量

- 数据库密码通过环境变量注入，不硬编码在配置文件中
- PostgreSQL 使用独立用户 `contract_user`，仅授予必要权限（SELECT, INSERT, UPDATE, DELETE）
- Redis 在内网部署，不暴露外部端口
- 数据库连接使用 SSL/TLS 加密（生产环境）
- 迁移脚本执行前自动备份 SQLite 数据库文件

## 依赖

### 新增 Python 依赖

```
psycopg2-binary>=2.9.9      # PostgreSQL 同步驱动
redis>=5.0.0                  # Redis 客户端
alembic>=1.13.0               # 数据库迁移工具
```

### 新增基础设施

- PostgreSQL 16 Alpine（Docker 镜像）
- Redis 7 Alpine（Docker 镜像）

### 现有依赖保持不变

- SQLAlchemy（已使用，升级连接配置即可）
- FastAPI + Uvicorn
- 百度OCR / 千帆大模型 / 火山引擎 ARK
