"""
添加补充协议金额字段
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
        # 检查amount字段是否已存在
        cursor.execute("PRAGMA table_info(supplements)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'amount' not in columns:
            print("添加 amount 字段到 supplements 表...")
            cursor.execute("""
                ALTER TABLE supplements 
                ADD COLUMN amount REAL
            """)
            conn.commit()
            print("✓ amount 字段添加成功")
        else:
            print("✓ amount 字段已存在，无需添加")
        
        # 验证字段
        cursor.execute("PRAGMA table_info(supplements)")
        columns = cursor.fetchall()
        print("\n当前 supplements 表结构:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("补充协议金额字段迁移")
    print("=" * 60)
    migrate()
    print("\n迁移完成!")
