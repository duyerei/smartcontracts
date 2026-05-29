import { useEffect, useMemo, useState } from 'react'
import { Plus, Pencil, Trash2, Check, X, ShieldCheck, User as UserIcon, Link2, RefreshCw } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { cn } from '@/lib/utils'
import {
  authAdminApi,
  orgApi,
  roleApi,
  type AdminUserRecord,
  type DingTalkCandidateRecord,
  type OrgNode,
  type RoleRecord,
} from '@/lib/api'

interface UserFormState {
  username: string
  password: string
  real_name: string
  employee_no: string
  position_name: string
  dingtalk_user_id: string
  dingtalk_union_id: string
  dingtalk_open_id: string
  primary_org_id: string
  role_ids: number[]
}

const emptyForm: UserFormState = {
  username: '',
  password: '',
  real_name: '',
  employee_no: '',
  position_name: '',
  dingtalk_user_id: '',
  dingtalk_union_id: '',
  dingtalk_open_id: '',
  primary_org_id: '',
  role_ids: [],
}

const requiredMark = (
  <span className="ml-0.5 font-semibold" style={{ color: 'hsl(var(--destructive))' }} aria-hidden="true">
    *
  </span>
)

const scopeNames: Record<string, string> = {
  contract: '合同',
  payment: '付款',
  partner: '伙伴',
}

const commonWeakPasswords = new Set([
  '123456',
  '12345678',
  '123456789',
  '1234567890',
  'abcdefg',
  'abcdefgh',
  'abc12345',
  'abc123456',
  'password',
  'password123',
  'qwerty123',
  'admin123',
  'welcome123',
  '11111111',
  '00000000',
])

function flattenOrgs(items: OrgNode[], depth = 0): Array<OrgNode & { depth: number }> {
  return items.flatMap((item) => [
    { ...item, depth },
    ...flattenOrgs(item.children || [], depth + 1),
  ])
}

function isSelectablePrimaryOrg(org?: OrgNode | null) {
  if (!org) return false
  if (org.is_selectable !== undefined) return org.is_selectable
  return org.status === 'active' && org.org_type !== 'root' && (org.children?.length || 0) === 0
}

function scopeLabel(scopeType?: string | null) {
  switch (scopeType) {
    case 'ALL':
      return '全部'
    case 'ORG_ONLY':
      return '本组织'
    case 'ORG_AND_CHILDREN':
      return '本组织及下级'
    case 'SELF':
      return '仅本人'
    default:
      return scopeType || '未配置'
  }
}

function normalizeRoleIds(user: AdminUserRecord, roles: RoleRecord[]) {
  const validIds = user.role_ids.filter((id) => id > 0 && roles.some((role) => role.id === id))
  if (validIds.length > 0) return validIds

  if (user.role === 'admin') {
    const adminRole = roles.find((role) => ['super_admin', 'system_admin'].includes(role.code))
    if (adminRole) return [adminRole.id]
  }

  const fallbackRole = roles.find((role) => role.code === 'contract_operator')
  return fallbackRole ? [fallbackRole.id] : []
}

function deriveLegacyRole(roleIds: number[], roles: RoleRecord[]) {
  const selected = roles.filter((role) => roleIds.includes(role.id))
  return selected.some((role) => ['super_admin', 'system_admin'].includes(role.code)) ? 'admin' : 'user'
}

function buildSuggestedUsername(candidate: DingTalkCandidateRecord) {
  const suggestions = [
    candidate.employee_no,
    candidate.dingtalk_user_id,
    candidate.dingtalk_union_id,
    candidate.nick?.trim().replace(/\s+/g, ''),
  ]
  return suggestions.find((item) => item && item.trim())?.trim() || ''
}

function summarizeScopes(user: AdminUserRecord) {
  const parts = Object.entries(user.data_scopes || {}).map(([resource, scope]) => (
    `${scopeNames[resource] || resource}:${scopeLabel(scope.scope_type || scope.scope_types?.[0])}`
  ))
  return parts.length > 0 ? parts.join(' / ') : '-'
}

