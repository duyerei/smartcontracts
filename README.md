# AI智能合同管理系统

## 快速启动

### Windows 用户

双击运行以下文件：

| 文件 | 说明 |
|------|------|
| `启动服务.bat` | 一键启动前后端服务 |
| `停止服务.bat` | 停止所有服务 |

或者使用 PowerShell：
```powershell
.\启动服务.ps1
```

### 访问地址

- **前端**: http://localhost:3001
- **后端**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 功能说明

### 合同状态计算规则
- **合同履行中**: 距离到期日大于2个月
- **即将到期**: 距离到期日在2个月内
- **履行完成**: 已过到期日

### 主要功能
1. 合同上传与OCR识别
2. AI智能解析合同内容
3. 合同列表与详情查看
4. 合同状态自动计算
5. 合同搜索与筛选

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite
- **前端**: React + TypeScript + Vite + Tailwind CSS

## AI助手（AppBuilder）接入与联调

### 1. 后端环境变量（backend/.env）

```env
# 你的AppBuilder应用调用地址（按百度控制台/API文档填写）
APPBUILDER_API_URL=

# 应用Token（不要写到前端代码）
APPBUILDER_API_TOKEN=

# 你的应用ID
APPBUILDER_APP_ID=
```

### 2. 联调检查接口

- 健康检查：`GET /api/v1/agent/health`
  - 返回是否已配置 AppBuilder（`appbuilder_configured`）
- 咨询链路探测：`POST /api/v1/agent/probe`
  - 仅验证 AppBuilder/Qianfan 回退链路
  - 支持透传 `conversation_id`

### 3. 示例请求

```bash
# 1) 检查配置
curl http://localhost:8000/api/v1/agent/health

# 2) 首轮对话（无conversation_id）
curl -X POST http://localhost:8000/api/v1/agent/probe \
  -H "Content-Type: application/json" \
  -d '{"message":"你好，帮我概括你能做什么"}'

# 3) 多轮对话（透传conversation_id）
curl -X POST http://localhost:8000/api/v1/agent/probe \
  -H "Content-Type: application/json" \
  -d '{"message":"继续上一轮", "conversation_id":"<上一步返回的conversation_id>"}'
```

### 4. 前端可视化

AI小窗会展示：
- `来源(provider)`：`appbuilder` / `qianfan` / `rule`
- `会话ID(conversation_id)`：用于多轮对话透传
- `错误细节(error_detail)`：用于排查AppBuilder联调问题
