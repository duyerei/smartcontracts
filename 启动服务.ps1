# AI智能合同管理系统 - 启动脚本 (PowerShell)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   AI智能合同管理系统 - 启动脚本" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 停止现有服务
Write-Host "[1/4] 停止现有服务..." -ForegroundColor Yellow

# 停止占用8000端口的Python进程
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    $process = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -eq "python") {
        Write-Host "  停止后端进程: $($process.Id)" -ForegroundColor Gray
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

# 停止占用3000/3001端口的Node进程
@("3000", "3001") | ForEach-Object {
    Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue | ForEach-Object {
        $process = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "  停止前端进程: $($process.Id)" -ForegroundColor Gray
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Sleep -Seconds 2
Write-Host ""

# 启动后端
Write-Host "[2/4] 启动后端服务..." -ForegroundColor Yellow
$backendPath = Join-Path $ScriptDir "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; python run.py" -WindowStyle Normal

# 等待后端启动
Write-Host "  等待后端服务启动..." -ForegroundColor Gray
Start-Sleep -Seconds 5
Write-Host "  后端已启动: http://localhost:8000" -ForegroundColor Green

# 启动前端
Write-Host ""
Write-Host "[3/4] 启动前端服务..." -ForegroundColor Yellow
$frontendPath = Join-Path $ScriptDir "frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev" -WindowStyle Normal

Write-Host "  等待前端服务启动..." -ForegroundColor Gray
Start-Sleep -Seconds 5
Write-Host "  前端已启动: http://localhost:3001" -ForegroundColor Green

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  后端: http://localhost:8000" -ForegroundColor White
Write-Host "  前端: http://localhost:3001" -ForegroundColor White
Write-Host ""
Write-Host "  请在浏览器中打开前端地址访问系统" -ForegroundColor Gray
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
