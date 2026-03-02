"""测试风险分析功能"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract
from app.services import llm_service

db = SessionLocal()
try:
    # 测试合同ID 18
    contract = db.query(Contract).filter(Contract.id == 18).first()
    if contract and contract.raw_text:
        print(f"合同ID: {contract.id}")
        print(f"合同标题: {contract.title}")
        print(f"原始文本长度: {len(contract.raw_text)}")
        
        print("\n" + "="*80)
        print("开始风险分析...")
        print("="*80)
        
        try:
            risk_analysis = llm_service.llm_service.analyze_risk(contract.raw_text)
            
            if risk_analysis:
                print(f"\n✓ 风险分析成功")
                print(f"分析结果长度: {len(risk_analysis)} 字符")
                print("\n" + "="*80)
                print("风险分析结果:")
                print("="*80)
                print(risk_analysis)
                
                # 统计风险等级
                high_count = risk_analysis.count("🔴")
                medium_count = risk_analysis.count("🟡")
                low_count = risk_analysis.count("🟢")
                print("\n" + "="*80)
                print(f"风险统计: 🔴 高风险 {high_count} 个, 🟡 中风险 {medium_count} 个, 🟢 低风险 {low_count} 个")
                
                # 判断整体风险等级
                if high_count >= 2:
                    overall = "high"
                elif high_count >= 1 or medium_count >= 3:
                    overall = "medium"
                else:
                    overall = "low"
                print(f"整体风险等级: {overall}")
            else:
                print("\n✗ 风险分析失败：LLM返回空结果")
                
        except Exception as e:
            print(f"\n✗ 风险分析异常: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("合同不存在或无原始文本")
finally:
    db.close()
