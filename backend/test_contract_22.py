"""
测试合同22的附件识别
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, Contract
from app.services.baidu_ocr import BaiduOCR
from app.services.llm_service import llm_service
import re
import os

def test_contract_22():
    """测试合同23的附件识别"""
    db = next(get_db())
    contract_id = 23
    
    # 查询合同
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    
    if not contract:
        print(f"合同 {contract_id} 不存在")
        return
    
    print(f"\n{'='*60}")
    print(f"测试合同: {contract.title}")
    print(f"合同ID: {contract.id}")
    print(f"合同编号: {contract.contract_number}")
    print(f"{'='*60}\n")
    
    # 读取OCR文本
    ocr = BaiduOCR()
    # 构建完整文件路径
    file_path = os.path.join("storage", contract.file_path)
    print(f"文件路径: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    ocr_text = ocr.extract_text_from_file(file_path)
    
    print(f"OCR文本总长度: {len(ocr_text)} 字符")
    
    # 查找附件部分
    if "附件" in ocr_text:
        attachment_start = ocr_text.find("附件")
        print(f"\n找到'附件'关键词，位置: {attachment_start}")
        
        # 提取附件部分（前后各500字符）
        start = max(0, attachment_start - 200)
        end = min(len(ocr_text), attachment_start + 1500)
        attachment_section = ocr_text[start:end]
        
        print(f"\n{'='*60}")
        print("附件部分内容:")
        print(f"{'='*60}")
        print(attachment_section)
        print(f"{'='*60}\n")
    else:
        print("\n未找到'附件'关键词")
    
    # 查找产品明细
    keywords = ["产品", "明细", "价格", "软件", "定制", "升级", "支持"]
    print(f"\n{'='*60}")
    print("关键词检查:")
    print(f"{'='*60}")
    for kw in keywords:
        count = ocr_text.count(kw)
        print(f"'{kw}': {count} 次")
    
    # 查找价格数字
    price_pattern = r'\d+[,，]?\d*\.?\d*\s*元'
    prices = re.findall(price_pattern, ocr_text)
    print(f"\n找到 {len(prices)} 个价格:")
    for i, price in enumerate(prices[:10], 1):  # 只显示前10个
        print(f"  {i}. {price}")
    if len(prices) > 10:
        print(f"  ... 还有 {len(prices) - 10} 个")
    
    # 测试智能采样
    print(f"\n{'='*60}")
    print("测试智能采样逻辑:")
    print(f"{'='*60}")
    
    pages = ocr_text.split("--- 第")
    print(f"总页数: {len(pages)}")
    
    found_attachment_page = False
    for i, page in enumerate(pages):
        if "附件" in page:
            print(f"\n第 {i} 页包含'附件'")
            
            # 检查表格特征
            has_serial = "序号" in page or "编号" in page or re.search(r'^\s*\d+[、\.]', page, re.MULTILINE)
            has_product = "产品" in page or "服务" in page or "项目" in page
            has_price = re.search(r'\d+[,，]?\d*\.?\d*\s*元', page) or "价格" in page or "金额" in page
            
            print(f"  - 包含序号: {has_serial}")
            print(f"  - 包含产品/服务: {has_product}")
            print(f"  - 包含价格: {has_price}")
            
            has_table_structure = has_serial and has_product and has_price
            print(f"  - 识别为表格: {has_table_structure}")
            
            if has_table_structure:
                found_attachment_page = True
                print(f"\n  ✓ 找到附件表格页面")
                print(f"\n页面内容（前800字符）:")
                print(page[:800])
    
    if not found_attachment_page:
        print("\n⚠ 未找到符合条件的附件表格页面")
        print("尝试查找包含多个价格的页面...")
        
        for i, page in enumerate(pages):
            price_matches = re.findall(price_pattern, page)
            if len(price_matches) >= 3:
                print(f"\n第 {i} 页包含 {len(price_matches)} 个价格")
                print(f"页面内容（前500字符）:")
                print(page[:500])
                break
    
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
    test_contract_22()
