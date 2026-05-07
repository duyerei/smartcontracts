import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export interface AuthUser {
  id: number
  username: string
  real_name: string
  department: string
  role: 'admin' | 'user'
  primary_org_id?: number | null
  primary_org_name?: string | null
  role_ids?: number[]
  roles?: Array<{ id: number; code: string; name: string }>
  permissions?: string[]
  data_scopes?: Record<string, { scope_type?: string | null; scope_types?: string[]; org_ids?: number[] }>
  is_active: boolean
}

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  loading: boolean
  hasPermission: (permission: string) => boolean
  login: (username: string, password: string) => Promise<string | null>
  logout: () => void
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  hasPermission: () => false,
  login: async () => null,
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (token) {
      fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => {
          if (!r.ok) throw new Error()
          return r.json()
        })
        .then((data) => setUser(data))
        .catch(() => {
          localStorage.removeItem('token')
          setToken(null)
          setUser(null)
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [token])

  const hasPermission = (permission: string) => {
    if (!user) return false
    if (user.role === 'admin') return true
    return !!user.permissions?.includes(permission)
  }

  const login = async (username: string, password: string): Promise<string | null> => {
    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)

      const resp = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        return err.detail || '登录失败'
      }

      const data = await resp.json()
      localStorage.setItem('token', data.access_token)
      setToken(data.access_token)
      setUser(data.user)
      return null
    } catch {
      return '网络错误，请稍后重试'
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, hasPermission, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