function validateStrongPassword(password: string, username: string, realName: string) {
  if (password.length < 8) return '密码至少 8 位'
  if (/\s/.test(password)) return '密码不能包含空格'
  if (!/[A-Z]/.test(password)) return '密码需包含大写字母'
  if (!/[a-z]/.test(password)) return '密码需包含小写字母'
  if (!/\d/.test(password)) return '密码需包含数字'
  if (!/[^A-Za-z0-9]/.test(password)) return '密码需包含特殊字符'
  if (commonWeakPasswords.has(password.toLowerCase()) || new Set(password).size === 1) {
    return '密码过于简单，请使用更复杂的密码'
  }

  const normalizedUsername = username.trim().toLowerCase()
  if (normalizedUsername.length >= 3 && password.toLowerCase().includes(normalizedUsername)) {
    return '密码不能包含用户名'
  }

  const normalizedRealName = realName.trim().toLowerCase()
  if (normalizedRealName.length >= 2 && password.toLowerCase().includes(normalizedRealName)) {
    return '密码不能包含姓名'
  }

  return ''
}

export function UserManagement() {
  const [users, setUsers] = useState<AdminUserRecord[]>([])
  const [roles, setRoles] = useState<RoleRecord[]>([])
  const [orgTree, setOrgTree] = useState<OrgNode[]>([])
  const [dingtalkCandidates, setDingtalkCandidates] = useState<DingTalkCandidateRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingUser, setEditingUser] = useState<AdminUserRecord | null>(null)
  const [form, setForm] = useState<UserFormState>(emptyForm)

  const flatOrgs = useMemo(() => flattenOrgs(orgTree), [orgTree])
  const selectedOrg = flatOrgs.find((item) => String(item.id) === form.primary_org_id)
  const isCreating = !editingUser
  const passwordValidationMessage = form.password
    ? validateStrongPassword(form.password, form.username, form.real_name)
    : ''
  const showPasswordValidation = !!form.password

  const fetchAll = async () => {
    setLoading(true)
    const [userResult, roleResult, orgResult] = await Promise.all([
      authAdminApi.listUsers(),
      roleApi.list(),
      orgApi.getTree(),
    ])

    const nextError = userResult.error || roleResult.error || orgResult.error
    if (nextError || !userResult.data || !roleResult.data || !orgResult.data) {
      setError(nextError || '用户权限数据加载失败')
      setLoading(false)
      return
    }

    setUsers(userResult.data)
    setRoles(roleResult.data.items)
    setOrgTree(orgResult.data.items)
    const candidateResult = await authAdminApi.listDingtalkCandidates()
    if (candidateResult.data) {
      setDingtalkCandidates(candidateResult.data)
    }
    setError('')
    setLoading(false)
  }

  useEffect(() => {
    fetchAll()
  }, [])

  const openCreate = () => {
    const defaultRole = roles.find((role) => role.code === 'contract_operator')
    setEditingUser(null)
    setForm({
      ...emptyForm,
      role_ids: defaultRole ? [defaultRole.id] : [],
    })
    setError('')
    setShowForm(true)
  }

  const openEdit = (user: AdminUserRecord) => {
    setEditingUser(user)
    setForm({
      username: user.username,
      password: '',
      real_name: user.real_name || '',
      employee_no: user.employee_no || '',
      position_name: user.position_name || '',
      dingtalk_user_id: user.dingtalk_user_id || '',
      dingtalk_union_id: user.dingtalk_union_id || '',
      dingtalk_open_id: user.dingtalk_open_id || '',
      primary_org_id: user.primary_org_id ? String(user.primary_org_id) : '',
      role_ids: normalizeRoleIds(user, roles),
    })
    setError('')
    setShowForm(true)
  }

  const toggleRole = (roleId: number) => {
    setForm((prev) => ({
      ...prev,
      role_ids: prev.role_ids.includes(roleId)
        ? prev.role_ids.filter((item) => item !== roleId)
        : [...prev.role_ids, roleId],
    }))
  }

  const applyDingtalkCandidate = (candidate: DingTalkCandidateRecord) => {
    const matchedOrg = flatOrgs.find((item) => {
      if (!candidate.department_name) return false
      return isSelectablePrimaryOrg(item) && item.name === candidate.department_name
    })

    setForm((prev) => ({
      ...prev,
      username: prev.username || buildSuggestedUsername(candidate),
      real_name: candidate.nick || prev.real_name,
      employee_no: candidate.employee_no || prev.employee_no,
      position_name: candidate.position_name || prev.position_name,
      dingtalk_user_id: candidate.dingtalk_user_id || '',
      dingtalk_union_id: candidate.dingtalk_union_id || '',
      dingtalk_open_id: candidate.dingtalk_open_id || '',
      primary_org_id: matchedOrg ? String(matchedOrg.id) : prev.primary_org_id,
    }))
  }

  const ignoreDingtalkCandidate = async (candidate: DingTalkCandidateRecord) => {
    const label = candidate.nick || candidate.email || candidate.dingtalk_union_id || '该钉钉身份'
    if (!window.confirm(`确定忽略「${label}」吗？`)) return
    const result = await authAdminApi.ignoreDingtalkCandidate(candidate.id)
    if (result.error) {
      setError(result.error)
      return
    }
    fetchAll()
  }

  const handleSave = async () => {
    if (!form.username.trim()) {
      setError('用户名不能为空')
      return
    }
    if (!form.real_name.trim()) {
      setError('姓名不能为空')
      return
    }
    if (!form.position_name.trim()) {
      setError('岗位不能为空')
      return
    }
    if (!selectedOrg) {
      setError('主组织不能为空')
      return
    }
    if (!isSelectablePrimaryOrg(selectedOrg)) {
      setError('主组织必须选择到具体部门，不能选择组织架构或父级组织')
      return
    }
    if (!editingUser && !form.password) {
      setError('密码不能为空')
      return
    }
    if (!editingUser) {
      const passwordError = validateStrongPassword(form.password, form.username, form.real_name)
      if (passwordError) {
        setError(passwordError)
        return
      }
    }
    if (editingUser && form.password) {
      const passwordError = validateStrongPassword(form.password, form.username, form.real_name)
      if (passwordError) {
        setError(passwordError)
        return
      }
    }
    if (form.primary_org_id === '') {
      setError('请选择具体部门')
      return
    }
    if (form.role_ids.length === 0) {
      setError('至少选择一个角色')
      return
    }

    setSaving(true)
    const payload = {
      username: form.username.trim(),
      password: form.password || undefined,
      real_name: form.real_name.trim(),
      employee_no: form.employee_no.trim() || undefined,
      position_name: form.position_name.trim(),
      dingtalk_user_id: editingUser ? form.dingtalk_user_id.trim() : form.dingtalk_user_id.trim() || undefined,
      dingtalk_union_id: editingUser ? form.dingtalk_union_id.trim() : form.dingtalk_union_id.trim() || undefined,
      dingtalk_open_id: editingUser ? form.dingtalk_open_id.trim() : form.dingtalk_open_id.trim() || undefined,
      primary_org_id: selectedOrg ? selectedOrg.id : null,
      department: selectedOrg?.name || '',
      role_ids: form.role_ids,
      role: deriveLegacyRole(form.role_ids, roles),
    }

    const result = editingUser
      ? await authAdminApi.updateUser(editingUser.id, payload)
      : await authAdminApi.createUser(payload)

    setSaving(false)
    if (result.error) {
      setError(result.error)
      return
    }

    setShowForm(false)
    setEditingUser(null)
    setForm(emptyForm)
    fetchAll()
  }

  const handleToggleActive = async (user: AdminUserRecord) => {
    const result = await authAdminApi.updateUser(user.id, { is_active: !user.is_active })
    if (result.error) {
      setError(result.error)
      return
    }
    fetchAll()
  }

  const handleDelete = async (user: AdminUserRecord) => {
    if (!window.confirm(`确定删除用户「${user.real_name || user.username}」吗？`)) return
    const result = await authAdminApi.deleteUser(user.id)
    if (result.error) {
      setError(result.error)
      return
    }
    fetchAll()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">用户权限管理</h1>
          <p className="text-sm text-muted-foreground">为用户分配所属部门、角色和对应的数据范围</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-1 h-4 w-4" />
          新增用户
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{editingUser ? '编辑用户' : '新增用户'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium">用户名 {requiredMark}</label>
                <Input
                  value={form.username}
                  onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
                  disabled={!!editingUser}
                  placeholder="登录用户名"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  {editingUser ? '新密码（留空不修改）' : <>密码 {requiredMark}</>}
                </label>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder={editingUser ? '留空表示不修改' : '至少8位，含大小写字母/数字/符号'}
                />
                <p
                  className={cn(
                    'mt-1 text-xs',
                    showPasswordValidation
                      ? passwordValidationMessage ? 'text-red-600' : 'text-green-600'
                      : 'text-muted-foreground',
                  )}
                >
                  {showPasswordValidation
                    ? passwordValidationMessage || '密码复杂度符合要求'
                    : '需至少8位，且包含大写字母、小写字母、数字和特殊字符'}
                </p>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">姓名 {requiredMark}</label>
                <Input
                  value={form.real_name}
                  onChange={(e) => setForm((prev) => ({ ...prev, real_name: e.target.value }))}
                  placeholder="真实姓名"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">员工编号</label>
                <Input
                  value={form.employee_no}
                  onChange={(e) => setForm((prev) => ({ ...prev, employee_no: e.target.value }))}
                  placeholder="可选"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">岗位 {requiredMark}</label>
                <Input
                  value={form.position_name}
                  onChange={(e) => setForm((prev) => ({ ...prev, position_name: e.target.value }))}
                  placeholder="例如：法务经理"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">主组织 {requiredMark}</label>
                <Select
                  value={form.primary_org_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, primary_org_id: e.target.value }))}
                >
                  <option value="">请选择具体部门</option>
                  {flatOrgs.map((org) => (
                    <option key={org.id} value={org.id} disabled={!isSelectablePrimaryOrg(org)}>
                      {'　'.repeat(org.depth)}
                      {org.name}
                      {!isSelectablePrimaryOrg(org) ? '（请选择下级）' : ''}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">钉钉 UserId</label>
                <Input
                  value={form.dingtalk_user_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, dingtalk_user_id: e.target.value }))}
                  placeholder="用于钉钉扫码登录绑定，可选"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">钉钉 UnionId</label>
                <Input
                  value={form.dingtalk_union_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, dingtalk_union_id: e.target.value }))}
                  placeholder="用于跨应用识别，可选"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">钉钉 OpenId</label>
                <Input
                  value={form.dingtalk_open_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, dingtalk_open_id: e.target.value }))}
                  placeholder="授权返回时可用于匹配，可选"
                />
              </div>
            </div>

            <div className="rounded-lg border p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <div className="font-medium">待绑定钉钉身份</div>
                  <div className="text-xs text-muted-foreground">
                    让员工先扫码一次，未绑定的身份会出现在这里；选择后保存当前用户即可完成绑定
                  </div>
                </div>
                <Button type="button" variant="outline" size="sm" onClick={fetchAll} title="刷新待绑定身份">
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
              </div>
              {dingtalkCandidates.length === 0 ? (
                <div className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
                  暂无待绑定身份。请让需要开通扫码登录的员工先在登录页扫码一次。
                </div>
              ) : (
                <div className="grid gap-2 md:grid-cols-2">
                  {dingtalkCandidates.map((candidate) => (
                    <div key={candidate.id} className="rounded-md border p-3">
                      <div className="flex items-start gap-3">
                        {candidate.avatar_url ? (
                          <img
                            src={candidate.avatar_url}
                            alt={candidate.nick || '钉钉用户'}
                            className="h-10 w-10 rounded-full object-cover"
                          />
                        ) : (
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                            <UserIcon className="h-4 w-4 text-muted-foreground" />
                          </div>
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">{candidate.nick || '未命名钉钉用户'}</div>
                          <div className="truncate text-xs text-muted-foreground">{candidate.email || '-'}</div>
                          <div className="mt-1 truncate text-xs text-muted-foreground">
                            工号：{candidate.employee_no || '-'}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            部门：{candidate.department_name || '-'}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            岗位：{candidate.position_name || '-'}
                          </div>
                          <div className="mt-1 truncate text-xs text-muted-foreground">
                            UnionId：{candidate.dingtalk_union_id || '-'}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            OpenId：{candidate.dingtalk_open_id || '-'}
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            扫码 {candidate.seen_count || 1} 次
                            {candidate.last_seen_at ? ` · ${candidate.last_seen_at.replace('T', ' ').split('.')[0]}` : ''}
                          </div>
                        </div>
                      </div>
                      <div className="mt-3 flex gap-2">
                        <Button type="button" size="sm" onClick={() => applyDingtalkCandidate(candidate)}>
                          <Link2 className="mr-1 h-3.5 w-3.5" />
                          一键填入
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => ignoreDingtalkCandidate(candidate)}>
                          忽略
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-lg border p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <div className="font-medium">角色分配 {requiredMark}</div>
                  <div className="text-xs text-muted-foreground">
                    角色决定功能权限，数据范围取决于角色配置和用户所属部门
                  </div>
                </div>
                {selectedOrg && isSelectablePrimaryOrg(selectedOrg) && (
                  <Badge variant="secondary">所属组织：{selectedOrg.name}</Badge>
                )}
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {roles.map((role) => (
                  <label key={role.id} className="flex cursor-pointer items-start gap-2 rounded-md border p-3">
                    <input
                      type="checkbox"
                      checked={form.role_ids.includes(role.id)}
                      onChange={() => toggleRole(role.id)}
                      className="mt-1"
                    />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{role.name}</span>
                        {role.is_system && <Badge variant="secondary">系统角色</Badge>}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{role.code}</div>
                      <div className="mt-2 text-xs text-muted-foreground">{role.description || '暂无说明'}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {error && <div className="text-sm text-destructive">{error}</div>}
            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? '保存中...' : '保存'}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>
                取消
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="px-4 py-3 text-left font-medium">用户</th>
                <th className="px-4 py-3 text-left font-medium">所属部门</th>
                <th className="px-4 py-3 text-left font-medium">角色</th>
                <th className="px-4 py-3 text-left font-medium">数据范围</th>
                <th className="px-4 py-3 text-left font-medium">钉钉</th>
                <th className="px-4 py-3 text-left font-medium">状态</th>
                <th className="px-4 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                    暂无用户
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-3">
                      <div className="font-medium">{user.real_name || user.username}</div>
                      <div className="text-xs text-muted-foreground">
                        {user.username}
                        {user.employee_no ? ` · ${user.employee_no}` : ''}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div>{user.primary_org_name || user.department || '-'}</div>
                      <div className="text-xs text-muted-foreground">{user.position_name || '-'}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {user.roles.length > 0 ? user.roles.map((role) => (
                          <Badge key={`${user.id}-${role.id}`} variant="secondary">
                            {role.name}
                          </Badge>
                        )) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{summarizeScopes(user)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={user.dingtalk_bound ? 'success' : 'secondary'}>
                        {user.dingtalk_bound ? '已绑定' : '未绑定'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={user.is_active ? 'success' : 'destructive'}>
                        {user.is_active ? '启用' : '禁用'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => openEdit(user)} title="编辑">
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleToggleActive(user)}
                          title={user.is_active ? '禁用' : '启用'}
                        >
                          {user.is_active ? <X className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}
                        </Button>
                        {user.username !== 'admin' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => handleDelete(user)}
                            title="删除"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {!showForm && error && <div className="text-sm text-destructive">{error}</div>}

      {!showForm && users.length > 0 && (
        <Card>
          <CardContent className="grid gap-4 pt-6 md:grid-cols-3">
            <div className="rounded-lg border p-4">
              <div className="text-xs text-muted-foreground">启用用户</div>
              <div className="mt-2 flex items-center gap-2 text-xl font-semibold">
                <Check className="h-4 w-4 text-green-600" />
                {users.filter((item) => item.is_active).length}
              </div>
            </div>
            <div className="rounded-lg border p-4">
              <div className="text-xs text-muted-foreground">管理员用户</div>
              <div className="mt-2 flex items-center gap-2 text-xl font-semibold">
                <ShieldCheck className="h-4 w-4 text-primary" />
                {users.filter((item) => item.role === 'admin').length}
              </div>
            </div>
            <div className="rounded-lg border p-4">
              <div className="text-xs text-muted-foreground">普通用户</div>
              <div className="mt-2 flex items-center gap-2 text-xl font-semibold">
                <UserIcon className="h-4 w-4 text-muted-foreground" />
                {users.filter((item) => item.role !== 'admin').length}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
