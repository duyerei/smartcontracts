"""检查合同18的文本内容"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract

db = SessionLocal()
try:
    contract = db.query(Contract).filter(Contract.id == 18).first()
    if contract:
        print(f"合同ID: {contract.id}")
        print(f"合同标题: {contract.title}")
        print(f"原始文本长度: {len(contract.raw_text) if contract.raw_text else 0}")
        print(f"摘要长度: {len(contract.summary) if contract.summary else 0}")
        print("\n" + "="*80)
        print("原始文本前2000字符:")
        print("="*80)
        if contract.raw_text:
            print(contract.raw_text[:2000])
        print("\n" + "="*80)
        print("原始文本后2000字符:")
        print("="*80)
        if contract.raw_text:
            print(contract.raw_text[-2000:])
        print("\n" + "="*80)
        print("摘要内容:")
        print("="*80)
        if contract.summary:
            print(contract.summary)
    else:
        print("合同不存在")
finally:
    db.close()
