"""
添加付款管理表
"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path(__file__).parent / "contracts.db"
    
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查payments表是否已存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
        if cursor.fetchone():
            print("✓ payments 表已存在，无需创建")
        else:
            print("创建 payments 表...")
            cursor.execute("""
                CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    payment_date DATETIME,
                    amount REAL,
                    description VARCHAR(500),
                    file_path VARCHAR(500),
                    file_size INTEGER,
                    is_deleted BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX ix_payments_contract_id ON payments (contract_id)")
            
            conn.commit()
            print("✓ payments 表创建成功")
        
        # 验证表结构
        cursor.execute("PRAGMA table_info(payments)")
        columns = cursor.fetchall()
        print("\n当前 payments 表结构:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("付款管理表迁移")
    print("=" * 60)
    migrate()
    print("\n迁移完成!")
