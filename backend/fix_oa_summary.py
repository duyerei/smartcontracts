"""
清除 raw_data 中错误存入的 PDF 原文摘要（合同摘要字段）
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from app.database import SessionLocal, Contract

db = SessionLocal()
try:
    contracts = db.query(Contract).filter(Contract.raw_data != None).all()
    fixed = 0
    for c in contracts:
        try:
            raw = json.loads(c.raw_data)
        except:
            continue
        summary = raw.get('合同摘要', '')
        # 判断是否是PDF原文（超过200字，或包含典型的OCR原文特征）
        if summary and (
            len(summary) > 200 or
            '--- 第1页 ---' in summary or
            '打印日期' in summary or
            '基本信息\n主题' in summary or
            summary.startswith('[已读取')
        ):
            print(f"合同 {c.id} ({c.contract_number}): 清除错误摘要（前50字）: {summary[:50]}")
            del raw['合同摘要']
            c.raw_data = json.dumps(raw, ensure_ascii=False)
            fixed += 1
    db.commit()
    print(f"\n共修复 {fixed} 条合同")
finally:
    db.close()
