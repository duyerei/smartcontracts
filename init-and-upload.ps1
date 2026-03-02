# 初始化 Git 仓库并上传到 GitHub
# 适用于首次使用 Git 的项目

Write-Host "=== 初始化 Git 仓库并上传到 GitHub ===" -ForegroundColor Cyan
Write-Host ""

# 配置
$VERSION = "v1.2.0"
$BRANCH = "main"

# 步骤 1: 初始化 Git 仓库
Write-Host "=== 步骤 1: 初始化 Git 仓库 ===" -ForegroundColor Yellow
if (Test-Path ".git") {
    Write-Host "✅ Git 仓库已存在" -ForegroundColor Green
} else {
    Write-Host "正在初始化 Git 仓库..." -ForegroundColor Cyan
    git init
    Write-Host "✅ Git 仓库初始化完成" -ForegroundColor Green
}
Write-Host ""

# 步骤 2: 配置 Git 用户信息（如果未配置）
Write-Host "=== 步骤 2: 配置 Git 用户信息 ===" -ForegroundColor Yellow
$userName = git config user.name
$userEmail = git config user.email

if (-not $userName) {
    $userName = Read-Host "请输入你的 Git 用户名"
    git config user.name $userName
}
if (-not $userEmail) {
    $userEmail = Read-Host "请输入你的 Git 邮箱"
    git config user.email $userEmail
}
Write-Host "✅ Git 用户: $userName <$userEmail>" -ForegroundColor Green
Write-Host ""

# 步骤 3: 确保 .gitignore 正确配置
Write-Host "=== 步骤 3: 检查 .gitignore 配置 ===" -ForegroundColor Yellow
if (Test-Path ".gitignore") {
    Write-Host "✅ .gitignore 文件已存在" -ForegroundColor Green
    
    # 确保包含必要的忽略规则
    $gitignoreContent = Get-Content ".gitignore" -Raw
    $needsUpdate = $false
    
    if ($gitignoreContent -notmatch "backend/\.env") {
        Add-Content -Path ".gitignore" -Value "`nbackend/.env"
        $needsUpdate = $true
    }
    if ($gitignoreContent -notmatch "^\.env$") {
        Add-Content -Path ".gitignore" -Value ".env"
        $needsUpdate = $true
    }
    
    if ($needsUpdate) {
        Write-Host "✅ 已更新 .gitignore 配置" -ForegroundColor Green
    }
} else {
    Write-Host "⚠️  .gitignore 文件不存在，正在创建..." -ForegroundColor Yellow
    # 创建基本的 .gitignore
    @"
# 环境变量文件（包含敏感信息）
.env
backend/.env
frontend/.env.local

# Python
__pycache__/
*.py[cod]
*.pyc
.Python
venv/
.venv/
*.db
*.sqlite

# Node
node_modules/
npm-debug.log*

# IDE
.vscode/
.idea/
*.swp

# 存储文件
storage/
backend/storage/
backend/app/storage/

# 日志
*.log

# 临时文件
*.tmp
.DS_Store
"@ | Out-File -FilePath ".gitignore" -Encoding UTF8
    Write-Host "✅ 已创建 .gitignore 文件" -ForegroundColor Green
}
Write-Host ""

# 步骤 4: 验证敏感文件不会被提交
Write-Host "=== 步骤 4: 验证敏感文件 ===" -ForegroundColor Yellow
if (Test-Path "backend/.env") {
    Write-Host "✅ 发现 backend/.env 文件" -ForegroundColor Green
    $checkIgnore = git check-ignore backend/.env 2>&1
    if ($checkIgnore -match "backend/.env") {
        Write-Host "✅ backend/.env 已被 .gitignore 忽略" -ForegroundColor Green
    } else {
        Write-Host "⚠️  backend/.env 未被忽略，请检查 .gitignore" -ForegroundColor Yellow
    }
} else {
    Write-Host "ℹ️  未找到 backend/.env 文件" -ForegroundColor Cyan
}
Write-Host ""

# 步骤 5: 查看将要提交的文件
Write-Host "=== 步骤 5: 查看将要提交的文件 ===" -ForegroundColor Yellow
git status
Write-Host ""
Write-Host "⚠️  请仔细检查上面的文件列表，确认没有敏感文件（如 .env、.db 等）" -ForegroundColor Yellow
$confirm = Read-Host "确认继续? (y/n)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "❌ 已取消操作" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit
}
Write-Host ""

# 步骤 6: 添加所有文件
Write-Host "=== 步骤 6: 添加文件到暂存区 ===" -ForegroundColor Yellow
git add .
Write-Host "✅ 文件已添加到暂存区" -ForegroundColor Green
Write-Host ""

# 步骤 7: 再次确认暂存区
Write-Host "=== 步骤 7: 确认暂存区文件 ===" -ForegroundColor Yellow
$stagedFiles = git diff --cached --name-only
Write-Host "暂存区文件数量: $($stagedFiles.Count)" -ForegroundColor Cyan

