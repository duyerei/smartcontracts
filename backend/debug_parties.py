"""调试脚本：检查数据库中的 parties 字段"""
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract

def main():
    db = SessionLocal()
    try:
        # 获取所有合同
        contracts = db.query(Contract).filter(Contract.is_deleted == False).limit(10).all()
        
        print(f"找到 {len(contracts)} 份合同\n")
        
        for contract in contracts:
            print(f"合同ID: {contract.id}")
            print(f"合同编号: {contract.contract_number}")
            print(f"合同标题: {contract.title}")
            print(f"Parties原始值: {repr(contract.parties)}")
            print(f"Parties类型: {type(contract.parties)}")
            
            # 尝试解析
            try:
                if contract.parties:
                    parsed = json.loads(contract.parties)
                    print(f"解析后: {parsed}")
                    print(f"解析后类型: {type(parsed)}")
                    if isinstance(parsed, list):
                        print(f"数组长度: {len(parsed)}")
                        for i, party in enumerate(parsed):
                            print(f"  [{i}] = {repr(party)}")
                else:
                    print("Parties为空")
            except Exception as e:
                print(f"解析失败: {e}")
            
            print("-" * 80)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
