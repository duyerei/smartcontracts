"""
测试补充协议上传功能
"""
import requests
import os
from pathlib import Path

# 配置
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录获取token"""
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={
            "username": USERNAME,
            "password": PASSWORD
        }
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    else:
        print(f"登录失败: {response.status_code}")
        print(response.text)
        return None

def list_contracts(token):
    """获取合同列表"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/v1/contracts", headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("contracts", [])
    return []

def list_supplements(token, contract_id):
    """获取补充协议列表"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/v1/supplements/{contract_id}/list",
        headers=headers
    )
    print(f"\n获取补充协议列表 (合同ID: {contract_id}):")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        supplements = data.get("supplements", [])
        print(f"找到 {len(supplements)} 个补充协议:")
        for s in supplements:
            print(f"  - ID: {s['id']}, 标题: {s['title']}, 签订时间: {s.get('signed_date', '未设置')}")
        return supplements
    else:
        print(f"错误: {response.text}")
        return []

def upload_supplement(token, contract_id, file_path, title=None, signed_date=None):
    """上传补充协议"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 准备文件
    files = {"file": open(file_path, "rb")}
    data = {}
    if title:
        data["title"] = title
    if signed_date:
        data["signed_date"] = signed_date
    
    response = requests.post(
        f"{BASE_URL}/api/v1/supplements/{contract_id}/upload",
        headers=headers,
        files=files,
        data=data
    )
    
    print(f"\n上传补充协议:")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"上传成功!")
        print(f"  - ID: {data['id']}")
        print(f"  - 标题: {data['title']}")
        print(f"  - 文件大小: {data['file_size']} 字节")
        return data
    else:
        print(f"上传失败: {response.text}")
        return None

def download_supplement(token, supplement_id, output_path):
    """下载补充协议"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/v1/supplements/{supplement_id}/download",
        headers=headers
    )
    
    print(f"\n下载补充协议 (ID: {supplement_id}):")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"下载成功，保存到: {output_path}")
        return True
    else:
        print(f"下载失败: {response.text}")
        return False

def delete_supplement(token, supplement_id):
    """删除补充协议"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(
        f"{BASE_URL}/api/v1/supplements/{supplement_id}",
        headers=headers
    )
    
    print(f"\n删除补充协议 (ID: {supplement_id}):")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print("删除成功!")
        return True
    else:
        print(f"删除失败: {response.text}")
        return False

def main():
    print("=" * 60)
    print("补充协议功能测试")
    print("=" * 60)
    
    # 1. 登录
    print("\n1. 登录...")
    token = login()
    if not token:
        print("登录失败，测试终止")
        return
    print(f"登录成功，Token: {token[:20]}...")
    
    # 2. 获取合同列表
    print("\n2. 获取合同列表...")
    contracts = list_contracts(token)
    if not contracts:
        print("没有找到合同，测试终止")
        return
    
    # 使用第一个合同进行测试
    contract = contracts[0]
    contract_id = contract["id"]
    print(f"使用合同: ID={contract_id}, 标题={contract.get('title', '未命名')}")
    
    # 3. 查看现有补充协议
    print("\n3. 查看现有补充协议...")
    existing_supplements = list_supplements(token, contract_id)
    
    # 4. 查找一个PDF文件用于测试上传
    print("\n4. 准备测试文件...")
    storage_path = Path("storage/contracts")
    if storage_path.exists():
        pdf_files = list(storage_path.glob("*.pdf"))
        if pdf_files:
            test_file = pdf_files[0]
            print(f"使用测试文件: {test_file}")
            
            # 5. 上传补充协议
            print("\n5. 上传补充协议...")
            uploaded = upload_supplement(
                token,
                contract_id,
                str(test_file),
                title="测试补充协议",
                signed_date="2026-03-01"
            )
            
            if uploaded:
                supplement_id = uploaded["id"]
                
                # 6. 再次查看补充协议列表
                print("\n6. 验证上传结果...")
                list_supplements(token, contract_id)
                
                # 7. 下载补充协议
                print("\n7. 测试下载功能...")
                download_path = Path("storage/temp") / f"downloaded_{supplement_id}.pdf"
                download_path.parent.mkdir(parents=True, exist_ok=True)
                download_supplement(token, supplement_id, str(download_path))
                
                # 8. 删除测试的补充协议
                print("\n8. 清理测试数据...")
                if input("\n是否删除测试上传的补充协议? (y/n): ").lower() == 'y':
                    delete_supplement(token, supplement_id)
                    
                    # 9. 验证删除结果
                    print("\n9. 验证删除结果...")
                    list_supplements(token, contract_id)
        else:
            print("storage/contracts 目录中没有PDF文件")
    else:
        print("storage/contracts 目录不存在")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
