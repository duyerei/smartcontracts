"""
检查合同的summary内容
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, Contract

def check_summary(contract_id: int):
    """检查合同的summary"""
    db = next(get_db())
    
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    
    if not contract:
        print(f"合同 {contract_id} 不存在")
        return
    
    print(f"\n{'='*60}")
    print(f"合同ID: {contract.id}")
    print(f"合同编号: {contract.contract_number}")
    print(f"合同标题: {contract.title}")
    print(f"{'='*60}\n")
    
    print("Summary内容:")
    print(contract.summary if contract.summary else "(无)")
    
    print(f"\n{'='*60}")
    print("其他字段:")
    print(f"{'='*60}")
    print(f"甲方: {contract.parties}")
    print(f"合同类型: {contract.contract_type}")
    print(f"金额: {contract.amount}")
    print(f"签订日期: {contract.signed_date}")
    print(f"开始日期: {contract.start_date}")
    print(f"结束日期: {contract.end_date}")

if __name__ == "__main__":
    # 检查最新的合同
    contract_id = 23
    check_summary(contract_id)
