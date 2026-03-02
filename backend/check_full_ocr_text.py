"""
检查合同23的完整OCR文本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, Contract
from app.services.baidu_ocr import BaiduOCR

def check_full_text():
    """检查完整OCR文本"""
    db = next(get_db())
    contract = db.query(Contract).filter(Contract.id == 23).first()
    
    if not contract:
        print("合同不存在")
        return
    
    file_path = os.path.join("storage", contract.file_path)
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print("开始OCR识别...")
    ocr = BaiduOCR()
    text = ocr.extract_text_from_file(file_path)
    
    print(f"\nOCR文本总长度: {len(text)} 字符")
    print("\n" + "="*60)
    print("完整OCR文本:")
    print("="*60)
    print(text)
    print("="*60)
    
    # 检查关键词
    keywords = ["产品", "明细", "价格", "金额", "付款", "服务费", "总价", "合计"]
    print("\n关键词检查:")
    for kw in keywords:
        count = text.count(kw)
        if count > 0:
            print(f"  '{kw}': {count} 次")

if __name__ == "__main__":
    check_full_text()
