# GitHub 上传完整指南

## 📋 准备工作

### 1. 确认 .gitignore 配置

确保 `.gitignore` 文件中包含以下内容，防止敏感信息上传：

```gitignore
# 环境变量文件（包含敏感信息）
.env
backend/.env
frontend/.env.local

# 数据库文件
*.db
*.sqlite
*.sqlite3

# 存储文件
storage/
backend/storage/
backend/app/storage/

# 安全文件
/secure/
admin_password.txt
```

### 2. 验证敏感文件已被忽略

运行以下命令验证：

```bash
# 检查 .env 是否被忽略
git check-ignore backend/.env

# 如果返回 "backend/.env"，说明已被忽略 ✅
# 如果没有输出，说明未被忽略 ❌
```

---

## 🚀 方法一：使用自动化脚本（推荐）

### Windows 用户

1. 双击运行 `upload-to-github.bat`
2. 按照提示操作
3. 脚本会自动完成所有步骤

### Linux/Mac 用户

1. 添加执行权限：
```bash
chmod +x upload-to-github.sh
```

2. 运行脚本：
```bash
./upload-to-github.sh
```

3. 按照提示操作

---

## 📝 方法二：手动上传

### 步骤 1: 检查状态

```bash
# 查看当前状态
git status

# 确认没有 .env 文件在列表中
```

### 步骤 2: 添加文件

```bash
# 添加所有更改（.env 会被自动忽略）
git add .

# 再次确认暂存区没有 .env
git diff --cached --name-only | grep .env
# 如果没有输出，说明 .env 未被添加 ✅
```

### 步骤 3: 提交更改

```bash
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
   - 修复SupplementList.tsx重复代码问题"
```

### 步骤 4: 创建版本标签

```bash
git tag -a v1.2.0 -m "版本 v1.2.0 - 付款管理功能及UI优化

主要功能：
✅ 付款管理完整功能
✅ 文件预览修复
✅ UI优化和用户体验改进
✅ 识别超时处理
✅ 文件后缀显示"
```

### 步骤 5: 配置远程仓库（首次上传）

如果是首次上传，需要配置远程仓库：

```bash
# 添加远程仓库
git remote add origin https://github.com/你的用户名/smart-contracts.git

# 验证配置
git remote -v
```

### 步骤 6: 推送到 GitHub

```bash
# 推送代码到 main 分支
git push -u origin main

# 推送标签
git push origin v1.2.0

# 或推送所有标签
git push origin --tags
```

---

## 🔒 安全检查清单

在推送之前，请确认：

- [ ] `.env` 文件已在 `.gitignore` 中
- [ ] `backend/.env` 不在暂存区
- [ ] 数据库文件（`.db`、`.sqlite`）不在暂存区
- [ ] 存储文件夹（`storage/`）不在暂存区
- [ ] 没有包含 API 密钥的文件
- [ ] 没有包含密码的文件

### 验证命令

```bash
# 查看将要提交的文件
git diff --cached --name-only

# 检查是否包含敏感文件
git diff --cached --name-only | grep -E "\.(env|db|sqlite)"

# 如果有输出，说明包含敏感文件，需要移除
git reset 文件名
```

---

## 🆘 常见问题

### 问题 1: .env 文件被添加到暂存区

**解决方案**：
```bash
# 从暂存区移除
git reset backend/.env

# 确保 .gitignore 包含 .env
echo "backend/.env" >> .gitignore
```

### 问题 2: 远程仓库已存在

**解决方案**：
```bash
# 查看远程仓库
git remote -v

# 如果需要更改
git remote set-url origin https://github.com/你的用户名/smart-contracts.git
```

### 问题 3: 推送被拒绝

**解决方案**：
```bash
# 先拉取远程更改
git pull origin main --rebase

# 再推送
git push origin main
```

### 问题 4: 标签已存在

**解决方案**：
```bash
# 删除本地标签
git tag -d v1.2.0

# 删除远程标签
git push origin :refs/tags/v1.2.0

# 重新创建标签
git tag -a v1.2.0 -m "版本说明"

# 推送新标签
git push origin v1.2.0
```

---

## 📊 推送后验证

### 1. 在 GitHub 上检查

访问你的仓库：`https://github.com/你的用户名/smart-contracts`

确认：
- ✅ 代码已更新
- ✅ 没有 `.env` 文件
- ✅ 没有 `storage/` 文件夹
- ✅ 版本标签已创建

### 2. 查看提交历史

```bash
# 查看最近的提交
git log -3 --oneline --decorate

# 查看所有标签
git tag -l

# 查看标签详情
git show v1.2.0
```

### 3. 克隆测试

在另一个目录测试克隆：

```bash
# 克隆仓库
git clone https://github.com/你的用户名/smart-contracts.git test-clone

# 进入目录
cd test-clone

# 检查是否有 .env 文件
ls -la backend/

# 应该没有 .env 文件 ✅
```

---

## 🎯 最佳实践

### 1. 定期提交

- 每完成一个功能就提交一次
- 提交信息要清晰明确
- 使用语义化的提交信息（feat、fix、docs等）

### 2. 使用分支

```bash
# 创建功能分支
git checkout -b feature/payment-management

# 开发完成后合并到 main
git checkout main
git merge feature/payment-management
```

### 3. 版本标签

- 使用语义化版本号（v1.2.0）
- 主版本号：不兼容的 API 修改
- 次版本号：向下兼容的功能性新增
- 修订号：向下兼容的问题修正

### 4. 保护敏感信息

- 永远不要提交 `.env` 文件
- 使用 `.env.example` 作为模板
- 在 README 中说明如何配置环境变量

---

## 📚 相关文档

- [Git 官方文档](https://git-scm.com/doc)
- [GitHub 使用指南](https://docs.github.com/)
- [语义化版本](https://semver.org/lang/zh-CN/)
- [Git 提交信息规范](https://www.conventionalcommits.org/zh-hans/)

---

## 🔗 快速命令参考

```bash
# 查看状态
git status

# 添加文件
git add .

# 提交
git commit -m "提交信息"

# 创建标签
git tag -a v1.2.0 -m "版本说明"

# 推送代码
git push origin main

# 推送标签
git push origin v1.2.0

# 查看日志
git log --oneline --decorate

# 查看标签
git tag -l

# 查看远程仓库
git remote -v
```

---

**版本**: v1.2.0  
**更新日期**: 2024年  
**仓库名称**: smart-contracts
