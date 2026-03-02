"""
根据合同编号查找合同ID
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, Contract

def find_contract(contract_number: str):
    """根据合同编号查找合同"""
    db = next(get_db())
    
    contract = db.query(Contract).filter(Contract.contract_number == contract_number).first()
    
    if contract:
        print(f"找到合同:")
        print(f"  ID: {contract.id}")
        print(f"  编号: {contract.contract_number}")
        print(f"  标题: {contract.title}")
        print(f"  文件路径: {contract.file_path}")
        return contract.id
    else:
        print(f"未找到合同编号: {contract_number}")
        return None

if __name__ == "__main__":
    contract_number = "CT-20260301-170623"
    contract_id = find_contract(contract_number)
    
    if contract_id:
        print(f"\n可以使用以下命令测试:")
        print(f"python test_attachment_recognition.py")
        print(f"然后输入ID: {contract_id}")
