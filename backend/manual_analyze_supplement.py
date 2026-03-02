"""
手动触发补充协议分析
"""
import sys
sys.path.insert(0, '.')

from app.routers.supplements import analyze_and_update_supplement
from pathlib import Path

# 获取最新的补充协议
import sqlite3

db_path = Path("contracts.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
    SELECT id, file_path
    FROM supplements
    WHERE is_deleted = 0
    AND (signed_date IS NULL OR amount IS NULL)
    ORDER BY created_at DESC
    LIMIT 1
""")

result = cursor.fetchone()
conn.close()

if not result:
    print("没有需要分析的补充协议")
else:
    supplement_id, file_path = result
    print(f"开始分析补充协议 ID={supplement_id}, 文件={file_path}")
    
    # 构建完整路径
    full_path = Path("storage") / file_path
    
    # 调用分析函数
    analyze_and_update_supplement(supplement_id, str(full_path))
    
    print("\n分析完成，检查结果...")
    
    # 检查结果
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT signed_date, amount
        FROM supplements
        WHERE id = ?
    """, (supplement_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        print(f"签订时间: {result[0] or '未识别'}")
        print(f"金额: {result[1] or '未识别'}")
