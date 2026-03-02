#!/usr/bin/env python3
"""测试登录接口"""
import requests
import json

# 测试登录
url = "http://localhost:8000/api/v1/auth/login"
data = {
    "username": "admin",
    "password": "admin123"
}

print("测试登录接口...")
print(f"URL: {url}")
print(f"数据: {data}")
print("-" * 50)

try:
    response = requests.post(
        url,
        data=data,  # OAuth2PasswordRequestForm 使用 form data
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    print(f"响应内容: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ 登录成功！")
        result = response.json()
        print(f"Token: {result.get('access_token', 'N/A')[:50]}...")
        print(f"用户: {result.get('user', {})}")
    else:
        print(f"\n❌ 登录失败！")
        try:
            error = response.json()
            print(f"错误详情: {json.dumps(error, indent=2, ensure_ascii=False)}")
        except:
            print(f"错误内容: {response.text}")
            
except Exception as e:
    print(f"❌ 请求失败: {e}")
    import traceback
    traceback.print_exc()
