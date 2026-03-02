"""
测试通过API重新解析合同23
"""
import requests
import time

def test_reparse():
    contract_id = 23
    base_url = "http://localhost:8000/api/v1"
    
    print(f"触发重新解析合同 {contract_id}...")
    response = requests.post(f"{base_url}/contracts/{contract_id}/reparse")
    print(f"响应: {response.json()}")
    
    print("\n等待10秒后检查结果...")
    time.sleep(10)
    
    # 检查合同信息
    response = requests.get(f"{base_url}/contracts/{contract_id}")
    contract = response.json()
    
    print(f"\n合同信息:")
    print(f"  合同名称: {contract['title']}")
    print(f"  甲方乙方: {contract['parties']}")
    print(f"  签订日期: {contract.get('signed_date', 'None')}")
    print(f"  摘要长度: {len(contract.get('summary', ''))}")
    print(f"\n摘要前500字符:")
    print(contract.get('summary', '')[:500])

if __name__ == "__main__":
    test_reparse()
