import { useRoutes, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { ContractList } from '@/pages/ContractList'
import { ContractDetail } from '@/pages/ContractDetail'
import { UploadContract } from '@/pages/UploadContract'
import { Search } from '@/pages/Search'
import { SettingsPage } from '@/pages/Settings'
import { Login } from '@/pages/Login'
import { UserManagement } from '@/pages/UserManagement'
import { useAuth } from '@/contexts/AuthContext'
import type { ReactNode } from 'react'

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-muted-foreground">加载中...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return <>{children}</>
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-muted-foreground">加载中...</div>
  if (user) return <Navigate to="/" replace />
  return <>{children}</>
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
        element: <Dashboard />,
      },
      {
        path: 'contracts',
        element: <ContractList />,
      },
      {
        path: 'contracts/:id',
        element: <ContractDetail />,
      },
      {
        path: 'upload',
        element: <UploadContract />,
      },
      {
        path: 'search',
        element: <Search />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      {
        path: 'users',
        element: <RequireAdmin><UserManagement /></RequireAdmin>,
      },
    ],
  },
]

export function AppRoutes() {
  return useRoutes(routes)
}
