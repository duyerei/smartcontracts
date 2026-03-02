"""数据库迁移脚本：添加 signed_date 字段"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path(__file__).parent / "contracts.db"
    
    if not db_path.exists():
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(contracts)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'signed_date' in columns:
            print("signed_date 字段已存在，跳过迁移")
            return
        
        # 添加 signed_date 字段
        print("添加 signed_date 字段...")
        cursor.execute("ALTER TABLE contracts ADD COLUMN signed_date DATETIME")
        conn.commit()
        print("✓ signed_date 字段添加成功")
        
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
