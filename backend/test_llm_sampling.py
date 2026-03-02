"""测试LLM文本采样策略"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract

db = SessionLocal()
try:
    contract = db.query(Contract).filter(Contract.id == 18).first()
    if contract and contract.raw_text:
        text = contract.raw_text
        
        print(f"原始文本长度: {len(text)} 字符")
        print("\n" + "="*80)
        
        # 模拟新的LLM采样逻辑
        if len(text) <= 5000:
            text_sample = text
            print("文本较短，全部使用")
        else:
            text_head = text[:2000]
            text_tail = text[-1500:]
            
            # 查找包含关键词和具体数字的段落
            key_content = ""
            
            # 按页面分割文本
            pages = text.split("--- 第")
            print(f"总共 {len(pages)-1} 个页面\n")
            
            # 优先查找"附件"+"价格数字"
            for i, page in enumerate(pages):
                if ("附件" in page or "清单" in page) and ("元/" in page or "元，" in page or "价格" in page):
                    print(f"✓ 找到包含具体价格的附件页面 {i}:")
                    first_line = page.split('\n')[0] if '\n' in page else page[:50]
                    print(f"  页面标识: {first_line}")
                    key_content = page[:1500]
                    print(f"  提取长度: {len(key_content)} 字符")
                    print(f"\n  内容预览（前300字符）:")
                    print("  " + "-"*76)
                    print("  " + key_content[:300].replace('\n', '\n  '))
                    break
            
            if not key_content:
                print("未找到包含具体价格的附件页面")
            
            print(f"\n采样文本总长度: {len(text_head)} + {len(key_content)} + {len(text_tail)} = {len(text_head) + len(key_content) + len(text_tail)} 字符")
    else:
        print("合同不存在或无原始文本")
finally:
    db.close()
