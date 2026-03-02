"""检查合同18的摘要"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract

db = SessionLocal()
try:
    contract = db.query(Contract).filter(Contract.id == 18).first()
    if contract:
        print("="*80)
        print("摘要内容:")
        print("="*80)
        print(contract.summary if contract.summary else "无摘要")
        print("\n" + "="*80)
        print(f"摘要长度: {len(contract.summary) if contract.summary else 0} 字符")
    else:
        print("合同不存在")
finally:
    db.close()
