"""
列出最近的合同
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, Contract
from sqlalchemy import desc

def list_recent():
    """列出最近的10个合同"""
    db = next(get_db())
    
    contracts = db.query(Contract).order_by(desc(Contract.created_at)).limit(10).all()
    
    print(f"最近的10个合同:")
    print("="*80)
    for c in contracts:
        print(f"ID: {c.id:3d} | 编号: {c.contract_number:25s} | 标题: {c.title}")
    print("="*80)

if __name__ == "__main__":
    list_recent()
