"""
从 raw_data 中文字段补填数据库字段（修复历史数据）
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(__file__))
from app.database import SessionLocal, Contract

CN_FIELD_MAP = {
    '甲方': 'company',
    '乙方': 'counterparty',
    '申请人': 'applicant',
    '申请人姓名': 'applicant',
    '申请部门': 'department',
    '发起部门': 'department',
    '付款方式': 'payment_type',
    '合同份数': 'copies',
}

db = SessionLocal()
try:
    contracts = db.query(Contract).filter(Contract.raw_data != None).all()
    fixed = 0
    for c in contracts:
        try:
            raw = json.loads(c.raw_data)
        except:
            continue
        changed = False
        for cn_key, db_field in CN_FIELD_MAP.items():
            val = raw.get(cn_key, '')
            if val and str(val).lower() not in ('null', 'none', ''):
                current = getattr(c, db_field, None)
                if not current:
                    setattr(c, db_field, str(val))
                    print(f"合同 {c.id} ({c.contract_number}): {db_field} = {val}")
                    changed = True
        # 清除 raw_data 里的 summary 原文
        if 'summary' in raw:
            s = raw['summary']
            if len(s) > 200 or '--- 第1页 ---' in s or '打印日期' in s or s.startswith('[已读取'):
                del raw['summary']
                c.raw_data = json.dumps(raw, ensure_ascii=False)
                print(f"合同 {c.id}: 清除 raw_data.summary 原文")
                changed = True
        # 修复 amount
        if not c.amount:
            amt_raw = raw.get('amount') or raw.get('合同金额', '')
            if amt_raw:
                nums = re.findall(r'\d+\.?\d*', str(amt_raw).replace(',', ''))
                if nums:
                    try:
                        c.amount = float(nums[0])
                        print(f"合同 {c.id}: amount = {c.amount}")
                        changed = True
                    except:
                        pass
        if changed:
            fixed += 1
    db.commit()
    print(f"\n共修复 {fixed} 条合同")
finally:
    db.close()
