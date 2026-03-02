"""检查合同日期数据"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract

def main():
    db = SessionLocal()
    try:
        # 查找"劳动关系转移协议"
        contract = db.query(Contract).filter(
            Contract.title.like("%劳动关系转移%")
        ).first()
        
        if not contract:
            print("未找到合同")
            return
        
        print(f"合同ID: {contract.id}")
        print(f"合同编号: {contract.contract_number}")
        print(f"合同标题: {contract.title}")
        print(f"签订时间: {contract.signed_date}")
        print(f"开始日期: {contract.start_date}")
        print(f"结束日期: {contract.end_date}")
        print(f"原始文本长度: {len(contract.raw_text) if contract.raw_text else 0}")
        
        # 检查原始文本中的日期信息
        if contract.raw_text:
            text = contract.raw_text[:2000]
            print("\n原始文本前2000字符:")
            print(text)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
