"""
手动重新解析合同23
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, Contract
from app.services.contract_parser import ContractParser
from app.services.llm_service import llm_service
from app.services.baidu_ocr import BaiduOCR

def reparse_contract_23():
    """重新解析合同23"""
    db = next(get_db())
    contract_id = 23
    
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    
    if not contract:
        print(f"合同 {contract_id} 不存在")
        return
    
    print(f"\n{'='*60}")
    print(f"开始重新解析合同")
    print(f"合同ID: {contract.id}")
    print(f"合同编号: {contract.contract_number}")
    print(f"文件路径: {contract.file_path}")
    print(f"{'='*60}\n")
    
    # 构建完整文件路径
    file_path = os.path.join("storage", contract.file_path)
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print("步骤1: OCR识别（这可能需要1-2分钟）...")
    ocr = BaiduOCR()
    
    try:
        text = ocr.extract_text_from_file(file_path)
        print(f"OCR完成，提取文本长度: {len(text)} 字符")
        
        if len(text) < 500:
            print("\n警告：提取的文本太短，可能识别失败")
            print(f"文本内容:\n{text}")
            return
        
        print(f"\n文本前500字符:\n{text[:500]}")
        
        print("\n步骤2: LLM提取基本信息...")
        llm_result = llm_service.parse_contract_with_llm(text)
        
        if llm_result:
            print(f"LLM基本信息提取成功")
            print(f"  合同名称: {llm_result.get('合同名称', '未提取')}")
            print(f"  甲方: {llm_result.get('甲方', '未提取')}")
            print(f"  乙方: {llm_result.get('乙方', '未提取')}")
            print(f"  签订日期: {llm_result.get('签订日期', '未提取')}")
            
            # 更新基本信息
            if llm_result.get("合同名称"):
                contract.title = llm_result["合同名称"]
            
            parties_list = []
            if llm_result.get("甲方"):
                parties_list.append(llm_result["甲方"])
            if llm_result.get("乙方"):
                parties_list.append(llm_result["乙方"])
            if llm_result.get("丙方") and llm_result.get("丙方") != "null":
                parties_list.append(llm_result["丙方"])
            
            if parties_list:
                import json
                contract.parties = json.dumps(parties_list, ensure_ascii=False)
            
            # 更新日期
            if llm_result.get("签订日期") and llm_result.get("签订日期") != "null":
                from datetime import datetime
                date_str = llm_result["签订日期"]
                for fmt in ["%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"]:
                    try:
                        contract.signed_date = datetime.strptime(date_str, fmt)
                        break
                    except:
                        continue
        else:
            print("LLM基本信息提取失败")
        
        print("\n步骤3: LLM提取合同摘要...")
        summary = llm_service.extract_full_summary(text)
        
        if summary:
            print(f"LLM提取完成，摘要长度: {len(summary)} 字符")
            print(f"\n摘要内容:\n{summary[:500]}...")
            
            # 更新数据库（包括raw_text）
            contract.summary = summary
            contract.raw_text = text  # 保存OCR文本
            db.commit()
            print("\n✓ 数据库已更新（包括raw_text）")
        else:
            print("LLM提取失败或返回空")
        
        print(f"\n{'='*60}")
        print("重新解析完成")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("注意：这将调用百度OCR API，可能需要1-2分钟")
    print("按Enter继续...")
    input()
    reparse_contract_23()
