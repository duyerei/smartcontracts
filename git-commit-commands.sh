#!/bin/bash

# Git 提交命令脚本
# 本次更新内容：付款管理功能完整实现及UI优化

echo "=== 查看当前状态 ==="
git status

echo ""
echo "=== 添加所有更改 ==="
git add .

echo ""
echo "=== 提交更改 ==="
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
- 自动刷新：每5秒检查更新

相关文件：
- backend/app/routers/payments.py
- backend/app/routers/supplements.py
- backend/app/routers/__init__.py
- backend/app/main.py
- frontend/src/components/PaymentList.tsx
- frontend/src/components/SupplementList.tsx
- frontend/src/pages/ContractDetail.tsx
- 付款管理功能说明.md
- 补充协议预览修复说明.md
- 补充协议显示优化说明.md"

echo ""
echo "=== 查看提交日志 ==="
git log -1 --stat

echo ""
echo "=== 完成！==="
