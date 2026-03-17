import { useState } from 'react'
import { X, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { agentApi, type AgentChatResponse, type AgentOperation } from '@/lib/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  operation?: AgentOperation
  data?: Record<string, unknown>[]
  requires_confirmation?: boolean
  provider?: 'ark' | 'appbuilder' | 'qianfan' | 'bailian' | 'bailian_llm' | 'rule'
  conversationId?: string
  errorDetail?: string
}

export function AgentChatWidget() {
  const [open, setOpen] = useState(false) // 默认收起
  const [conversationId, setConversationId] = useState<string | undefined>(undefined)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingOperation, setPendingOperation] = useState<AgentOperation | undefined>(undefined)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: '你好！我是AI助手，可以帮你查询合同、查看详情、重新解析等操作。',
    },
  ])

  // 辅助函数：安全地转换为字符串
  const toStr = (value: unknown): string => String(value || '')

  const sendMessage = async (confirm = false) => {
    const message = input.trim()
    if (!message && !confirm) return

    if (!confirm) {
      setMessages((prev) => [...prev, { role: 'user', content: message }])
      setInput('')
    }

    setLoading(true)

    const result = await agentApi.chat(
      message || '确认执行',
      confirm,
      confirm ? pendingOperation : undefined,
      conversationId,
    )

    if (result.error || !result.data) {
      setLoading(false)
      setMessages((prev) => [...prev, { role: 'assistant', content: `请求失败：${result.error || '未知错误'}` }])
      return
    }

    const payload: AgentChatResponse = result.data

    if (payload.conversation_id) setConversationId(payload.conversation_id)
    if (payload.requires_confirmation && payload.operation) {
      setPendingOperation(payload.operation)
    } else {
      setPendingOperation(undefined)
    }

    const isConsult = payload.provider !== 'rule' && (!payload.operation || payload.operation.action === 'consult')

    if (isConsult) {
      setMessages((prev) => [...prev, { role: 'assistant', content: '思考中...' }])

      await agentApi.chatStream(
        message,
        conversationId,
        (text) => {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'assistant') {
              updated[updated.length - 1] = { ...last, content: text }
            }
            return updated
          })
        },
        (cid, provider) => {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'assistant') {
              updated[updated.length - 1] = {
                ...last,
                provider: provider as 'ark' | 'appbuilder' | 'qianfan' | 'bailian' | 'bailian_llm' | 'rule',
                conversationId: cid,
              }
            }
            return updated
          })
          if (cid) setConversationId(cid)
          setLoading(false)
        },
        () => {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'assistant') {
              updated[updated.length - 1] = {
                ...last,
                content: payload.reply || '抱歉，暂时无法回复。',
                provider: payload.provider,
                conversationId: payload.conversation_id,
                errorDetail: payload.error_detail,
              }
            }
            return updated
          })
          setLoading(false)
        },
      )
      return
    }

    setLoading(false)
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: payload.reply,
        operation: payload.operation,
        data: payload.data,
        requires_confirmation: payload.requires_confirmation,
        provider: payload.provider,
        conversationId: payload.conversation_id,
        errorDetail: payload.error_detail,
      },
    ])
  }

  return (
    <>
      {/* 收起状态 - 右侧悬浮按钮 */}
      {!open && (
        <div className="fixed right-0 top-1/2 -translate-y-1/2 z-50">
          
          <button
            onClick={() => setOpen(true)}
            className="relative group flex flex-col items-center gap-2 bg-gradient-to-br from-blue-500 to-blue-600 text-white px-3 py-6 rounded-l-2xl shadow-lg hover:shadow-xl transition-all duration-300 hover:px-4"
          >
            {/* AI虚拟形象 */}
            <div className="relative">
              <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-md group-hover:scale-110 transition-transform">
                <svg className="w-7 h-7 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-5-9c.83 0 1.5-.67 1.5-1.5S7.83 8 7 8s-1.5.67-1.5 1.5S6.17 11 7 11zm10 0c.83 0 1.5-.67 1.5-1.5S17.83 8 17 8s-1.5.67-1.5 1.5.67 1.5 1.5 1.5zm-5 5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"/>
                </svg>
              </div>
              {/* 呼吸光效 */}
              <div className="absolute inset-0 bg-white/20 rounded-full animate-pulse" />
            </div>
            
            {/* 文字 */}
            <div className="writing-mode-vertical text-sm font-medium tracking-wider">
              AI助手
            </div>
            
            {/* 小箭头提示 */}
            <div className="text-xs opacity-70 group-hover:opacity-100 transition-opacity">
              ◀
            </div>
          </button>
        </div>
      )}

      {/* 展开状态 - 右侧面板 */}
      {open && (
        <div className="fixed right-0 top-0 h-screen w-[400px] z-50 bg-white shadow-2xl border-l border-gray-200 flex flex-col animate-in slide-in-from-right duration-300">
          {/* 头部 */}
          <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center shadow-md">
                <svg className="w-6 h-6 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-5-9c.83 0 1.5-.67 1.5-1.5S7.83 8 7 8s-1.5.67-1.5 1.5S6.17 11 7 11zm10 0c.83 0 1.5-.67 1.5-1.5S17.83 8 17 8s-1.5.67-1.5 1.5.67 1.5 1.5 1.5z"/>
                </svg>
              </div>
              <div>
                <div className="font-semibold text-base">AI智能助手</div>
                <div className="text-xs text-white/80">智能解答 高效便捷</div>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/20 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 快捷问题（可选） */}
          {messages.length === 1 && (
            <div className="px-6 py-4 bg-blue-50 border-b border-blue-100">
              <div className="text-xs text-gray-600 mb-2">为你推荐：</div>
              <div className="space-y-2">
                {[
                  '查看所有合同',
                  '即将到期的合同'
                ].map((q, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setInput(q)
                      setTimeout(() => sendMessage(), 100)
                    }}
                    className="block w-full text-left px-3 py-2 text-sm text-gray-700 bg-white rounded-lg hover:bg-blue-50 hover:text-blue-600 transition-colors border border-gray-200"
                  >
                    • {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 聊天内容区 */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 bg-gray-50">
            {messages.map((m, idx) => (
              <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] ${m.role === 'user' ? 'order-2' : 'order-1'}`}>
                  {/* 消息气泡 */}
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm shadow-sm ${
                      m.role === 'user'
                        ? 'bg-blue-500 text-white rounded-br-sm'
                        : 'bg-white text-gray-800 rounded-bl-sm border border-gray-200'
                    }`}
                  >
                    <div className="whitespace-pre-wrap break-words leading-relaxed">{m.content}</div>
                  </div>

                  {/* 合同数据卡片 */}
                  {m.data && m.data.length > 0 && (
                    <div className="mt-2 space-y-2">
                      {m.data.map((item, i) => {
                        const contractItem = item as Record<string, unknown>
                        return (
                          <div key={i} className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <a
                                href={`/contracts/${contractItem.id}`}
                                className="font-medium text-blue-600 hover:text-blue-700 hover:underline text-sm flex-1"
                                title={toStr(contractItem.title)}
                              >
                                {toStr(contractItem.title) || `合同${contractItem.id}`}
                              </a>
                              <span className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] text-blue-600 font-medium">
                                {toStr(contractItem.status)}
                              </span>
                            </div>
                            <div className="space-y-1 text-[11px] text-gray-500">
                              <div>编号: {toStr(contractItem.contract_number)}</div>
                              <div>类型: {toStr(contractItem.contract_type)}</div>
                              <div>部门: {toStr(contractItem.department)}</div>
                              {contractItem.amount != null && <div>金额: ¥{Number(contractItem.amount).toLocaleString()}</div>}
                              <div>到期: {toStr(contractItem.end_date)}</div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* 元信息 */}
                  {(m.provider || m.conversationId || m.errorDetail) && (
                    <div className="mt-1 text-[10px] text-gray-400 px-1">
                      {m.provider && <span className="mr-2">来源: {m.provider}</span>}
                      {m.conversationId && <span className="mr-2">会话: {m.conversationId.slice(0, 8)}</span>}
                      {m.errorDetail && <span className="text-red-400">错误: {m.errorDetail}</span>}
                    </div>
                  )}

                  {/* 确认按钮 */}
                  {m.requires_confirmation && (
                    <div className="mt-2">
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => sendMessage(true)}
                        disabled={loading}
                        className="rounded-full text-xs"
                      >
                        确认执行
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* 加载动画 */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white rounded-2xl rounded-bl-sm px-4 py-3 border border-gray-200 shadow-sm">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 输入区 */}
          <div className="px-6 py-4 bg-white border-t border-gray-200">
            <div className="flex gap-2 items-end">
              <div className="flex-1 relative">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="请输入你想问的问题..."
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      sendMessage()
                    }
                  }}
                  className="rounded-full border-gray-300 focus:border-blue-500 focus:ring-blue-500 pr-10"
                  disabled={loading}
                />
              </div>
              <Button
                size="icon"
                onClick={() => sendMessage()}
                disabled={loading || !input.trim()}
                className="rounded-full bg-blue-500 hover:bg-blue-600 shrink-0 w-10 h-10"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <div className="mt-2 text-[10px] text-gray-400 text-center">
              AI生成内容仅供参考
            </div>
          </div>
        </div>
      )}

      {/* 添加竖排文字样式 */}
      <style>{`
        .writing-mode-vertical {
          writing-mode: vertical-rl;
          text-orientation: upright;
        }
      `}</style>
    </>
  )
}
