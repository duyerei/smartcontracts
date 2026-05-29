@echo off
echo ================================================
echo    AI智能合同管理系统 - 启动脚本
echo ================================================
echo.

REM 检查端口占用并清理
echo [1/3] 检查端口占用情况...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo 端口 8000 被占用，尝试关闭进程 %%a
    taskkill /F /PID %%a 2>nul
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
    echo 端口 3000 被占用，尝试关闭进程 %%a
    taskkill /F /PID %%a 2>nul
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001" ^| findstr "LISTENING"') do (
    echo 端口 3001 被占用，尝试关闭进程 %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo [2/3] 启动后端服务...
start "Backend - AI合同管理系统" cmd /k "cd /d %~dp0backend && python run.py"

REM 等待后端启动
echo 等待后端服务启动...
timeout /t 5 /nobreak >nul

echo.
echo [3/3] 启动前端服务...
start "Frontend - AI合同管理系统" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ================================================
echo 启动完成！
echo.
echo 后端地址: http://localhost:8000
echo 前端地址: http://localhost:3001
echo.
echo 请在浏览器中打开前端地址访问系统
echo ================================================
pause
