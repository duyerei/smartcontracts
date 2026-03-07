import { NavLink, useNavigate } from 'react-router-dom'
import { 
  LayoutDashboard, 
  FileText, 
  Settings,
  Shield,
  LogOut,
  Download,
  CreditCard,
  Building2,
  FolderInput,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '工作台' },
  { to: '/contracts', icon: FileText, label: '合同管理' },
  { to: '/partners', icon: Building2, label: '合作伙伴' },
  { to: '/payments', icon: CreditCard, label: '付款管理' },
  { to: '/upload', icon: FolderInput, label: '数据导入' },
  { to: '/settings', icon: Settings, label: '系统设置' },
]

const adminNavItems = [
  { to: '/import', icon: Download, label: 'OA导入(旧)' },
]

export function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="w-64 border-r bg-card h-screen flex flex-col">
      <div className="p-6 border-b">
        <div className="flex items-center gap-2">
          <Shield className="h-8 w-8 text-primary" />
          <div>
            <h1 className="font-bold text-lg">AI合同管理</h1>
            <p className="text-xs text-muted-foreground">智能合同管理系统</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t space-y-3">
        {user && (
          <div className="flex items-center justify-between">
            <div className="text-xs">
              <p className="font-medium text-foreground">{user.real_name || user.username}</p>
              <p className="text-muted-foreground">{user.role === 'admin' ? '管理员' : '普通用户'}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="退出登录"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
        <div className="text-xs text-muted-foreground">
          <p>版本: v1.0.0</p>
        </div>
      </div>
    </aside>
  )
}
