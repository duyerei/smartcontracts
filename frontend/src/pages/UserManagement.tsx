import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus, Pencil, Trash2, ShieldCheck, User, Check, X } from 'lucide-react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

interface UserItem {
  id: number
  username: string
  real_name: string
  department: string
  role: string
  is_active: boolean
  created_at: string | null
}

interface UserForm {
  username: string
  password: string
  real_name: string
  department: string
  role: 'admin' | 'user'
}

const emptyForm: UserForm = { username: '', password: '', real_name: '', department: '', role: 'user' }

export function UserManagement() {
  const { token } = useAuth()
  const [users, setUsers] = useState<UserItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState<UserForm>(emptyForm)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API_BASE_URL}/auth/users`, { headers })
      if (r.ok) setUsers(await r.json())
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const openCreate = () => {
    setEditId(null)
    setForm(emptyForm)
    setError('')
    setShowForm(true)
  }

  const openEdit = (u: UserItem) => {
    setEditId(u.id)
    setForm({ username: u.username, password: '', real_name: u.real_name, department: u.department, role: u.role as 'admin' | 'user' })
    setError('')
    setShowForm(true)
  }

  const handleSave = async () => {
    setError('')
    if (!form.username.trim()) { setError('用户名不能为空'); return }
    if (!editId && form.password.length < 6) { setError('密码至少6位'); return }
    if (editId && form.password && form.password.length < 6) { setError('密码至少6位'); return }
    setSaving(true)
    try {
      const url = editId ? `${API_BASE_URL}/auth/users/${editId}` : `${API_BASE_URL}/auth/users`
      const method = editId ? 'PUT' : 'POST'
      const body = editId
        ? JSON.stringify({ real_name: form.real_name, department: form.department, role: form.role, ...(form.password ? { password: form.password } : {}) })
        : JSON.stringify(form)
      const r = await fetch(url, { method, headers, body })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(err.detail || '操作失败')
        return
      }
      setShowForm(false)
      fetchUsers()
    } finally {
      setSaving(false)
    }
  }

  const handleToggleActive = async (u: UserItem) => {
    await fetch(`${API_BASE_URL}/auth/users/${u.id}`, {
      method: 'PUT', headers, body: JSON.stringify({ is_active: !u.is_active }),
    })
    fetchUsers()
  }

  const handleDelete = async (u: UserItem) => {
    if (!confirm(`确定删除用户「${u.real_name || u.username}」？`)) return
    await fetch(`${API_BASE_URL}/auth/users/${u.id}`, { method: 'DELETE', headers })
    fetchUsers()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">用户管理</h1>
          <p className="text-muted-foreground text-sm">管理系统用户，分配角色与权限</p>
        </div>
        <Button onClick={openCreate}><Plus className="h-4 w-4 mr-1" />新增用户</Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{editId ? '编辑用户' : '新增用户'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">用户名 *</label>
                <Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} disabled={!!editId} placeholder="登录用户名" />
              </div>
              <div>
                <label className="text-sm font-medium">{editId ? '新密码（留空不修改）' : '密码 *'}</label>
                <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder={editId ? '留空不修改' : '至少6位'} />
              </div>
              <div>
                <label className="text-sm font-medium">姓名</label>
                <Input value={form.real_name} onChange={(e) => setForm({ ...form, real_name: e.target.value })} placeholder="真实姓名" />
              </div>
              <div>
                <label className="text-sm font-medium">部门</label>
                <Input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="所属部门" />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">角色</label>
              <div className="flex gap-4 mt-1">
                <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                  <input type="radio" name="role" checked={form.role === 'user'} onChange={() => setForm({ ...form, role: 'user' })} />
                  普通用户
                </label>
                <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                  <input type="radio" name="role" checked={form.role === 'admin'} onChange={() => setForm({ ...form, role: 'admin' })} />
                  管理员
                </label>
              </div>
            </div>
            {error && <div className="text-sm text-destructive">{error}</div>}
            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={saving}>{saving ? '保存中...' : '保存'}</Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>取消</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">用户名</th>
                <th className="px-4 py-3 text-left font-medium">姓名</th>
                <th className="px-4 py-3 text-left font-medium">部门</th>
                <th className="px-4 py-3 text-left font-medium">角色</th>
                <th className="px-4 py-3 text-left font-medium">状态</th>
                <th className="px-4 py-3 text-left font-medium">创建时间</th>
                <th className="px-4 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">加载中...</td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">暂无用户</td></tr>
              ) : users.map((u) => (
                <tr key={u.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2.5 font-medium">{u.username}</td>
                  <td className="px-4 py-2.5">{u.real_name || '-'}</td>
                  <td className="px-4 py-2.5">{u.department || '-'}</td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs ${u.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
                      {u.role === 'admin' ? <ShieldCheck className="h-3 w-3" /> : <User className="h-3 w-3" />}
                      {u.role === 'admin' ? '管理员' : '普通用户'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {u.is_active ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                      {u.is_active ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{u.created_at ? u.created_at.replace('T', ' ').split('.')[0] : '-'}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(u)} title="编辑"><Pencil className="h-3.5 w-3.5" /></Button>
                      <Button size="sm" variant="ghost" onClick={() => handleToggleActive(u)} title={u.is_active ? '禁用' : '启用'}>
                        {u.is_active ? <X className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}
                      </Button>
                      {u.username !== 'admin' && (
                        <Button size="sm" variant="ghost" className="text-destructive" onClick={() => handleDelete(u)} title="删除"><Trash2 className="h-3.5 w-3.5" /></Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
