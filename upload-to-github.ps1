# PowerShell 脚本 - 上传代码到 GitHub
# 仓库名称: smart-contracts

Write-Host "=== 上传代码到 GitHub - Smart Contracts ===" -ForegroundColor Cyan
Write-Host ""

# 配置
$REPO_NAME = "smart-contracts"
$BRANCH = "main"
$VERSION = "v1.2.0"

# 1. 检查 .gitignore
Write-Host "=== 步骤 1: 检查 .gitignore 配置 ===" -ForegroundColor Yellow
if (Select-String -Path ".gitignore" -Pattern "\.env" -Quiet) {
    Write-Host "✅ .env 已在 .gitignore 中，不会被上传" -ForegroundColor Green
} else {
    Write-Host "⚠️  警告: .env 未在 .gitignore 中" -ForegroundColor Red
    Write-Host "正在添加 .env 到 .gitignore..."
    Add-Content -Path ".gitignore" -Value ".env"
    Add-Content -Path ".gitignore" -Value "backend/.env"
}
Write-Host ""

# 2. 验证 .env 不会被提交
Write-Host "=== 步骤 2: 验证敏感文件不会被提交 ===" -ForegroundColor Yellow
$checkIgnore = git check-ignore backend/.env 2>&1
if ($checkIgnore -match "backend/.env") {
    Write-Host "✅ backend/.env 已被忽略" -ForegroundColor Green
} else {
    Write-Host "❌ 警告: backend/.env 可能会被提交！" -ForegroundColor Red
    Write-Host "请检查 .gitignore 配置"
    Read-Host "按 Enter 继续"
}
Write-Host ""

# 3. 查看将要提交的文件
Write-Host "=== 步骤 3: 查看将要提交的文件 ===" -ForegroundColor Yellow
git status
Write-Host ""
Write-Host "请确认以上文件中没有 .env 文件" -ForegroundColor Cyan
Read-Host "按 Enter 继续，或 Ctrl+C 取消"
Write-Host ""

# 4. 添加所有更改
Write-Host "=== 步骤 4: 添加所有更改 ===" -ForegroundColor Yellow
git add .
Write-Host ""

# 5. 确认暂存区文件
Write-Host "=== 步骤 5: 确认暂存区文件 ===" -ForegroundColor Yellow
$stagedFiles = git diff --cached --name-only
if ($stagedFiles -match "\.env") {
    Write-Host "❌ 错误: 发现 .env 文件在暂存区！" -ForegroundColor Red
    Write-Host "正在移除..."
    git reset backend/.env 2>$null
    git reset .env 2>$null
    Write-Host "✅ 已移除 .env 文件" -ForegroundColor Green
} else {
    Write-Host "✅ 暂存区中没有 .env 文件" -ForegroundColor Green
}
Write-Host ""

# 6. 提交更改
Write-Host "=== 步骤 6: 提交更改 ===" -ForegroundColor Yellow
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

技术细节：
- 后端：FastAPI + BackgroundTasks异步处理
- 前端：React + TypeScript
- AI识别：OCR + LLM智能提取
- 文件存储：backend/storage/payments/
- 自动刷新：每5秒检查更新
"@

git commit -m $commitMessage
Write-Host ""

# 7. 创建版本标签
Write-Host "=== 步骤 7: 创建版本标签 $VERSION ===" -ForegroundColor Yellow
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
Write-Host ""

# 8. 检查远程仓库
Write-Host "=== 步骤 8: 检查远程仓库配置 ===" -ForegroundColor Yellow
$remotes = git remote
if ($remotes -contains "origin") {
    Write-Host "✅ 远程仓库已配置" -ForegroundColor Green
    git remote -v
} else {
    Write-Host "⚠️  未配置远程仓库" -ForegroundColor Yellow
    $repoUrl = Read-Host "请输入 GitHub 仓库 URL (例如: https://github.com/username/smart-contracts.git)"
    git remote add origin $repoUrl
    Write-Host "✅ 已添加远程仓库" -ForegroundColor Green
}
Write-Host ""

# 9. 推送到 GitHub
Write-Host "=== 步骤 9: 推送到 GitHub ===" -ForegroundColor Yellow
Write-Host "正在推送代码到 $BRANCH 分支..." -ForegroundColor Cyan
git push -u origin $BRANCH
Write-Host ""

Write-Host "正在推送标签 $VERSION..." -ForegroundColor Cyan
git push origin $VERSION
Write-Host ""

# 10. 完成
Write-Host "=== 完成！===" -ForegroundColor Green
Write-Host ""
Write-Host "✅ 代码已成功上传到 GitHub" -ForegroundColor Green
Write-Host "✅ 版本标签 $VERSION 已创建" -ForegroundColor Green
Write-Host ""
Write-Host "GitHub 仓库地址:" -ForegroundColor Cyan
git remote get-url origin
Write-Host ""
Write-Host "查看提交历史:" -ForegroundColor Cyan
Write-Host "git log -3 --oneline --decorate"
Write-Host ""
Write-Host "查看所有标签:" -ForegroundColor Cyan
Write-Host "git tag -l"
Write-Host ""

Read-Host "按 Enter 退出"
