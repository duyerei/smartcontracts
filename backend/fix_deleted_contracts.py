"""修复软删除合同的编号冲突问题"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'contracts.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT id, contract_number FROM contracts WHERE is_deleted=1")
rows = cur.fetchall()

print(f"找到 {len(rows)} 条已删除合同")
for row_id, number in rows:
    if '__deleted_' not in (number or ''):
        new_number = f"{number}__deleted_{row_id}"
        cur.execute("UPDATE contracts SET contract_number=? WHERE id=?", (new_number, row_id))
        print(f"  ID={row_id}: {number} -> {new_number}")

conn.commit()
conn.close()
print("完成")
