#!/bin/bash

# 上传代码到 GitHub 脚本
# 仓库名称: smart-contracts

echo "=== 上传代码到 GitHub - Smart Contracts ==="
echo ""

# 配置
REPO_NAME="smart-contracts"
BRANCH="main"
VERSION="v1.2.0"

# 1. 检查 .gitignore
echo "=== 步骤 1: 检查 .gitignore 配置 ==="
if grep -q "\.env" .gitignore; then
    echo "✅ .env 已在 .gitignore 中，不会被上传"
else
    echo "⚠️  警告: .env 未在 .gitignore 中"
    echo "正在添加 .env 到 .gitignore..."
    echo ".env" >> .gitignore
    echo "backend/.env" >> .gitignore
fi
echo ""

# 2. 验证 .env 不会被提交
echo "=== 步骤 2: 验证敏感文件不会被提交 ==="
if git check-ignore backend/.env > /dev/null 2>&1; then
    echo "✅ backend/.env 已被忽略"
else
    echo "❌ 警告: backend/.env 可能会被提交！"
    echo "请检查 .gitignore 配置"
    exit 1
fi
echo ""

# 3. 查看将要提交的文件
echo "=== 步骤 3: 查看将要提交的文件 ==="
git status
echo ""
echo "请确认以上文件中没有 .env 文件"
read -p "按 Enter 继续，或 Ctrl+C 取消..."
echo ""

# 4. 添加所有更改（.env 会被自动忽略）
echo "=== 步骤 4: 添加所有更改 ==="
git add .
echo ""

# 5. 再次确认没有 .env 文件
echo "=== 步骤 5: 确认暂存区文件 ==="
if git diff --cached --name-only | grep -q "\.env"; then
    echo "❌ 错误: 发现 .env 文件在暂存区！"
    echo "正在移除..."
    git reset backend/.env 2>/dev/null
    git reset .env 2>/dev/null
    echo "✅ 已移除 .env 文件"
else
    echo "✅ 暂存区中没有 .env 文件"
fi
echo ""

# 6. 提交更改
echo "=== 步骤 6: 提交更改 ==="
git commit -m "feat: 实现付款管理功能及UI优化

主要更新：
1. 付款管理功能
   - 完成后端路由注册（payments.py）
   - 创建前端PaymentList组件
   - 集成到合同详情页面
   - 支持上传付款凭证（PDF、图片、DOC、DOCX）
   - AI自动识别付款时间和金额
   - 支持编辑和删除功能

2. 文件预览修复
   - 修复补充协议和付款凭证预览失败问题
   - 根据文件类型动态设置正确的media_type
   - 改进blob URL清理机制
   - 添加详细的错误处理

3. UI优化
   - 将'查看附件'改为文件名可点击链接
   - 文件名自动显示文件后缀（.pdf、.docx等）
   - 识别超时（2分钟）后显示'未识别'而不是'识别中...'
   - 界面更简洁直观

4. Bug修复
   - 修复file_storage.file_storage错误
   - 修复supplements.py下载接口media_type问题
   - 修复SupplementList.tsx重复代码问题

技术细节：
- 后端：FastAPI + BackgroundTasks异步处理
- 前端：React + TypeScript
- AI识别：OCR + LLM智能提取
- 文件存储：backend/storage/payments/
- 自动刷新：每5秒检查更新"
echo ""

# 7. 创建版本标签
echo "=== 步骤 7: 创建版本标签 $VERSION ==="
git tag -a $VERSION -m "版本 $VERSION - 付款管理功能及UI优化

主要功能：
✅ 付款管理完整功能
✅ 文件预览修复
✅ UI优化和用户体验改进
✅ 识别超时处理
✅ 文件后缀显示

发布日期: $(date '+%Y-%m-%d')"
echo ""

# 8. 检查远程仓库
echo "=== 步骤 8: 检查远程仓库配置 ==="
if git remote | grep -q "origin"; then
    echo "✅ 远程仓库已配置"
    git remote -v
else
    echo "⚠️  未配置远程仓库"
    echo "请输入 GitHub 仓库 URL (例如: https://github.com/username/smart-contracts.git):"
    read REPO_URL
    git remote add origin $REPO_URL
    echo "✅ 已添加远程仓库"
fi
echo ""

# 9. 推送到 GitHub
echo "=== 步骤 9: 推送到 GitHub ==="
echo "正在推送代码到 $BRANCH 分支..."
git push -u origin $BRANCH
echo ""

echo "正在推送标签 $VERSION..."
git push origin $VERSION
echo ""

# 10. 完成
echo "=== 完成！==="
echo ""
echo "✅ 代码已成功上传到 GitHub"
echo "✅ 版本标签 $VERSION 已创建"
echo ""
echo "GitHub 仓库地址:"
git remote get-url origin
echo ""
echo "查看提交历史:"
echo "git log -3 --oneline --decorate"
echo ""
echo "查看所有标签:"
echo "git tag -l"
echo ""
