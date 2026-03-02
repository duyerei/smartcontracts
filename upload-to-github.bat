@echo off
chcp 65001 >nul
echo === 上传代码到 GitHub - Smart Contracts ===
echo.

REM 配置
set REPO_NAME=smart-contracts
set BRANCH=main
set VERSION=v1.2.0

REM 1. 检查 .gitignore
echo === 步骤 1: 检查 .gitignore 配置 ===
findstr /C:".env" .gitignore >nul
if %errorlevel% equ 0 (
    echo ✅ .env 已在 .gitignore 中，不会被上传
) else (
    echo ⚠️  警告: .env 未在 .gitignore 中
    echo 正在添加 .env 到 .gitignore...
    echo .env >> .gitignore
    echo backend/.env >> .gitignore
)
echo.

REM 2. 验证 .env 不会被提交
echo === 步骤 2: 验证敏感文件不会被提交 ===
git check-ignore backend/.env >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ backend/.env 已被忽略
) else (
    echo ❌ 警告: backend/.env 可能会被提交！
    echo 请检查 .gitignore 配置
    pause
    exit /b 1
)
echo.

REM 3. 查看将要提交的文件
echo === 步骤 3: 查看将要提交的文件 ===
git status
echo.
echo 请确认以上文件中没有 .env 文件
pause
echo.

REM 4. 添加所有更改
echo === 步骤 4: 添加所有更改 ===
git add .
echo.

REM 5. 确认暂存区文件
echo === 步骤 5: 确认暂存区文件 ===
git diff --cached --name-only | findstr /C:".env" >nul
if %errorlevel% equ 0 (
    echo ❌ 错误: 发现 .env 文件在暂存区！
    echo 正在移除...
    git reset backend/.env 2>nul
    git reset .env 2>nul
    echo ✅ 已移除 .env 文件
) else (
    echo ✅ 暂存区中没有 .env 文件
)
echo.

REM 6. 提交更改
echo === 步骤 6: 提交更改 ===
git commit -m "feat: 实现付款管理功能及UI优化" -m "" -m "主要更新：" -m "1. 付款管理功能" -m "   - 完成后端路由注册（payments.py）" -m "   - 创建前端PaymentList组件" -m "   - 集成到合同详情页面" -m "   - 支持上传付款凭证（PDF、图片、DOC、DOCX）" -m "   - AI自动识别付款时间和金额" -m "   - 支持编辑和删除功能" -m "" -m "2. 文件预览修复" -m "   - 修复补充协议和付款凭证预览失败问题" -m "   - 根据文件类型动态设置正确的media_type" -m "   - 改进blob URL清理机制" -m "   - 添加详细的错误处理" -m "" -m "3. UI优化" -m "   - 将'查看附件'改为文件名可点击链接" -m "   - 文件名自动显示文件后缀（.pdf、.docx等）" -m "   - 识别超时（2分钟）后显示'未识别'而不是'识别中...'" -m "   - 界面更简洁直观" -m "" -m "4. Bug修复" -m "   - 修复file_storage.file_storage错误" -m "   - 修复supplements.py下载接口media_type问题" -m "   - 修复SupplementList.tsx重复代码问题"
echo.

REM 7. 创建版本标签
echo === 步骤 7: 创建版本标签 %VERSION% ===
git tag -a %VERSION% -m "版本 %VERSION% - 付款管理功能及UI优化" -m "" -m "主要功能：" -m "✅ 付款管理完整功能" -m "✅ 文件预览修复" -m "✅ UI优化和用户体验改进" -m "✅ 识别超时处理" -m "✅ 文件后缀显示"
echo.

REM 8. 检查远程仓库
echo === 步骤 8: 检查远程仓库配置 ===
git remote | findstr /C:"origin" >nul
if %errorlevel% equ 0 (
    echo ✅ 远程仓库已配置
    git remote -v
) else (
    echo ⚠️  未配置远程仓库
    set /p REPO_URL="请输入 GitHub 仓库 URL (例如: https://github.com/username/smart-contracts.git): "
    git remote add origin %REPO_URL%
    echo ✅ 已添加远程仓库
)
echo.

REM 9. 推送到 GitHub
echo === 步骤 9: 推送到 GitHub ===
echo 正在推送代码到 %BRANCH% 分支...
git push -u origin %BRANCH%
echo.

echo 正在推送标签 %VERSION%...
git push origin %VERSION%
echo.

REM 10. 完成
echo === 完成！===
echo.
echo ✅ 代码已成功上传到 GitHub
echo ✅ 版本标签 %VERSION% 已创建
echo.
echo GitHub 仓库地址:
git remote get-url origin
echo.
echo 查看提交历史:
echo git log -3 --oneline --decorate
echo.
echo 查看所有标签:
echo git tag -l
echo.
pause
