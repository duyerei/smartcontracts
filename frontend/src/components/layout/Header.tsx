import { useNavigate } from 'react-router-dom'
import { Bell, User, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'

export function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="h-16 border-b bg-card px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold">AI智能合同管理系统</h2>
      </div>
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
        </Button>
        <div className="flex items-center gap-2 border-l pl-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
              <User className="h-4 w-4 text-primary-foreground" />
            </div>
            <div className="text-sm">
              <p className="font-medium">{user?.real_name || user?.username || '用户'}</p>
              <p className="text-xs text-muted-foreground">{user?.role === 'admin' ? '管理员' : '普通用户'}{user?.department ? ` · ${user.department}` : ''}</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={handleLogout} title="退出登录">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}
