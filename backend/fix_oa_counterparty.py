"""修复所有OA合同的对方联系人/地址/电话字段（从raw_data复合key中解析）"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import SessionLocal, Contract

def parse_counterparty_from_raw(raw_data: dict, counterparty_name: str = '') -> dict:
    result = {'contact': '', 'address': '', 'phone': ''}
    if not raw_data:
        return result
    for key in raw_data.keys():
        if key.endswith('_2'):
            continue
        if '对方名称' in key and '对方经办人' in key and '地址' in key and '电话' in key:
            brace_idx = key.find('{1}')
            data_str = key[brace_idx + 3:].strip() if brace_idx >= 0 else key
            stripped = re.sub(r'^\d+\s*', '', data_str).strip()
            # 1. 电话在末尾
            phone_match = re.search(r'(\d{7,13})\s*$', stripped)
            phone = phone_match.group(1) if phone_match else ''
            without_phone = stripped[:stripped.rfind(phone)].strip() if phone else stripped
            # 2. 切掉公司名，剩余是"经办人+地址"
            after_company = ''
            if counterparty_name and counterparty_name in without_phone:
                after_company = without_phone[without_phone.index(counterparty_name) + len(counterparty_name):].strip()
            else:
                co_match = re.match(r'^(.+(?:公司|集团|有限|股份|机构|中心|部门|局|院|所))\s*(.*)', without_phone)
                if co_match:
                    after_company = co_match.group(2).strip()
            if not after_company:
                result = {'contact': '', 'address': '', 'phone': phone}
                break
            # 3. 用已知省市名列表定位地址起点，避免误匹配姓名中的字
            known_regions = [
                '北京市', '上海市', '天津市', '重庆市',
                '广东省', '广州市', '深圳市', '佛山市', '珠海市', '东莞市', '惠州市', '中山市',
                '浙江省', '杭州市', '宁波市', '温州市',
                '江苏省', '南京市', '苏州市', '无锡市',
                '山东省', '济南市', '青岛市',
                '四川省', '成都市',
                '湖北省', '武汉市',
                '湖南省', '长沙市',
                '河南省', '郑州市',
                '河北省', '石家庄市',
                '陕西省', '西安市',
                '甘肃省', '兰州市',
                '云南省', '昆明市',
                '贵州省', '贵阳市',
                '福建省', '福州市', '厦门市',
                '安徽省', '合肥市',
                '江西省', '南昌市',
                '辽宁省', '沈阳市', '大连市',
                '吉林省', '长春市',
                '黑龙江省', '哈尔滨市',
                '内蒙古', '新疆', '西藏', '宁夏', '广西', '海南省',
            ]
            addr_idx = -1
            for region in known_regions:
                idx = after_company.find(region)
                if idx >= 0 and (addr_idx < 0 or idx < addr_idx):
                    addr_idx = idx
            if addr_idx > 0:
                contact = after_company[:addr_idx].strip()
                address = after_company[addr_idx:].strip()
            elif addr_idx == 0:
                contact = ''
                address = after_company.strip()
            else:
                # 没找到省市名，尝试路/街/道
                addr_start2 = re.search(r'[\u4e00-\u9fa5]{1,10}(?:路|街|道|大道)', after_company)
                if addr_start2:
                    contact = after_company[:addr_start2.start()].strip()
                    address = after_company[addr_start2.start():].strip()
                else:
                    contact = after_company
                    address = ''
            result = {'contact': contact, 'address': address, 'phone': phone}
            break
    return result

db = SessionLocal()
try:
    contracts = db.query(Contract).filter(Contract.source == 'oa_import').all()
    updated = 0
    for c in contracts:
        if not c.raw_data:
            continue
        try:
            raw = json.loads(c.raw_data)
        except:
            continue
        cp = parse_counterparty_from_raw(raw, c.counterparty or '')
        changed = False
        if cp['contact'] or cp['address'] or cp['phone']:
            print(f"ID={c.id} {c.title[:30]}")
            print(f"  联系人: {repr(c.counterparty_contact)} -> {repr(cp['contact'])}")
            print(f"  地址:   {repr(c.counterparty_address)} -> {repr(cp['address'])}")
            print(f"  电话:   {repr(cp['phone'])}")
            if cp['contact']:
                c.counterparty_contact = cp['contact']
            if cp['address']:
                c.counterparty_address = cp['address']
            raw['_counterparty_phone'] = cp['phone']
            changed = True
        # 补充 doc_create_time（申请时间）
        if not raw.get('doc_create_time') and c.signed_date:
            raw['doc_create_time'] = c.signed_date.strftime('%Y-%m-%d')
            changed = True
        if changed:
            c.raw_data = json.dumps(raw, ensure_ascii=False)
            updated += 1
    db.commit()
    print(f"\n✓ 共更新 {updated} 条合同")
finally:
    db.close()
