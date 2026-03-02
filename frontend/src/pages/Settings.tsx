import { useState } from 'react'
import { 
  Settings, 
  Key, 
  Server, 
  Shield, 
  Users,
  Activity,
  Plus,
  Copy,
  Trash2,
  CheckCircle,
  XCircle,
  RefreshCw
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  status: 'active' | 'in MCPConnectionactive'
}

interface MCPConnection {
  name: string
  serverUrl: string
  status: 'connected' | 'disconnected'
  lastConnected: string | null
}

const mockAPIKeys: APIKey[] = [
  {
    id: '1',
    name: '生产环境API',
    key: 'sk-**** **** **** ****',
    createdAt: '2025-01-15',
    lastUsed: '2025-01-28',
    status: 'active',
  },
  {
    id: '2',
    name: '测试环境API',
    key: 'sk-**** **** **** ****',
    createdAt: '2025-01-10',
    lastUsed: '2025-01-25',
    status: 'active',
  },
]

const mockMCPConnections: MCPConnection[] = [
  {
    name: 'Claude Desktop',
    serverUrl: 'http://localhost:3001',
    status: 'connected',
    lastConnected: '2025-01-28 10:30',
  },
  {
    name: '企业Agent',
    serverUrl: 'http://agent.company.com:8080',
    status: 'disconnected',
    lastConnected: null,
  },
]

export function SettingsPage() {
  const [apiKeys, setAPIKeys] = useState<APIKey[]>(mockAPIKeys)
  const [mcpConnections, setMCPConnections] = useState<MCPConnection[]>(mockMCPConnections)
  const [newKeyName, setNewKeyName] = useState('')
  const [activeTab, setActiveTab] = useState('api')

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

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

  const deleteAPIKey = (id: string) => {
    setAPIKeys(apiKeys.filter(k => k.id !== id))
  }

  const toggleMCPConnection = (name: string) => {
    setMCPConnections(connections => 
      connections.map(conn => 
        conn.name === name 
          ? { 
              ...conn, 
              status: conn.status === 'connected' ? 'disconnected' : 'connected',
              lastConnected: conn.status === 'dis new Date().toconnected' ?LocaleString() : conn.lastConnected
            }
          : conn
      )
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">系统设置</h1>
        <p className="text-muted-foreground">
          管理API密钥、MCP连接和系统配置
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="api" className="flex items-center gap-2">
            <Key className="h-4 w-4" />
            API管理
          </TabsTrigger>
          <TabsTrigger value="mcp" className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            MCP配置
          </TabsTrigger>
          <TabsTrigger value="security" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            安全设置
          </TabsTrigger>
          <TabsTrigger value="logs" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            审计日志
          </TabsTrigger>
        </TabsList>

        <TabsContent value="api" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>API密钥管理</CardTitle>
              <CardDescription>
                创建和管理API密钥，用于调用系统REST API
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 mb-6">
                <Input
                  placeholder="输入密钥名称"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  className="max-w-xs"
                />
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
                          <code className="text-sm bg-muted px-2 py-1 rounded">
                            {apiKey.key}
                          </code>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => copyToClipboard(apiKey.key)}
                          >
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
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteAPIKey(apiKey.id)}
                        >
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
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">今日调用</p>
                  <p className="text-2xl font-bold">1,234</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">本周调用</p>
                  <p className="text-2xl font-bold">8,567</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">本月调用</p>
                  <p className="text-2xl font-bold">32,456</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">平均响应</p>
                  <p className="text-2xl font-bold">1.2s</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mcp" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>MCP连接</CardTitle>
              <CardDescription>
                配置MCP Server连接，使AI Agent能够调用本系统
              </CardDescription>
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
                      <TableCell>
                        <code className="text-sm bg-muted px-2 py-1 rounded">
                          {conn.serverUrl}
                        </code>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {conn.status === 'connected' ? (
                            <>
                              <CheckCircle className="h-4 w-4 text-green-500" />
                              <span className="text-green-500">已连接</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="h-4 w-4 text-red-500" />
                              <span className="text-red-500">未连接</span>
                            </>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{conn.lastUsed || '-'}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant={conn.status === 'connected' ? 'destructive' : 'default'}
                          size="sm"
                          onClick={() => toggleMCPConnection(conn.name)}
                        >
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
        </TabsContent>

        <TabsContent value="security" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>安全设置</CardTitle>
              <CardDescription>配置系统安全选项</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">数据脱敏</p>
                  <p className="text-sm text-muted-foreground">
                    调用LLM前自动脱敏敏感信息
                  </p>
                </div>
                <Button variant="outline">配置</Button>
              </div>
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">RBAC权限控制</p>
                  <p className="text-sm text-muted-foreground">
                    基于角色的访问权限管理
                  </p>
                </div>
                <Button variant="outline">管理</Button>
              </div>
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <p className="font-medium">API调用限制</p>
                  <p className="text-sm text-muted-foreground">
                    设置API调用频率限制
                  </p>
                </div>
                <Button variant="outline">配置</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs" className="space-y-6 mt-6">
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
                      <TableCell>
                        <Badge variant="outline">{log.action}</Badge>
                      </TableCell>
                      <TableCell className="text-sm">{log.detail}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{log.ip}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
