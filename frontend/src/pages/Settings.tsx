import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { 
  Key, 
  Server, 
  Shield, 
  Activity,
  Plus,
  Copy,
  Trash2,
  CheckCircle,
  XCircle,
  GitCommit,
  Tag,
  Pencil,
  ShieldCheck,
  User,
  Check,
  X,
} from 'lucide-react'
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface APIKey {
  id: string
  name: string
  key: string
  createdAt: string
  lastUsed: string | null
  status: 'active' | 'inactive'
}

interface MCPConnection {
  name: string
  serverUrl: string
  status: 'connected' | 'disconnected'
  lastConnected: string | null
}

interface UserItem {
  id: number
  username: string
  real_name: string
  department: string
  role: string
  is_active: boolean
  created_at: string | null
}

interface UserForm {
  username: string
  password: string
  real_name: string
  department: string
  role: 'admin' | 'user'
}

const emptyUserForm: UserForm = { username: '', password: '', real_name: '', department: '', role: 'user' }

const requiredMark = (
  <span className="ml-0.5 font-semibold" style={{ color: 'hsl(var(--destructive))' }} aria-hidden="true">
    *
  </span>
)

const mockAPIKeys: APIKey[] = [
  { id: '1', name: '生产环境API', key: 'sk-**** **** **** ****', createdAt: '2025-01-15', lastUsed: '2025-01-28', status: 'active' },
  { id: '2', name: '测试环境API', key: 'sk-**** **** **** ****', createdAt: '2025-01-10', lastUsed: '2025-01-25', status: 'active' },
]

const mockMCPConnections: MCPConnection[] = [
  { name: 'Claude Desktop', serverUrl: 'http://localhost:3001', status: 'connected', lastConnected: '2025-01-28 10:30' },
  { name: '企业Agent', serverUrl: 'http://agent.company.com:8080', status: 'disconnected', lastConnected: null },
]

const releaseLog = [
  {
    version: 'v1.4.0',
    date: '2026-03-07',
    items: [
      'UI重构：导航精简，新增"数据导入"模块，整合合同导入、付款单导入、OA批量导入',
      '工作台新增智能搜索入口，直接跳转合同列表并带入关键词',
      '用户管理并入系统设置，减少导航层级',
      '合同列表删除导出按钮，合同名称超长自动截断，悬浮显示完整名称',
    ],
  },
  {
    version: 'v1.3.0',
    date: '2026-03-06',
    items: [
      '文件预览速度优化：PDF/图片改为直接 URL 流式加载，利用浏览器缓存，不再经过 JS 内存',
      '后端下载接口支持 token query 参数，允许 iframe 直接携带 token 访问',
      '合同列表布局优化：去掉右侧 AI 助手预留空间，小屏幕完全展开',
      '合同有效期换行显示（开始/结束日期各占一行）',
      '付款管理 PDF 解析：上传后自动后台解析付款信息，支持图片型 PDF（百度 OCR 兜底）',
      '修复合同附件被误删问题：导入 OA 流程 PDF 不再覆盖 source 字段',
    ],
  },
  {
    version: 'v1.2.0',
    date: '2026-02-20',
    items: [
      'OA 流程信息字段解析优化：支持"字段名换行值"格式，新增申请人、申请单号、归属成本中心等 7 个核心字段',
      'OA 流程信息展示修复：删除重复布局代码，改为简洁无背景样式',
      '合作伙伴去重功能',
      '合同概况改为 OA 流程信息，条件显示',
    ],
  },
  {
    version: 'v1.1.0',
    date: '2026-02-01',
    items: [
      'OA 合同导入功能：支持从 OA 系统批量导入合同及附件',
      'Word 文档在线预览（docx-preview）',
      'OA 附件内嵌预览，支持 PDF/Word/图片',
      '补充协议智能上传与树形展示',
      '付款管理模块',
    ],
  },
  {
    version: 'v1.0.0',
    date: '2026-01-15',
    items: [
      '合同上传与 AI 自动解析（百度 OCR + LLM）',
      '合同列表、详情、搜索',
      '风险分析',
      '合作伙伴管理',
      'AI 助手对话窗口',
      'Docker 部署支持',
    ],
  },
]

type TabKey = 'api' | 'mcp' | 'security' | 'logs' | 'changelog' | 'users'

const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'api', label: 'API管理', icon: <Key className="h-4 w-4" /> },
  { key: 'mcp', label: 'MCP配置', icon: <Server className="h-4 w-4" /> },
  { key: 'security', label: '安全设置', icon: <Shield className="h-4 w-4" /> },
  { key: 'logs', label: '审计日志', icon: <Activity className="h-4 w-4" /> },
  { key: 'changelog', label: '版本日志', icon: <GitCommit className="h-4 w-4" /> },
]

