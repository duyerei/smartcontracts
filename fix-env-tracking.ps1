# 修复 .env 文件跟踪问题

Write-Host "=== 修复 .env 文件跟踪问题 ===" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 .env 是否被 Git 跟踪
Write-Host "步骤 1: 检查 .env 文件状态" -ForegroundColor Yellow
$trackedFiles = git ls-files | Select-String "\.env"
if ($trackedFiles) {
    Write-Host "⚠️  发现以下 .env 文件被 Git 跟踪:" -ForegroundColor Red
    $trackedFiles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    
    # 2. 从 Git 跟踪中移除 .env 文件
    Write-Host "步骤 2: 从 Git 跟踪中移除 .env 文件" -ForegroundColor Yellow
    
    # 移除 backend/.env
    if (Test-Path "backend/.env") {
        Write-Host "正在移除 backend/.env 的跟踪..." -ForegroundColor Cyan
        git rm --cached backend/.env
        Write-Host "✅ 已从 Git 跟踪中移除 backend/.env" -ForegroundColor Green
    }
    
    # 移除根目录 .env
    if (Test-Path ".env") {
        Write-Host "正在移除 .env 的跟踪..." -ForegroundColor Cyan
        git rm --cached .env
        Write-Host "✅ 已从 Git 跟踪中移除 .env" -ForegroundColor Green
    }
    
    Write-Host ""
} else {
    Write-Host "✅ 没有 .env 文件被 Git 跟踪" -ForegroundColor Green
    Write-Host ""
}

# 3. 确保 .gitignore 包含 .env
Write-Host "步骤 3: 确保 .gitignore 包含 .env" -ForegroundColor Yellow
$gitignoreContent = Get-Content ".gitignore" -Raw
if ($gitignoreContent -notmatch "backend/\.env") {
    Write-Host "添加 backend/.env 到 .gitignore..." -ForegroundColor Cyan
    Add-Content -Path ".gitignore" -Value "`nbackend/.env"
}
if ($gitignoreContent -notmatch "^\.env$") {
    Write-Host "添加 .env 到 .gitignore..." -ForegroundColor Cyan
    Add-Content -Path ".gitignore" -Value ".env"
}
Write-Host "✅ .gitignore 配置完成" -ForegroundColor Green
Write-Host ""

# 4. 验证 .env 现在被忽略
Write-Host "步骤 4: 验证 .env 现在被忽略" -ForegroundColor Yellow
$checkIgnore = git check-ignore backend/.env 2>&1
if ($checkIgnore -match "backend/.env") {
    Write-Host "✅ backend/.env 现在被正确忽略" -ForegroundColor Green
} else {
    Write-Host "⚠️  backend/.env 仍未被忽略，请手动检查 .gitignore" -ForegroundColor Yellow
}
Write-Host ""

# 5. 提交更改
Write-Host "步骤 5: 提交 .gitignore 更改" -ForegroundColor Yellow
$response = Read-Host "是否提交 .gitignore 的更改? (y/n)"
if ($response -eq "y" -or $response -eq "Y") {
    git add .gitignore
    git commit -m "chore: 从 Git 跟踪中移除 .env 文件

- 从 Git 跟踪中移除 backend/.env
- 更新 .gitignore 确保 .env 文件被忽略
- 防止敏感信息泄露"
    Write-Host "✅ 已提交更改" -ForegroundColor Green
} else {
    Write-Host "⏭️  跳过提交" -ForegroundColor Yellow
}
Write-Host ""

# 6. 显示当前状态
Write-Host "步骤 6: 当前 Git 状态" -ForegroundColor Yellow
git status
Write-Host ""

Write-Host "=== 完成！===" -ForegroundColor Green
Write-Host ""
Write-Host "现在可以安全地运行 upload-to-github.ps1 了" -ForegroundColor Cyan
Write-Host ""

Read-Host "按 Enter 退出"
