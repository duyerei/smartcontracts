"""直接调用重解析逻辑更新合同73金额"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, Contract
from app.services import llm_service
import re
from typing import Optional

def _cn_amount_to_float(cn_str: str) -> Optional[float]:
    cn_str = cn_str.replace("整","").replace("元","").replace("人民币","").strip()
    cn_num = {'零':0,'壹':1,'贰':2,'叁':3,'肆':4,'伍':5,'陆':6,'柒':7,'捌':8,'玖':9,
              '一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    cn_unit = {'拾':10,'佰':100,'仟':1000,'千':1000,'万':10000,'亿':100000000,'十':10,'百':100}
    if not any(c in cn_num or c in cn_unit for c in cn_str):
        return None
    total=0; current=0; wan_part=0
    for char in cn_str:
        if char in cn_num: current=cn_num[char]
        elif char in cn_unit:
            unit=cn_unit[char]
            if unit==10000: wan_part=(wan_part+total+(current if current else 0))*unit; total=0; current=0
            elif unit==100000000: wan_part=(wan_part+total+current)*unit; total=0; current=0
            else:
                if current==0 and unit==10: current=1
                total+=current*unit; current=0
    total+=current; result=wan_part+total
    return float(result) if result>0 else None

def parse_amount(s):
    s = str(s).strip()
    wan = re.search(r'([\d]+\.?\d*)\s*万', s.replace(',',''))
    if wan:
        return float(wan.group(1)) * 10000
    clean = s.replace(",","").replace("，","").replace("¥","").replace("￥","").replace("人民币","").replace("元","")
    nums = re.findall(r'[\d]+\.?\d*', clean)
    if nums:
        return float(nums[0])
    return _cn_amount_to_float(s)

db = SessionLocal()
try:
    contract = db.query(Contract).filter(Contract.id == 73).first()
    if not contract:
        print("合同73不存在")
    else:
        print(f"当前金额: {contract.amount}")
        raw_text = contract.raw_text
        if not raw_text:
            print("没有raw_text，无法解析")
        else:
            llm_result = llm_service.llm_service.parse_contract_with_llm(raw_text)
            amount_val = (
                llm_result.get("服务费用总额") or llm_result.get("合同金额") or
                llm_result.get("合同标额") or llm_result.get("合同总金额") or
                llm_result.get("合同价款") or llm_result.get("总金额") or ""
            )
            print(f"LLM金额字段: {repr(amount_val)}")
            parsed = parse_amount(amount_val) if amount_val else None
            print(f"解析结果: {parsed}")
            if parsed:
                contract.amount = parsed
                db.commit()
                print(f"✓ 已更新金额为: {parsed}")
            else:
                print("解析失败，未更新")
finally:
    db.close()
