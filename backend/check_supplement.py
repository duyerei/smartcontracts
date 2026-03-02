"""
检查补充协议记录
"""
import sqlite3
from pathlib import Path

def check_supplements():
    db_path = Path(__file__).parent / "contracts.db"
    
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 查询所有补充协议
        cursor.execute("""
            SELECT id, contract_id, title, signed_date, amount, file_path, created_at
            FROM supplements
            WHERE is_deleted = 0
            ORDER BY created_at DESC
        """)
        
        supplements = cursor.fetchall()
        
        if not supplements:
            print("没有找到补充协议记录")
            return
        
        print(f"找到 {len(supplements)} 条补充协议记录:\n")
        
        for s in supplements:
            print(f"ID: {s[0]}")
            print(f"  合同ID: {s[1]}")
            print(f"  标题: {s[2]}")
            print(f"  签订时间: {s[3] or '未识别'}")
            print(f"  金额: {s[4] or '未识别'}")
            print(f"  文件路径: {s[5]}")
            print(f"  创建时间: {s[6]}")
            print()
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("补充协议记录检查")
    print("=" * 60)
    check_supplements()
