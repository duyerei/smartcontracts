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
  Users,
  Network,
  KeyRound,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

const uploadPagePermissions = [
  'contract.create',
  'payment.import_pdf',
  'contract.import_oa',
]

type NavItem = {
  to: string
  icon: ComponentType<{ className?: string }>
  label: string
  permission?: string
  permissions?: string[]
}

const navItems: NavItem[] = [
  { to: '/', icon: LayoutDashboard, label: '工作台', permission: 'dashboard.view' },
  { to: '/contracts', icon: FileText, label: '合同管理', permission: 'contract.view' },
  { to: '/partners', icon: Building2, label: '合作伙伴', permission: 'partner.view' },
  { to: '/payments', icon: CreditCard, label: '付款管理', permission: 'payment.view' },
  { to: '/upload', icon: FolderInput, label: '数据导入', permissions: uploadPagePermissions },
  { to: '/import', icon: Download, label: 'OA导入', permission: 'contract.import_oa' },
]

const systemNavItems: NavItem[] = [
  { to: '/settings', icon: Settings, label: '系统设置', permission: 'settings.view' },
  { to: '/users', icon: Users, label: '用户管理', permission: 'user.view' },
  { to: '/orgs', icon: Network, label: '组织架构', permission: 'org.view' },
  { to: '/roles', icon: KeyRound, label: '角色权限', permission: 'role.view' },
]

export function Sidebar() {
  const { user, logout, hasPermission } = useAuth()
  const navigate = useNavigate()
  const canViewItem = (item: NavItem) => {
    if (!item.permission && !item.permissions) return true
    if (item.permission) return hasPermission(item.permission)
    return !!item.permissions?.some(hasPermission)
  }
  const visibleNavItems = navItems.filter(canViewItem)
  const visibleSystemNavItems = systemNavItems.filter(canViewItem)
  const roleSummary = user?.roles?.map((item) => item.name).join(' / ')

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
        {visibleNavItems.map((item) => (
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
        {visibleSystemNavItems.length > 0 && (
          <div className="pt-2">
            <div className="flex items-center gap-3 px-4 py-3 text-sm font-medium text-muted-foreground">
              <Settings className="h-5 w-5" />
              系统管理
            </div>
            <div className="ml-4 space-y-1 border-l pl-3">
              {visibleSystemNavItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )
                  }
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </nav>
      <div className="p-4 border-t space-y-3">
        {user && (
          <div className="flex items-center justify-between">
            <div className="text-xs">
              <p className="font-medium text-foreground">{user.real_name || user.username}</p>
              <p className="text-muted-foreground">{roleSummary || (user.role === 'admin' ? '管理员' : '普通用户')}</p>
              {user.primary_org_name && <p className="text-muted-foreground">{user.primary_org_name}</p>}
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
