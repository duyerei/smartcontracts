"""
直接测试OCR识别
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.baidu_ocr import BaiduOCR
import fitz  # PyMuPDF

def test_ocr():
    """测试OCR识别"""
    file_path = "storage/contracts/eb7677bb-f4ab-4352-9611-5c63df78c957.pdf"
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print(f"文件路径: {file_path}")
    print(f"文件大小: {os.path.getsize(file_path) / 1024:.2f} KB")
    
    # 检查PDF页数
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        print(f"PDF总页数: {total_pages}")
        doc.close()
    except Exception as e:
        print(f"无法打开PDF: {e}")
        return
    
    # 测试OCR
    print("\n开始OCR识别...")
    ocr = BaiduOCR()
    
    try:
        text = ocr.extract_text_from_file(file_path)
        print(f"\nOCR识别完成")
        print(f"提取文本长度: {len(text)} 字符")
        
        if len(text) < 1000:
            print(f"\n完整文本内容:")
            print(text)
        else:
            print(f"\n文本前500字符:")
            print(text[:500])
            print(f"\n文本后500字符:")
            print(text[-500:])
        
        # 检查关键词
        keywords = ["附件", "产品", "明细", "价格", "软件", "定制", "升级", "支持", "合同"]
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
    test_ocr()
