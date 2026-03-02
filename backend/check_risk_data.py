"""检查合同18的风险分析数据"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract

db = SessionLocal()
try:
    contract = db.query(Contract).filter(Contract.id == 18).first()
    if contract:
        print(f"合同ID: {contract.id}")
        print(f"风险等级: {contract.risk_level}")
        print(f"风险分析长度: {len(contract.risk_analysis) if contract.risk_analysis else 0}")
        print("\n" + "="*80)
        print("风险分析内容:")
        print("="*80)
        if contract.risk_analysis:
            print(contract.risk_analysis)
        else:
            print("无风险分析数据")
    else:
        print("合同不存在")
finally:
    db.close()
