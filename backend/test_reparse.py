"""测试重新解析功能"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract
from app.services import contract_parser, llm_service, file_storage
from app.routers.contracts import _merge_llm_result, _generate_contract_summary
from datetime import datetime
import json

def test_reparse(contract_id: int):
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            print(f"合同 {contract_id} 不存在")
            return
        
        print(f"开始重新解析合同: {contract.title}")
        print(f"合同编号: {contract.contract_number}")
        
        # 获取文件路径
        full_path = file_storage.get_file_path(contract.file_path)
        if not full_path.exists():
            print("文件不存在")
            return
        
        print(f"文件路径: {full_path}")
        
        # 重新OCR解析
        print("\n1. OCR解析...")
        parse_result = contract_parser.parse_contract(str(full_path), "")
        extracted = parse_result.get("data", {})
        raw_text = parse_result.get("raw_text", "")
        
        print(f"   - 提取的签订日期: {extracted.get('signed_date')}")
        print(f"   - 提取的开始日期: {extracted.get('start_date')}")
        print(f"   - 提取的结束日期: {extracted.get('end_date')}")
        print(f"   - 原始文本长度: {len(raw_text)}")
        
        # LLM增强解析
        print("\n2. LLM增强解析...")
        llm_result = {}
        if raw_text and len(raw_text) > 100:
            try:
                llm_result = llm_service.llm_service.parse_contract_with_llm(raw_text)
                print(f"   - LLM解析成功")
                print(f"   - LLM提取的签订日期: {llm_result.get('签订日期')}")
                print(f"   - LLM提取的开始日期: {llm_result.get('服务期限开始日期')}")
                print(f"   - LLM提取的结束日期: {llm_result.get('服务期限结束日期')}")
            except Exception as e:
                print(f"   - LLM解析失败: {e}")
        
        if llm_result:
            extracted = _merge_llm_result(extracted, llm_result)
            print("\n3. 合并后的结果:")
            print(f"   - 签订日期: {extracted.get('signed_date')}")
            print(f"   - 开始日期: {extracted.get('start_date')}")
            print(f"   - 结束日期: {extracted.get('end_date')}")
        
        # LLM生成摘要
        print("\n4. 生成摘要...")
        summary = ""
        try:
            llm_summary = llm_service.llm_service.extract_full_summary(raw_text)
            if llm_summary:
                summary = llm_summary
                print(f"   - LLM摘要生成成功，长度: {len(summary)}")
        except Exception as e:
            print(f"   - LLM摘要生成失败: {e}")
        
        if not summary:
            summary = _generate_contract_summary(extracted, raw_text)
            print(f"   - 使用基础摘要，长度: {len(summary)}")
        
        print("\n5. 更新数据库...")
        # 更新所有字段
        contract.parties = json.dumps(extracted.get("parties", []), ensure_ascii=False)
        contract.summary = summary
        contract.raw_text = raw_text
        
        # 更新日期字段
        if extracted.get("signed_date"):
            try:
                date_str = extracted["signed_date"]
                # 尝试多种日期格式
                for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                    try:
                        contract.signed_date = datetime.strptime(date_str, fmt)
                        print(f"   - 更新签订日期: {contract.signed_date}")
                        break
                    except:
                        continue
            except Exception as e:
                print(f"   - 签订日期转换失败: {e}")
        
        if extracted.get("start_date"):
            try:
                date_str = extracted["start_date"]
                for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                    try:
                        contract.start_date = datetime.strptime(date_str, fmt)
                        print(f"   - 更新开始日期: {contract.start_date}")
                        break
                    except:
                        continue
            except Exception as e:
                print(f"   - 开始日期转换失败: {e}")
        
        if extracted.get("end_date"):
            try:
                date_str = extracted["end_date"]
                for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                    try:
                        contract.end_date = datetime.strptime(date_str, fmt)
                        print(f"   - 更新结束日期: {contract.end_date}")
                        break
                    except:
                        continue
            except Exception as e:
                print(f"   - 结束日期转换失败: {e}")
        
        contract.updated_at = datetime.now()
        
        db.commit()
        print("\n✓ 重新解析完成")
        
    except Exception as e:
        print(f"\n✗ 重新解析失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    # 测试合同ID 18（集团客户服务协议-固网业务）
    test_reparse(18)
