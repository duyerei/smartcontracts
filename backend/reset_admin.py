#!/usr/bin/env python3
"""重置管理员账号"""
import sqlite3
import secrets
from pathlib import Path
from datetime import datetime

# 导入密码哈希函数
import sys
sys.path.insert(0, '.')
from app.auth import hash_password

try:
    conn = sqlite3.connect('contracts.db')
    cursor = conn.cursor()
    
    # 删除旧的管理员账号
    cursor.execute("DELETE FROM users WHERE username='admin'")
    print("✅ 已删除旧的管理员账号")
    
    # 生成新的强密码
    random_password = secrets.token_urlsafe(16)
    hashed_password = hash_password(random_password)
    
    # 创建新的管理员账号
    cursor.execute("""
        INSERT INTO users (username, hashed_password, real_name, role, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'admin',
        hashed_password,
        '系统管理员',
        'admin',
        True,
        datetime.now(),
        datetime.now()
    ))
    
    conn.commit()
    print("✅ 已创建新的管理员账号")
    
    # 保存密码到文件
    secure_dir = Path("./secure")
    secure_dir.mkdir(exist_ok=True)
    password_file = secure_dir / "admin_password.txt"
    
    with open(password_file, "w", encoding="utf-8") as f:
        f.write(f"管理员账号: admin\n")
        f.write(f"初始密码: {random_password}\n")
        f.write(f"创建时间: {datetime.now().isoformat()}\n")
        f.write(f"\n重要提示：\n")
        f.write(f"1. 请立即登录并修改密码\n")
        f.write(f"2. 修改密码后请删除此文件\n")
        f.write(f"3. 此文件包含敏感信息，请妥善保管\n")
    
    print(f"✅ 密码已保存到: {password_file.absolute()}")
    print(f"\n📋 登录信息：")
    print(f"   用户名: admin")
    print(f"   密码: {random_password}")
    print(f"\n⚠️  请立即登录并修改密码！")
    
    conn.close()
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
