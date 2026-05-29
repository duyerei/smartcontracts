import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { agentApi, type AgentChatResponse, type AgentOperation } from '@/lib/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  operation?: AgentOperation
  data?: Record<string, unknown>[]
  requires_confirmation?: boolean
}

function renderData(data?: Record<string, unknown>[]) {
  if (!data || data.length === 0) return null

  return (
    <div className="mt-3 rounded border bg-muted/30 p-3 text-xs overflow-x-auto">
      <pre className="whitespace-pre-wrap">{JSON.stringify(data, null, 2)}</pre>
    </div>
  )
}

export function AgentAssistant() {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingOperation, setPendingOperation] = useState<AgentOperation | undefined>(undefined)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: '你好，我是合同助手。你可以让我：\n1) 查询合同列表\n2) 查看合同详情（如：查看合同16）\n3) 重新解析合同（如：重新解析合同16）\n4) 删除合同（会二次确认）',
    },
  ])

  const sendMessage = async (confirm = false) => {
    const message = input.trim()
    if (!message && !confirm) return

    if (!confirm) {
      setMessages((prev) => [...prev, { role: 'user', content: message }])
      setInput('')
    }

    setLoading(true)
    const result = await agentApi.chat(message || '确认执行', confirm, confirm ? pendingOperation : undefined)
    setLoading(false)

    if (result.error || !result.data) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `请求失败：${result.error || '未知错误'}` }])
      return
    }

    const payload: AgentChatResponse = result.data
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: payload.reply,
        operation: payload.operation,
        data: payload.data,
        requires_confirmation: payload.requires_confirmation,
      },
    ])

    if (payload.requires_confirmation && payload.operation) {
      setPendingOperation(payload.operation)
    } else {
      setPendingOperation(undefined)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>多智能体协同Agent（MVP）</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[60vh] overflow-y-auto space-y-3 rounded border p-3 bg-background">
            {messages.map((m, idx) => (
              <div key={idx} className={m.role === 'user' ? 'text-right' : 'text-left'}>
                <div
                  className={`inline-block max-w-[85%] rounded px-3 py-2 text-sm whitespace-pre-wrap ${
                    m.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'
                  }`}
                >
                  {m.content}
                </div>
                {renderData(m.data)}
                {m.requires_confirmation && (
                  <div className="mt-2">
                    <Button size="sm" variant="destructive" onClick={() => sendMessage(true)} disabled={loading}>
                      确认执行
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-4 flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入：查询合同列表 / 查看合同16 / 重新解析合同16 / 删除合同16"
              onKeyDown={(e) => {
                if (e.key === 'Enter') sendMessage()
              }}
            />
            <Button onClick={() => sendMessage()} disabled={loading}>
              {loading ? '处理中...' : '发送'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
