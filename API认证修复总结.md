# API认证修复总结

## 问题概述

在添加API认证后，前端多个功能出现401未授权错误，原因是部分API调用没有携带JWT token。

## 修复的API接口

### 1. 合同下载 ✅
**文件**: `frontend/src/pages/ContractDetail.tsx`  
**问题**: 使用 `window.open()` 无法携带header  
**修复**: 使用 `fetch` + `blob` 方式下载

### 2. 合同预览 ✅
**文件**: `frontend/src/pages/ContractDetail.tsx`  
**问题**: 使用 `window.open()` 和 `<iframe>` 无法携带header  
**修复**: 使用 `fetch` + `blob URL`

### 3. 合同列表下载 ✅
**文件**: `frontend/src/pages/ContractList.tsx`  
**问题**: 使用 `window.open()` 无法携带header  
**修复**: 使用 `fetch` + `blob` 方式下载

### 4. 重新解析 ✅
**文件**: `frontend/src/lib/api.ts`  
**问题**: 直接使用 `fetch` 没有携带token  
**修复**: 添加 `Authorization` header

```typescript
// 修复前
const response = await fetch(`${API_BASE_URL}/contracts/${id}/reparse`, {
  method: 'POST',
})

// 修复后
const token = localStorage.getItem('token')
const response = await fetch(`${API_BASE_URL}/contracts/${id}/reparse`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  },
})
```

### 5. 合同上传 ✅
**文件**: `frontend/src/lib/api.ts`  
**问题**: 上传文件时没有携带token  
**修复**: 添加 `Authorization` header

```typescript
// 修复前
const response = await fetch(`${API_BASE_URL}/contracts/upload`, {
  method: 'POST',
  body: formData,
})

// 修复后
const token = localStorage.getItem('token')
const response = await fetch(`${API_BASE_URL}/contracts/upload`, {
  method: 'POST',
  headers: {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  },
  body: formData,
})
```

## 已验证正常的API

以下API使用了 `fetchApi` 辅助函数，会自动携带token：

- ✅ `contractApi.list()` - 合同列表
- ✅ `contractApi.get()` - 获取合同详情
- ✅ `contractApi.update()` - 更新合同
- ✅ `contractApi.delete()` - 删除合同
- ✅ `contractApi.analyze()` - 风险分析
- ✅ `contractApi.getText()` - 获取合同文本
- ✅ `agentApi.chat()` - AI助手对话
- ✅ `agentApi.chatStream()` - AI助手流式对话

## fetchApi 辅助函数

所有使用 `fetchApi` 的API调用都会自动携带token：

```typescript
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    })
    // ...
  }
}
```

## 测试清单

请测试以下功能确保都正常工作：

### 基础功能
- [ ] 登录
- [ ] 退出登录
- [ ] 查看合同列表
- [ ] 查看合同详情

### 合同操作
- [ ] 上传合同
- [ ] 下载合同（列表页）
- [ ] 下载合同（详情页）
- [ ] 预览合同（新窗口）
- [ ] 预览合同（iframe）
- [ ] 编辑合同
- [ ] 删除合同

### AI功能
- [ ] 重新解析合同
- [ ] AI风险分析
- [ ] AI助手对话

### 用户管理（管理员）
- [ ] 查看用户列表
- [ ] 创建用户
- [ ] 编辑用户
- [ ] 删除用户
- [ ] 修改密码

## 常见问题

### Q: 为什么有些API使用fetchApi，有些直接用fetch？

**A**: 
- `fetchApi` 用于标准的JSON API调用
- 直接 `fetch` 用于特殊情况：
  - 文件上传（需要 FormData）
  - 文件下载（需要处理 blob）
  - 流式响应（SSE）

### Q: 如何确保新的API调用携带token？

**A**: 
1. 优先使用 `fetchApi` 辅助函数
2. 如果必须直接使用 `fetch`，记得添加：
```typescript
const token = localStorage.getItem('token')
headers: {
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
}
```

### Q: Token过期怎么办？

**A**: 
- 当前实现：返回401，前端重定向到登录页
- 未来优化：实现token自动刷新机制

### Q: 为什么FormData上传不能设置Content-Type？

**A**: 
浏览器会自动设置正确的 `Content-Type`（包含boundary），手动设置会导致错误。

```typescript
// ❌ 错误 - 不要手动设置Content-Type
headers: {
  'Content-Type': 'multipart/form-data',
  Authorization: `Bearer ${token}`,
}

// ✅ 正确 - 让浏览器自动设置
headers: {
  Authorization: `Bearer ${token}`,
}
```

## 安全性改进

### 修复前
```
❌ 部分API无需认证即可访问
❌ 任何人都可以上传、下载、删除合同
❌ 无法追踪用户操作
```

### 修复后
```
✅ 所有API都需要认证
✅ Token在HTTP header中安全传输
✅ 后端可以记录用户操作日志
✅ 未登录用户自动重定向到登录页
```

## 后续优化建议

### 1. 统一API调用方式

创建一个统一的API客户端类：

```typescript
class ApiClient {
  private getHeaders(): HeadersInit {
    const token = localStorage.getItem('token')
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: this.getHeaders(),
    })
    return this.handleResponse(response)
  }

  async post<T>(endpoint: string, data: unknown): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    })
    return this.handleResponse(response)
  }

  // ... 其他方法
}

export const apiClient = new ApiClient()
```

### 2. 自动Token刷新

```typescript
// 拦截401响应，自动刷新token
async handleResponse(response: Response) {
  if (response.status === 401) {
    // 尝试刷新token
    const newToken = await this.refreshToken()
    if (newToken) {
      // 重试原请求
      return this.retryRequest(response.url, newToken)
    } else {
      // 刷新失败，跳转登录
      window.location.href = '/login'
    }
  }
  return response.json()
}
```

### 3. 请求队列

防止并发请求导致的token刷新问题：

```typescript
class TokenManager {
  private refreshPromise: Promise<string> | null = null

  async getToken(): Promise<string> {
    const token = localStorage.getItem('token')
    if (this.isTokenExpired(token)) {
      if (!this.refreshPromise) {
        this.refreshPromise = this.refreshToken()
      }
      return this.refreshPromise
    }
    return token
  }
}
```

## 相关文档

- [认证问题修复说明.md](./认证问题修复说明.md) - 下载和预览功能修复
- [安全修复实施指南.md](./安全修复实施指南.md) - 完整的安全修复方案
- [测试登录指南.md](./测试登录指南.md) - 登录测试步骤

---

**修复日期**: 2026-03-02  
**修复人**: 技术团队  
**影响范围**: 前端所有API调用