export function SettingsPage() {
  const { token } = useAuth()
  const [apiKeys, setAPIKeys] = useState<APIKey[]>(mockAPIKeys)
  const [mcpConnections, setMCPConnections] = useState<MCPConnection[]>(mockMCPConnections)
  const [newKeyName, setNewKeyName] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('api')

  // 用户管理状态
  const [users, setUsers] = useState<UserItem[]>([])
  const [usersLoading, setUsersLoading] = useState(false)
  const [showUserForm, setShowUserForm] = useState(false)
  const [editUserId, setEditUserId] = useState<number | null>(null)
  const [userForm, setUserForm] = useState<UserForm>(emptyUserForm)
  const [userError, setUserError] = useState('')
  const [userSaving, setUserSaving] = useState(false)

  const authHeaders = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

  const fetchUsers = useCallback(async () => {
    setUsersLoading(true)
    try {
      const r = await fetch(`${API_BASE_URL}/auth/users`, { headers: authHeaders })
      if (r.ok) setUsers(await r.json())
    } finally {
      setUsersLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (activeTab === 'users') fetchUsers()
  }, [activeTab, fetchUsers])

  const copyToClipboard = (text: string) => navigator.clipboard.writeText(text)

  const generateAPIKey = () => {
    const newKey: APIKey = {
      id: Math.random().toString(36).substring(7),
      name: newKeyName || '新API密钥',
      key: `sk-${Math.random().toString(36).substring(2)}${Math.random().toString(36).substring(2)}`,
      createdAt: new Date().toISOString().split('T')[0],
      lastUsed: null,
      status: 'active',
    }
    setAPIKeys([...apiKeys, newKey])
    setNewKeyName('')
  }

  const deleteAPIKey = (id: string) => setAPIKeys(apiKeys.filter(k => k.id !== id))

  const toggleMCPConnection = (name: string) => {
    setMCPConnections(connections =>
      connections.map(conn =>
        conn.name === name
          ? {
              ...conn,
              status: conn.status === 'connected' ? 'disconnected' : 'connected',
              lastConnected: conn.status === 'disconnected' ? new Date().toLocaleString() : conn.lastConnected,
            }
          : conn
      )
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">系统设置</h1>
        <p className="text-muted-foreground">管理API密钥、MCP连接和系统配置</p>
      </div>

      {/* Tab 导航 */}
      <div className="border-b">
        <div className="flex gap-1">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* API管理 */}
      {activeTab === 'api' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>API密钥管理</CardTitle>
              <CardDescription>创建和管理API密钥，用于调用系统REST API</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 mb-6">
                <Input placeholder="输入密钥名称" value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} className="max-w-xs" />
                <Button onClick={generateAPIKey}>
                  <Plus className="h-4 w-4 mr-2" />
                  生成新密钥
                </Button>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>密钥</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>最后使用</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {apiKeys.map((apiKey) => (
                    <TableRow key={apiKey.id}>
                      <TableCell className="font-medium">{apiKey.name}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <code className="text-sm bg-muted px-2 py-1 rounded">{apiKey.key}</code>
                          <Button variant="ghost" size="icon" onClick={() => copyToClipboard(apiKey.key)}>
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell>{apiKey.createdAt}</TableCell>
                      <TableCell>{apiKey.lastUsed || '-'}</TableCell>
                      <TableCell>
                        <Badge variant={apiKey.status === 'active' ? 'success' : 'secondary'}>
                          {apiKey.status === 'active' ? '启用' : '禁用'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => deleteAPIKey(apiKey.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>调用统计</CardTitle>
              <CardDescription>API调用情况统计</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  { label: '今日调用', value: '1,234' },
                  { label: '本周调用', value: '8,567' },
                  { label: '本月调用', value: '32,456' },
                  { label: '平均响应', value: '1.2s' },
                ].map(stat => (
                  <div key={stat.label} className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-sm text-muted-foreground">{stat.label}</p>
                    <p className="text-2xl font-bold">{stat.value}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* MCP配置 */}
      {activeTab === 'mcp' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>MCP连接</CardTitle>
              <CardDescription>配置MCP Server连接，使AI Agent能够调用本系统</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>服务器地址</TableHead>
                    <TableHead>连接状态</TableHead>
                    <TableHead>最后连接</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mcpConnections.map((conn) => (
                    <TableRow key={conn.name}>
                      <TableCell className="font-medium">{conn.name}</TableCell>
                      <TableCell><code className="text-sm bg-muted px-2 py-1 rounded">{conn.serverUrl}</code></TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {conn.status === 'connected' ? (
                            <><CheckCircle className="h-4 w-4 text-green-500" /><span className="text-green-500">已连接</span></>
                          ) : (
                            <><XCircle className="h-4 w-4 text-red-500" /><span className="text-red-500">未连接</span></>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{conn.lastConnected || '-'}</TableCell>
                      <TableCell className="text-right">
                        <Button variant={conn.status === 'connected' ? 'destructive' : 'default'} size="sm" onClick={() => toggleMCPConnection(conn.name)}>
                          {conn.status === 'connected' ? '断开' : '连接'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>可用MCP工具</CardTitle>
              <CardDescription>系统暴露给AI Agent的工具列表</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { name: 'upload_contract', desc: '上传合同文件并触发AI解析' },
                  { name: 'query_contracts', desc: '语义或条件查询合同' },
                  { name: 'get_contract_detail', desc: '获取特定合同的详细信息' },
                  { name: 'analyze_risk', desc: '生成合同风险分析报告' },
                ].map((tool) => (
                  <div key={tool.name} className="p-4 border rounded-lg">
                    <code className="text-sm font-medium">{tool.name}</code>
                    <p className="text-sm text-muted-foreground mt-1">{tool.desc}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 安全设置 */}
      {activeTab === 'security' && (
        <Card>
          <CardHeader>
            <CardTitle>安全设置</CardTitle>
            <CardDescription>配置系统安全选项</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { title: '数据脱敏', desc: '调用LLM前自动脱敏敏感信息' },
              { title: 'RBAC权限控制', desc: '基于角色的访问权限管理' },
              { title: 'API调用限制', desc: '设置API调用频率限制' },
            ].map(item => (
              <div key={item.title} className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-sm text-muted-foreground">{item.desc}</p>
                </div>
                <Button variant="outline">配置</Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* 审计日志 */}
      {activeTab === 'logs' && (
        <Card>
          <CardHeader>
            <CardTitle>操作日志</CardTitle>
            <CardDescription>记录所有系统操作，支持追溯和审计</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>操作者</TableHead>
                  <TableHead>操作类型</TableHead>
                  <TableHead>操作内容</TableHead>
                  <TableHead>IP地址</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[
                  { time: '2025-01-28 14:30:25', user: 'admin', action: '上传合同', detail: '上传文件: 华为采购合同.pdf', ip: '192.168.1.100' },
                  { time: '2025-01-28 14:25:10', user: 'admin', action: '查询合同', detail: '查询: 采购合同', ip: '192.168.1.100' },
                  { time: '2025-01-28 14:20:05', user: 'admin', action: '生成API Key', detail: '创建密钥: 测试环境API', ip: '192.168.1.100' },
                  { time: '2025-01-28 14:15:30', user: 'admin', action: '风险分析', detail: '分析合同: CT-2025-001', ip: '192.168.1.100' },
                ].map((log, index) => (
                  <TableRow key={index}>
                    <TableCell className="text-sm">{log.time}</TableCell>
                    <TableCell>{log.user}</TableCell>
                    <TableCell><Badge variant="outline">{log.action}</Badge></TableCell>
                    <TableCell className="text-sm">{log.detail}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{log.ip}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* 版本日志 */}
      {activeTab === 'changelog' && (
        <Card>
          <CardHeader>
            <CardTitle>版本更新日志</CardTitle>
            <CardDescription>记录每次发版的功能更新与修复内容</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {releaseLog.map((release) => (
                <div key={release.version} className="border-l-2 border-primary pl-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex items-center gap-1.5">
                      <Tag className="h-4 w-4 text-primary" />
                      <span className="font-semibold text-base">{release.version}</span>
                    </div>
                    <span className="text-sm text-muted-foreground">{release.date}</span>
                  </div>
                  <ul className="space-y-1">
                    {release.items.map((item, i) => (
                      <li key={i} className="text-sm text-muted-foreground flex gap-2">
                        <span className="text-primary mt-0.5">·</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 用户管理 */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">管理系统用户，分配角色与权限</p>
            <Button onClick={() => { setEditUserId(null); setUserForm(emptyUserForm); setUserError(''); setShowUserForm(true) }}>
              <Plus className="h-4 w-4 mr-1" />新增用户
            </Button>
          </div>

          {showUserForm && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{editUserId ? '编辑用户' : '新增用户'}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium">用户名 {requiredMark}</label>
                    <Input value={userForm.username} onChange={(e) => setUserForm({ ...userForm, username: e.target.value })} disabled={!!editUserId} placeholder="登录用户名" />
                  </div>
                  <div>
                    <label className="text-sm font-medium">
                      {editUserId ? '新密码（留空不修改）' : <>密码 {requiredMark}</>}
                    </label>
                    <Input type="password" value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} placeholder={editUserId ? '留空不修改' : '至少6位'} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">姓名</label>
                    <Input value={userForm.real_name} onChange={(e) => setUserForm({ ...userForm, real_name: e.target.value })} placeholder="真实姓名" />
                  </div>
                  <div>
                    <label className="text-sm font-medium">部门</label>
                    <Input value={userForm.department} onChange={(e) => setUserForm({ ...userForm, department: e.target.value })} placeholder="所属部门" />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">角色</label>
                  <div className="flex gap-4 mt-1">
                    <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                      <input type="radio" name="role" checked={userForm.role === 'user'} onChange={() => setUserForm({ ...userForm, role: 'user' })} />普通用户
                    </label>
                    <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                      <input type="radio" name="role" checked={userForm.role === 'admin'} onChange={() => setUserForm({ ...userForm, role: 'admin' })} />管理员
                    </label>
                  </div>
                </div>
                {userError && <div className="text-sm text-destructive">{userError}</div>}
                <div className="flex gap-2">
                  <Button disabled={userSaving} onClick={async () => {
                    setUserError('')
                    if (!userForm.username.trim()) { setUserError('用户名不能为空'); return }
                    if (!editUserId && userForm.password.length < 6) { setUserError('密码至少6位'); return }
                    if (editUserId && userForm.password && userForm.password.length < 6) { setUserError('密码至少6位'); return }
                    setUserSaving(true)
                    try {
                      const url = editUserId ? `${API_BASE_URL}/auth/users/${editUserId}` : `${API_BASE_URL}/auth/users`
                      const method = editUserId ? 'PUT' : 'POST'
                      const body = editUserId
                        ? JSON.stringify({ real_name: userForm.real_name, department: userForm.department, role: userForm.role, ...(userForm.password ? { password: userForm.password } : {}) })
                        : JSON.stringify(userForm)
                      const r = await fetch(url, { method, headers: authHeaders, body })
                      if (!r.ok) { const err = await r.json().catch(() => ({})); setUserError(err.detail || '操作失败'); return }
                      setShowUserForm(false)
                      fetchUsers()
                    } finally { setUserSaving(false) }
                  }}>{userSaving ? '保存中...' : '保存'}</Button>
                  <Button variant="outline" onClick={() => setShowUserForm(false)}>取消</Button>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium">用户名</th>
                    <th className="px-4 py-3 text-left font-medium">姓名</th>
                    <th className="px-4 py-3 text-left font-medium">部门</th>
                    <th className="px-4 py-3 text-left font-medium">角色</th>
                    <th className="px-4 py-3 text-left font-medium">状态</th>
                    <th className="px-4 py-3 text-left font-medium">创建时间</th>
                    <th className="px-4 py-3 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {usersLoading ? (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">加载中...</td></tr>
                  ) : users.length === 0 ? (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">暂无用户</td></tr>
                  ) : users.map((u) => (
                    <tr key={u.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="px-4 py-2.5 font-medium">{u.username}</td>
                      <td className="px-4 py-2.5">{u.real_name || '-'}</td>
                      <td className="px-4 py-2.5">{u.department || '-'}</td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs ${u.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
                          {u.role === 'admin' ? <ShieldCheck className="h-3 w-3" /> : <User className="h-3 w-3" />}
                          {u.role === 'admin' ? '管理员' : '普通用户'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                          {u.is_active ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                          {u.is_active ? '启用' : '禁用'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{u.created_at ? u.created_at.replace('T', ' ').split('.')[0] : '-'}</td>
                      <td className="px-4 py-2.5 text-right">
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="ghost" title="编辑" onClick={() => {
                            setEditUserId(u.id)
                            setUserForm({ username: u.username, password: '', real_name: u.real_name, department: u.department, role: u.role as 'admin' | 'user' })
                            setUserError('')
                            setShowUserForm(true)
                          }}><Pencil className="h-3.5 w-3.5" /></Button>
                          <Button size="sm" variant="ghost" title={u.is_active ? '禁用' : '启用'} onClick={async () => {
                            await fetch(`${API_BASE_URL}/auth/users/${u.id}`, { method: 'PUT', headers: authHeaders, body: JSON.stringify({ is_active: !u.is_active }) })
                            fetchUsers()
                          }}>{u.is_active ? <X className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}</Button>
                          {u.username !== 'admin' && (
                            <Button size="sm" variant="ghost" className="text-destructive" title="删除" onClick={async () => {
                              if (!confirm(`确定删除用户「${u.real_name || u.username}」？`)) return
                              await fetch(`${API_BASE_URL}/auth/users/${u.id}`, { method: 'DELETE', headers: authHeaders })
                              fetchUsers()
                            }}><Trash2 className="h-3.5 w-3.5" /></Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
