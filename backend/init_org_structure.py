"""初始化组织架构、角色权限和用户组织归属。

用法：
    python init_org_structure.py

脚本会读取当前 DATABASE_URL 指向的数据库，因此测试环境和生产环境执行同一个命令即可。
"""

from app.database import SessionLocal, init_db
from app.security.bootstrap import bootstrap_security_data


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        bootstrap_security_data(db)
        print("组织架构、角色权限和用户组织归属初始化完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()
