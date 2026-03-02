@echo off
chcp 65001 >nul
echo === AI智能合同管理系统 - 创建新版本 ===
echo.

REM 建议的版本号
set VERSION=v1.2.0

echo 建议版本号: %VERSION%
echo.
echo 版本更新内容：
echo - v1.0.0: 初始版本，基础合同管理功能
echo - v1.1.0: 补充协议功能、安全修复
echo - v1.2.0: 付款管理功能、UI优化、预览修复
echo.

REM 1. 查看当前状态
echo === 步骤 1: 查看当前状态 ===
git status
echo.

REM 2. 添加所有更改
echo === 步骤 2: 添加所有更改 ===
git add .
echo.

REM 3. 提交更改
echo === 步骤 3: 提交更改 ===
git commit -m "feat: 实现付款管理功能及UI优化" -m "" -m "主要更新：" -m "1. 付款管理功能" -m "   - 完成后端路由注册（payments.py）" -m "   - 创建前端PaymentList组件" -m "   - 集成到合同详情页面" -m "   - 支持上传付款凭证（PDF、图片、DOC、DOCX）" -m "   - AI自动识别付款时间和金额" -m "   - 支持编辑和删除功能" -m "" -m "2. 文件预览修复" -m "   - 修复补充协议和付款凭证预览失败问题" -m "   - 根据文件类型动态设置正确的media_type" -m "   - 改进blob URL清理机制" -m "   - 添加详细的错误处理" -m "" -m "3. UI优化" -m "   - 将'查看附件'改为文件名可点击链接" -m "   - 文件名自动显示文件后缀（.pdf、.docx等）" -m "   - 识别超时（2分钟）后显示'未识别'而不是'识别中...'" -m "   - 界面更简洁直观" -m "" -m "4. Bug修复" -m "   - 修复file_storage.file_storage错误" -m "   - 修复supplements.py下载接口media_type问题" -m "   - 修复SupplementList.tsx重复代码问题"
echo.

REM 4. 创建带注释的标签
echo === 步骤 4: 创建版本标签 %VERSION% ===
git tag -a %VERSION% -m "版本 %VERSION% - 付款管理功能及UI优化" -m "" -m "主要功能：" -m "✅ 付款管理完整功能" -m "✅ 文件预览修复" -m "✅ UI优化和用户体验改进" -m "✅ 识别超时处理" -m "✅ 文件后缀显示"
echo.

REM 5. 查看标签
echo === 步骤 5: 查看所有版本标签 ===
git tag -l
echo.

REM 6. 查看最新标签详情
echo === 步骤 6: 查看最新版本详情 ===
git show %VERSION% --stat
echo.

REM 7. 查看提交历史
echo === 步骤 7: 查看最近3次提交 ===
git log -3 --oneline --decorate
echo.

echo === 完成！===
echo.
echo 版本 %VERSION% 已创建成功！
echo.
echo 后续操作：
echo 1. 推送提交到远程仓库: git push origin main
echo 2. 推送标签到远程仓库: git push origin %VERSION%
echo 3. 推送所有标签: git push origin --tags
echo.
pause
