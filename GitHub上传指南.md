# GitHub 代码上传指南

## 当前状态

根据截图，您的GitHub仓库 `smartcontracts` 是空的，这是好消息！说明敏感信息还没有泄露。

## 正确的上传步骤

### 步骤1：确认.gitignore已配置

```bash
# 检查.gitignore文件是否存在
cat .gitignore

# 应该包含以下内容：
# .env
# backend/.env
# /secure/
```

### 步骤2：初始化Git仓库（如果还没有）

```bash
cd /path/to/your/project

# 初始化Git仓库
git init

# 添加远程仓库
git remote add origin https://github.com/duyun6/smartcontracts.git
```

### 步骤3：检查哪些文件会被提交

```bash
# 查看将要提交的文件
git status

# 确认.env文件不在列表中
# 如果看到.env文件，说明.gitignore没有生效
```

### 步骤4：添加文件到Git

```bash
# 添加所有文件（.gitignore会自动排除敏感文件）
git add .

# 再次确认
git status

# 应该看到类似输出：
# Changes to be committed:
#   new file:   .gitignore
#   new file:   backend/app/main.py
#   new file:   frontend/src/App.tsx
#   ...
# 
# 不应该看到：
#   backend/.env  ❌
#   secure/admin_password.txt  ❌
```

### 步骤5：提交代码

```bash
# 创建初始提交
git commit -m "feat: 初始化AI智能合同管理系统

- 后端API（FastAPI）
- 前端界面（React + TypeScript）
- 合同解析功能
- AI风险分析
- 用户认证系统
- 安全加固"

# 设置主分支名称
git branch -M main
```

### 步骤6：推送到GitHub

```bash
# 首次推送
git push -u origin main

# 如果遇到认证问题，使用Personal Access Token
# 在GitHub Settings > Developer settings > Personal access tokens 生成
```

## ⚠️ 重要提醒

### 如果.env文件已经被提交过

如果您之前已经提交过.env文件，需要从Git历史中删除：

```bash
# 1. 从Git缓存中删除
git rm --cached backend/.env

# 2. 提交删除操作
git commit -m "security: 移除敏感配置文件"

# 3. 如果已经推送到GitHub，需要清理历史
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch backend/.env" \
  --prune-empty --tag-name-filter cat -- --all

# 4. 强制推送
git push origin --force --all
```

### 验证.env文件没有被上传

```bash
# 在GitHub仓库页面搜索
# 搜索关键词：BAIDU_OCR_API_KEY
# 如果搜索结果为空，说明没有泄露
```

## 📋 上传前检查清单

在执行 `git push` 之前，请确认：

- [ ] `.gitignore` 文件已创建并包含 `.env`
- [ ] 执行 `git status` 确认 `.env` 不在提交列表中
- [ ] `backend/.env.example` 已创建（不包含真实密钥）
- [ ] `secure/` 目录不在提交列表中
- [ ] 数据库文件（`.db`）不在提交列表中
- [ ] `node_modules/` 不在提交列表中
- [ ] `__pycache__/` 不在提交列表中

## 🔒 安全最佳实践

### 1. 使用环境变量

生产环境不要使用.env文件，而是使用系统环境变量：

```bash
# Linux/Mac
export BAIDU_OCR_API_KEY="your_key_here"
export JWT_SECRET_KEY="your_secret_here"

# 或者在服务器配置文件中设置
# /etc/environment
# ~/.bashrc
```

### 2. 使用密钥管理服务

对于生产环境，建议使用专业的密钥管理服务：

- AWS Secrets Manager
- Azure Key Vault
- HashiCorp Vault
- 阿里云密钥管理服务（KMS）

### 3. 定期轮换密钥

- API密钥：每3个月轮换一次
- JWT密钥：每6个月轮换一次
- 数据库密码：每6个月轮换一次

### 4. 监控API使用

在各服务商控制台设置：
- API调用量告警
- 异常访问告警
- 费用告警

## 📝 .env.example 的作用

`.env.example` 文件的作用是：

1. **团队协作**：告诉其他开发者需要配置哪些环境变量
2. **文档说明**：说明每个变量的用途
3. **快速部署**：新环境可以快速复制并填入真实值

```bash
# 新开发者加入项目时
cp backend/.env.example backend/.env
# 然后编辑.env文件，填入真实的API密钥
```

## 🚀 持续集成/部署（CI/CD）

如果使用GitHub Actions，在仓库设置中配置Secrets：

1. 进入仓库 Settings > Secrets and variables > Actions
2. 添加以下Secrets：
   - `BAIDU_OCR_API_KEY`
   - `BAIDU_OCR_SECRET_KEY`
   - `JWT_SECRET_KEY`
   - 等等

3. 在GitHub Actions工作流中使用：

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Create .env file
        run: |
          echo "BAIDU_OCR_API_KEY=${{ secrets.BAIDU_OCR_API_KEY }}" >> backend/.env
          echo "JWT_SECRET_KEY=${{ secrets.JWT_SECRET_KEY }}" >> backend/.env
      
      - name: Deploy
        run: |
          # 部署命令
```

## 📞 遇到问题？

如果在上传过程中遇到问题：

1. **认证失败**：使用Personal Access Token代替密码
2. **文件太大**：检查是否误提交了大文件（数据库、日志等）
3. **推送被拒绝**：可能需要先pull远程更改

```bash
# 查看远程仓库状态
git remote -v

# 拉取远程更改
git pull origin main --rebase

# 再次推送
git push origin main
```

---

**重要提示**：一旦代码推送到GitHub，就认为是公开的。即使是私有仓库，也要假设可能被泄露。因此，绝对不要提交敏感信息！
