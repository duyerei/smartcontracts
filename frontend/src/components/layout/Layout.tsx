import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { AgentChatWidget } from '@/components/agent/AgentChatWidget'

export function Layout() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto bg-muted/30 p-6 pr-[416px]">
          {/* pr-[416px] = 400px(AI助手宽度) + 16px(padding) */}
          <Outlet />
        </main>
      </div>
      {/* AI助手窗口 - 全局显示 */}
      <AgentChatWidget />
    </div>
  )
}
