@echo off
echo ================================================
echo    AI智能合同管理系统 - 停止脚本
echo ================================================
echo.

echo 正在停止所有服务...

REM 停止所有Python进程 (后端)
echo [1/2] 停止后端服务...
taskkill /F /IM python.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   后端服务已停止
) else (
    echo   后端服务未运行
)

REM 停止Node.js进程 (前端)
echo [2/2] 停止前端服务...
taskkill /F /IM node.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   前端服务已停止
) else (
    echo   前端服务未运行
)

REM 停止占用端口的进程
echo.
echo 清理端口占用...
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a 2>nul
    )
)

netstat -ano | findstr ":3000" | findstr "LISTENING" >nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a 2>nul
    )
)

netstat -ano | findstr ":3001" | findstr "LISTENING" >nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a 2>nul
    )
)

echo.
echo ================================================
echo 所有服务已停止！
echo ================================================
pause
