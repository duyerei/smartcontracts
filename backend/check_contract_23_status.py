import requests

r = requests.get('http://localhost:8000/api/v1/contracts/23')
c = r.json()
print(f'合同名称: {c["title"]}')
print(f'甲方乙方: {c["parties"]}')
print(f'签订日期: {c.get("signed_date", "None")}')
print(f'摘要长度: {len(c.get("summary", ""))}')
print(f'\n摘要前500字符:')
print(c.get('summary', '')[:500])
