import os
from typing import Any

from sqlalchemy.engine import URL, make_url


SUPPORTED_DATABASES = {"sqlite", "mysql", "postgresql"}


def normalize_database_url(database_url: str) -> str:
    """规范数据库连接串，兼容常见主流数据库写法。"""
    url = make_url(database_url)
    drivername = url.drivername

    if drivername == "mysql":
        return url.set(drivername="mysql+pymysql").render_as_string(hide_password=False)
    if drivername == "postgres":
        return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    if drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)

    return url.render_as_string(hide_password=False)


def get_database_name(database_url: str) -> str:
    url = make_url(database_url)
    return url.get_backend_name()


def is_sqlite(database_url: str) -> bool:
    return get_database_name(database_url) == "sqlite"


def build_engine_options(database_url: str) -> dict[str, Any]:
    """根据数据库类型生成 SQLAlchemy engine 参数。"""
    database_name = get_database_name(database_url)
    if database_name not in SUPPORTED_DATABASES:
        supported = ", ".join(sorted(SUPPORTED_DATABASES))
        raise ValueError(f"不支持的数据库类型: {database_name}，当前支持: {supported}")

    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_name == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
        return options

    options["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    options["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    options["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    return options


def render_safe_database_url(database_url: str) -> str:
    """打印日志时隐藏密码，避免泄露数据库凭据。"""
    url = make_url(database_url)
    if not isinstance(url, URL) or url.password is None:
        return database_url
    return url.render_as_string(hide_password=True)
