#!/usr/bin/env python3
"""添加补充协议表的数据库迁移脚本"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path(__file__).parent / "contracts.db"
    
    if not db_path.exists():
        print("❌ 数据库文件不存在")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查supplements表是否已存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='supplements'")
        if cursor.fetchone():
            print("✅ supplements表已存在，无需迁移")
            return
        
        # 创建supplements表
        cursor.execute("""
            CREATE TABLE supplements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                title VARCHAR(500),
                signed_date DATETIME,
                file_path VARCHAR(500),
                file_size INTEGER,
                is_deleted BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX ix_supplements_contract_id ON supplements (contract_id)")
        
        conn.commit()
        print("✅ supplements表创建成功")
        
        # 显示表结构
        cursor.execute("PRAGMA table_info(supplements)")
        columns = cursor.fetchall()
        print("\n表结构：")
        for col in columns:
            print(f"  {col[1]} {col[2]}")
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("数据库迁移：添加补充协议表")
    print("=" * 50)
    migrate()
