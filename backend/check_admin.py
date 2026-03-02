#!/usr/bin/env python3
"""检查管理员账号状态"""
import sqlite3
import sys

try:
    conn = sqlite3.connect('contracts.db')
    cursor = conn.cursor()
    
    # 检查users表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("❌ users表不存在，数据库未初始化")
        print("✅ 解决方案：启动服务器会自动创建表和管理员账号")
        sys.exit(0)
    
    # 查询管理员账号
    cursor.execute("SELECT id, username, real_name, role, is_active, created_at FROM users WHERE role='admin'")
    admins = cursor.fetchall()
    
    if not admins:
        print("❌ 没有找到管理员账号")
        print("✅ 解决方案：启动服务器会自动创建管理员账号")
    else:
        print("✅ 找到管理员账号：")
        for admin in admins:
            print(f"  ID: {admin[0]}")
            print(f"  用户名: {admin[1]}")
            print(f"  真实姓名: {admin[2]}")
            print(f"  角色: {admin[3]}")
            print(f"  状态: {'激活' if admin[4] else '禁用'}")
            print(f"  创建时间: {admin[5]}")
            print()
        
        print("⚠️  密码信息：")
        print("  - 如果是旧账号，密码可能是: admin123")
        print("  - 如果是新账号，密码保存在: secure/admin_password.txt")
        print("  - 建议：登录后立即修改密码")
    
    conn.close()
    
except Exception as e:
    print(f"❌ 错误: {e}")
    print("✅ 解决方案：确保contracts.db文件存在且可访问")