# 检查是否有敏感文件
$sensitiveFiles = $stagedFiles | Where-Object { $_ -match "\.(env|db|sqlite)$" }
if ($sensitiveFiles) {
    Write-Host "❌ 警告: 发现敏感文件在暂存区!" -ForegroundColor Red
    $sensitiveFiles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    $removeFiles = Read-Host "是否移除这些文件? (y/n)"
    if ($removeFiles -eq "y" -or $removeFiles -eq "Y") {
        $sensitiveFiles | ForEach-Object { git reset $_ }
        Write-Host "✅ 已移除敏感文件" -ForegroundColor Green
    }
} else {
    Write-Host "✅ 暂存区中没有敏感文件" -ForegroundColor Green
}
Write-Host ""

# 步骤 8: 首次提交
Write-Host "=== 步骤 8: 创建首次提交 ===" -ForegroundColor Yellow
$commitMessage = @"
feat: 实现付款管理功能及UI优化

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

技术栈：
- 后端：FastAPI + BackgroundTasks + SQLAlchemy
- 前端：React + TypeScript + Tailwind CSS
- AI：百度OCR + 千帆大模型
- 数据库：SQLite
"@

git commit -m $commitMessage
Write-Host "✅ 首次提交完成" -ForegroundColor Green
Write-Host ""

# 步骤 9: 创建版本标签
Write-Host "=== 步骤 9: 创建版本标签 $VERSION ===" -ForegroundColor Yellow
$tagMessage = @"
版本 $VERSION - 付款管理功能及UI优化

主要功能：
✅ 付款管理完整功能
✅ 文件预览修复
✅ UI优化和用户体验改进
✅ 识别超时处理
✅ 文件后缀显示

发布日期: $(Get-Date -Format 'yyyy-MM-dd')
"@

git tag -a $VERSION -m $tagMessage
Write-Host "✅ 版本标签 $VERSION 已创建" -ForegroundColor Green
Write-Host ""

# 步骤 10: 配置远程仓库
Write-Host "=== 步骤 10: 配置远程仓库 ===" -ForegroundColor Yellow
$remotes = git remote
if ($remotes -contains "origin") {
    Write-Host "✅ 远程仓库已配置" -ForegroundColor Green
    git remote -v
    Write-Host ""
    $changeRemote = Read-Host "是否更改远程仓库地址? (y/n)"
    if ($changeRemote -eq "y" -or $changeRemote -eq "Y") {
        $repoUrl = Read-Host "请输入新的 GitHub 仓库 URL"
        git remote set-url origin $repoUrl
        Write-Host "✅ 远程仓库地址已更新" -ForegroundColor Green
    }
} else {
    Write-Host "请输入 GitHub 仓库 URL" -ForegroundColor Cyan
    Write-Host "格式: https://github.com/用户名/smart-contracts.git" -ForegroundColor Gray
    $repoUrl = Read-Host "仓库 URL"
    git remote add origin $repoUrl
    Write-Host "✅ 远程仓库已配置" -ForegroundColor Green
}
Write-Host ""

# 步骤 11: 推送到 GitHub
Write-Host "=== 步骤 11: 推送到 GitHub ===" -ForegroundColor Yellow
Write-Host "正在推送代码到 $BRANCH 分支..." -ForegroundColor Cyan
git branch -M $BRANCH
git push -u origin $BRANCH

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 代码推送成功" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "正在推送标签 $VERSION..." -ForegroundColor Cyan
    git push origin $VERSION
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 标签推送成功" -ForegroundColor Green
    }
} else {
    Write-Host "❌ 推送失败，请检查网络连接和仓库权限" -ForegroundColor Red
}
Write-Host ""

# 步骤 12: 完成
Write-Host "=== 完成！===" -ForegroundColor Green
Write-Host ""
Write-Host "✅ Git 仓库已初始化" -ForegroundColor Green
Write-Host "✅ 代码已提交到本地仓库" -ForegroundColor Green
Write-Host "✅ 版本标签 $VERSION 已创建" -ForegroundColor Green
Write-Host "✅ 代码已推送到 GitHub" -ForegroundColor Green
Write-Host ""
Write-Host "GitHub 仓库地址:" -ForegroundColor Cyan
git remote get-url origin
Write-Host ""
Write-Host "查看提交历史:" -ForegroundColor Cyan
Write-Host "  git log --oneline --decorate" -ForegroundColor Gray
Write-Host ""
Write-Host "查看所有标签:" -ForegroundColor Cyan
Write-Host "  git tag -l" -ForegroundColor Gray
Write-Host ""
Write-Host "查看远程仓库:" -ForegroundColor Cyan
Write-Host "  git remote -v" -ForegroundColor Gray
Write-Host ""

Read-Host "按 Enter 退出"
