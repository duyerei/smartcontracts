"""
测试附件内容识别
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db
from app.services.contract_parser import ContractParser
from app.services.llm_service import llm_service
from sqlalchemy.orm import Session

def test_contract_attachment(contract_id: int):
    """测试指定合同的附件识别"""
    db = next(get_db())
    
    # 查询合同
    from app.database import Contract
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    
    if not contract:
        print(f"合同 {contract_id} 不存在")
        return
    
    print(f"\n{'='*60}")
    print(f"测试合同: {contract.title}")
    print(f"合同ID: {contract.id}")
    print(f"{'='*60}\n")
    
    # 读取OCR文本
    parser = ContractParser()
    ocr_text = parser.get_ocr_text(contract.file_path)
    
    print(f"OCR文本总长度: {len(ocr_text)} 字符")
    print(f"\n{'='*60}")
    print("检查文本中的关键词:")
    print(f"{'='*60}")
    print(f"包含'附件': {'是' if '附件' in ocr_text else '否'}")
    print(f"包含'产品': {'是' if '产品' in ocr_text else '否'}")
    print(f"包含'明细': {'是' if '明细' in ocr_text else '否'}")
    print(f"包含'价格': {'是' if '价格' in ocr_text else '否'}")
    
    # 查找附件部分
    if "附件" in ocr_text:
        attachment_start = ocr_text.find("附件")
        attachment_section = ocr_text[attachment_start:attachment_start+1000]
        print(f"\n{'='*60}")
        print("附件部分内容预览（前1000字符）:")
        print(f"{'='*60}")
        print(attachment_section)
    
    # 测试智能采样
    print(f"\n{'='*60}")
    print("测试智能采样逻辑:")
    print(f"{'='*60}")
    
    pages = ocr_text.split("--- 第")
    print(f"总页数: {len(pages)}")
    
    for i, page in enumerate(pages):
        if "附件" in page:
            print(f"\n第 {i} 页包含'附件'")
            # 检查表格特征
            import re
            has_serial = "序号" in page or "编号" in page or re.search(r'^\s*\d+[、\.]', page, re.MULTILINE)
            has_product = "产品" in page or "服务" in page or "项目" in page
            has_price = re.search(r'\d+[,，]?\d*\.?\d*\s*元', page) or "价格" in page or "金额" in page
            
            print(f"  - 包含序号: {has_serial}")
            print(f"  - 包含产品/服务: {has_product}")
            print(f"  - 包含价格: {has_price}")
            
            if has_serial and has_product and has_price:
                print(f"  ✓ 识别为表格页面")
                print(f"\n页面内容预览（前500字符）:")
                print(page[:500])
    
    # 使用LLM提取摘要
    print(f"\n{'='*60}")
    print("使用LLM提取合同摘要:")
    print(f"{'='*60}")
    
    summary = llm_service.extract_full_summary(ocr_text)
    
    print("\n提取结果:")
    print(summary)
    
    print(f"\n{'='*60}")
    print("测试完成")
    print(f"{'='*60}")

if __name__ == "__main__":
    # 测试截图中的合同（根据截图，这应该是一个包含附件的合同）
    # 你需要替换为实际的合同ID
    contract_id = int(input("请输入要测试的合同ID: "))
    test_contract_attachment(contract_id)
