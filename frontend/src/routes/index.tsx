import { useRoutes, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { ContractList } from '@/pages/ContractList'
import { ContractDetail } from '@/pages/ContractDetail'
import { UploadContract } from '@/pages/UploadContract'
import ImportContracts from '@/pages/ImportContracts'
import { Search } from '@/pages/Search'
import { SettingsPage } from '@/pages/Settings'
import { Login } from '@/pages/Login'
import { UserManagement } from '@/pages/UserManagement'
import { OrgManagement } from '@/pages/OrgManagement'
import { RoleManagement } from '@/pages/RoleManagement'
import { PaymentManagementList } from '@/pages/PaymentManagementList'
import { PaymentManagementDetail } from '@/pages/PaymentManagementDetail'
import { PartnerList } from '@/pages/PartnerList'
import { PartnerDetail } from '@/pages/PartnerDetail'
import { useAuth } from '@/contexts/AuthContext'
import type { ReactNode } from 'react'

const UPLOAD_PAGE_PERMISSIONS = [
  'contract.create',
  'payment.import_pdf',
  'contract.import_oa',
]

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-muted-foreground">加载中...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function resolveFirstAccessiblePath(hasPermission: (permission: string) => boolean) {
  if (hasPermission('dashboard.view')) return '/'
  if (hasPermission('contract.view')) return '/contracts'
  if (hasPermission('payment.view')) return '/payments'
  if (hasPermission('partner.view')) return '/partners'
  if (UPLOAD_PAGE_PERMISSIONS.some(hasPermission)) return '/upload'
  if (hasPermission('contract.import_oa')) return '/import'
  if (hasPermission('user.view')) return '/users'
  if (hasPermission('org.view')) return '/orgs'
  if (hasPermission('role.view')) return '/roles'
  if (hasPermission('settings.view')) return '/settings'
  return '/login'
}

function RequirePermission({
  permission,
  children,
}: {
  permission: string
  children: ReactNode
}) {
  const { hasPermission } = useAuth()
  if (!hasPermission(permission)) {
    return <Navigate to={resolveFirstAccessiblePath(hasPermission)} replace />
  }
  return <>{children}</>
}

function RequireAnyPermission({
  permissions,
  children,
}: {
  permissions: string[]
  children: ReactNode
}) {
  const { hasPermission } = useAuth()
  if (!permissions.some(hasPermission)) {
    return <Navigate to={resolveFirstAccessiblePath(hasPermission)} replace />
  }
  return <>{children}</>
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading, hasPermission } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-muted-foreground">加载中...</div>
  if (user) {
    const target = resolveFirstAccessiblePath(hasPermission)
    return <Navigate to={target === '/login' ? '/' : target} replace />
  }
  return <>{children}</>
}

function DefaultLanding() {
  const { hasPermission } = useAuth()

  if (hasPermission('dashboard.view')) return <Dashboard />
  if (hasPermission('contract.view')) return <Navigate to="/contracts" replace />
  if (hasPermission('payment.view')) return <Navigate to="/payments" replace />
  if (hasPermission('partner.view')) return <Navigate to="/partners" replace />
  if (UPLOAD_PAGE_PERMISSIONS.some(hasPermission)) return <Navigate to="/upload" replace />
  if (hasPermission('contract.import_oa')) return <Navigate to="/import" replace />
  if (hasPermission('user.view')) return <Navigate to="/users" replace />
  if (hasPermission('org.view')) return <Navigate to="/orgs" replace />
  if (hasPermission('role.view')) return <Navigate to="/roles" replace />
  if (hasPermission('settings.view')) return <Navigate to="/settings" replace />

  return (
    <div className="flex h-[60vh] items-center justify-center text-sm text-muted-foreground">
      当前账号未分配可访问的页面权限，请联系管理员。
    </div>
  )
}

const routes = [
  {
    path: '/login',
    element: <GuestOnly><Login /></GuestOnly>,
  },
  {
    path: '/',
    element: <RequireAuth><Layout /></RequireAuth>,
    children: [
      {
        index: true,
        element: <DefaultLanding />,
      },
      {
        path: 'contracts',
        element: <RequirePermission permission="contract.view"><ContractList /></RequirePermission>,
      },
      {
        path: 'contracts/:id',
        element: <RequirePermission permission="contract.view"><ContractDetail /></RequirePermission>,
      },
      {
        path: 'upload',
        element: <RequireAnyPermission permissions={UPLOAD_PAGE_PERMISSIONS}><UploadContract /></RequireAnyPermission>,
      },
      {
        path: 'import',
        element: <RequirePermission permission="contract.import_oa"><ImportContracts /></RequirePermission>,
      },
      {
        path: 'search',
        element: <RequirePermission permission="contract.view"><Search /></RequirePermission>,
      },
      {
        path: 'settings',
        element: <RequirePermission permission="settings.view"><SettingsPage /></RequirePermission>,
      },
      {
        path: 'users',
        element: <RequirePermission permission="user.view"><UserManagement /></RequirePermission>,
      },
      {
        path: 'orgs',
        element: <RequirePermission permission="org.view"><OrgManagement /></RequirePermission>,
      },
      {
        path: 'roles',
        element: <RequirePermission permission="role.view"><RoleManagement /></RequirePermission>,
      },
      {
        path: 'payments',
        element: <RequirePermission permission="payment.view"><PaymentManagementList /></RequirePermission>,
      },
      {
        path: 'payments/:id',
        element: <RequirePermission permission="payment.view"><PaymentManagementDetail /></RequirePermission>,
      },
      {
        path: 'partners',
        element: <RequirePermission permission="partner.view"><PartnerList /></RequirePermission>,
      },
      {
        path: 'partners/:id',
        element: <RequirePermission permission="partner.view"><PartnerDetail /></RequirePermission>,
      },
    ],
  },
]

export function AppRoutes() {
  return useRoutes(routes)
}
