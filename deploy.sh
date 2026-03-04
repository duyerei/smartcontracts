#!/bin/bash
# 合同管理系统 - 服务器部署脚本
# 适用于 Rocky Linux 9 + Docker + 1Panel

set -e

echo "========================================="
echo "  AI智能合同管理系统 - 部署脚本"
echo "========================================="

# 1. 检查 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先通过 1Panel 安装 Docker"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安装"
    exit 1
fi

echo "✅ Docker 环境检查通过"

# 2. 检查 .env.production 是否已配置
if [ ! -f backend/.env.production ]; then
    echo "❌ 请先配置 backend/.env.production"
    echo "   cp backend/.env.production.example backend/.env.production"
    echo "   然后编辑填入实际的 API Key 等配置"
    exit 1
fi

if grep -q "CHANGE_ME" backend/.env.production; then
    echo "⚠️  警告: backend/.env.production 中包含未修改的默认值"
    echo "   请确保 JWT_SECRET_KEY 已更换为随机字符串"
    echo "   生成方法: python3 -c \"import secrets; print(secrets.token_urlsafe(64))\""
    read -p "是否继续部署? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 3. 构建并启动
echo ""
echo "🔨 开始构建镜像..."
docker compose build --no-cache

echo ""
echo "🚀 启动服务..."
docker compose up -d

echo ""
echo "⏳ 等待服务启动..."
sleep 5

# 4. 检查服务状态
echo ""
echo "📋 服务状态:"
docker compose ps

echo ""
echo "🔍 后端健康检查:"
if docker compose exec backend curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ 后端服务正常"
else
    echo "   ⚠️  后端服务可能还在启动中，请稍后检查"
    echo "   查看日志: docker compose logs backend"
fi

echo ""
echo "========================================="
echo "  部署完成"
echo "  访问地址: http://服务器IP:8080"
echo "  管理员初始密码查看:"
echo "    docker compose exec backend cat /app/secure/admin_password.txt"
echo "========================================="
