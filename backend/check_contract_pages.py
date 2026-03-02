"""检查合同18的页面读取情况"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, Contract

db = SessionLocal()
try:
    contract = db.query(Contract).filter(Contract.id == 18).first()
    if contract and contract.raw_text:
        # 统计每一页的标记
        pages = contract.raw_text.split("--- 第")
        print(f"总共识别到 {len(pages)-1} 个页面标记")
        print("\n页面列表:")
        for i, page in enumerate(pages[1:], 1):  # 跳过第一个空元素
            first_line = page.split('\n')[0]
            print(f"  页面 {i}: {first_line}")
            # 检查是否包含"附件"、"明细"、"价格"等关键词
            if any(keyword in page for keyword in ["附件", "明细", "价格", "产品", "费用"]):
                print(f"    ✓ 包含关键内容")
                # 显示前200字符
                content = page[:200].replace('\n', ' ')
                print(f"    内容预览: {content}...")
    else:
        print("合同不存在或无原始文本")
finally:
    db.close()
