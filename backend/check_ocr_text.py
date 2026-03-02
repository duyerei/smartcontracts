"""
检查合同的OCR文本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, Contract
from app.services.baidu_ocr import BaiduOCR

def check_ocr(contract_id: int):
    """检查合同的OCR文本"""
    db = next(get_db())
    
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    
    if not contract:
        print(f"合同 {contract_id} 不存在")
        return
    
    print(f"\n{'='*60}")
    print(f"合同ID: {contract.id}")
    print(f"合同编号: {contract.contract_number}")
    print(f"文件路径: {contract.file_path}")
    print(f"{'='*60}\n")
    
    # 构建完整文件路径
    file_path = os.path.join("storage", contract.file_path)
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print(f"文件大小: {os.path.getsize(file_path) / 1024:.2f} KB")
    
    # 读取OCR文本
    print("\n开始OCR识别（这可能需要一些时间）...")
    ocr = BaiduOCR()
    
    try:
        text = ocr.extract_text_from_file(file_path)
        
        print(f"\nOCR识别完成")
        print(f"提取文本长度: {len(text)} 字符")
        
        if len(text) < 2000:
            print(f"\n完整OCR文本:")
            print("="*60)
            print(text)
            print("="*60)
        else:
            print(f"\nOCR文本前1000字符:")
            print("="*60)
            print(text[:1000])
            print("="*60)
            print(f"\nOCR文本后1000字符:")
            print("="*60)
            print(text[-1000:])
            print("="*60)
        
        # 检查关键词
        keywords = ["附件", "产品", "明细", "价格", "软件", "服务", "合同", "甲方", "乙方"]
        print(f"\n关键词检查:")
        for kw in keywords:
            count = text.count(kw)
            if count > 0:
                print(f"  '{kw}': {count} 次")
        
    except Exception as e:
        print(f"OCR识别失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 检查最新的合同
    contract_id = 23
    print("注意：这将调用百度OCR API，可能需要1-2分钟")
    check_ocr(contract_id)
