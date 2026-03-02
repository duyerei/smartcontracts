"""
测试补充协议分析功能
"""
from app.services.baidu_ocr import BaiduOCR
from app.services.llm_service import LLMService
from pathlib import Path
import re
import json

def test_analyze():
    # 找一个PDF文件测试
    storage_path = Path("storage/supplements")
    if not storage_path.exists():
        print("supplements目录不存在")
        return
    
    pdf_files = list(storage_path.glob("*.pdf"))
    if not pdf_files:
        print("没有找到PDF文件")
        return
    
    test_file = pdf_files[0]
    print(f"测试文件: {test_file}")
    
    # 初始化服务
    ocr = BaiduOCR()
    llm = LLMService()
    
    # OCR识别
    print("\n1. OCR识别...")
    try:
        ocr_result = ocr.recognize_pdf(str(test_file), max_pages=2)
        if ocr_result and "pages" in ocr_result:
            ocr_text = "\n".join([page.get("text", "") for page in ocr_result["pages"]])
            print(f"识别成功，文本长度: {len(ocr_text)}")
            print(f"前500字符:\n{ocr_text[:500]}")
        else:
            print("OCR未返回结果")
            return
    except Exception as e:
        print(f"OCR识别失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # LLM提取信息
    print("\n2. LLM提取信息...")
    try:
        prompt = f"""请从以下补充协议文本中提取关键信息：

文本内容：
{ocr_text[:2000]}

请提取：
1. 签订日期（格式：YYYY-MM-DD）
2. 补充协议涉及的金额（仅数字，不含货币符号）

请以JSON格式返回：
{{
    "signed_date": "YYYY-MM-DD",
    "amount": 数字
}}

如果无法识别某项信息，请返回null。"""

        response = llm.chat(prompt)
        print(f"LLM响应:\n{response}")
        
        # 解析JSON
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            info = json.loads(json_match.group())
            print(f"\n解析结果:")
            print(f"  签订日期: {info.get('signed_date')}")
            print(f"  金额: {info.get('amount')}")
        else:
            print("未找到JSON格式的响应")
    except Exception as e:
        print(f"LLM提取失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("补充协议分析功能测试")
    print("=" * 60)
    test_analyze()
