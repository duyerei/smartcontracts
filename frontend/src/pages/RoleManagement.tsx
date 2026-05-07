import { useEffect, useMemo, useState } from 'react'
import { Plus, Pencil, Trash2, ShieldCheck, Save } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import {
  roleApi,
  orgApi,
  type OrgNode,
  type PermissionItem,
  type RoleDataScopeItem,
  type RoleRecord,
} from '@/lib/api'

interface RoleFormState {
  code: string
  name: string
  description: string
  status: string
}

const emptyForm: RoleFormState = {
  code: '',
  name: '',
  description: '',
  status: 'active',
}

const resourceLabels: Record<string, string> = {
  contract: '合同',
  payment: '付款',
  partner: '合作伙伴',
}

function flattenOrgs(items: OrgNode[], depth = 0): Array<OrgNode & { depth: number }> {
  return items.flatMap((item) => [
    { ...item, depth },
    ...flattenOrgs(item.children || [], depth + 1),
  ])
}

function scopeLabel(scopeType: string) {
  switch (scopeType) {
    case 'ALL':
      return '全部数据'
    case 'ORG_ONLY':
      return '本组织'
    case 'ORG_AND_CHILDREN':
      return '本组织及下级'
    case 'SELF':
      return '仅本人'
    default:
      return scopeType
  }
}

export function RoleManagement() {
  const [roles, setRoles] = useState<RoleRecord[]>([])
  const [permissions, setPermissions] = useState<PermissionItem[]>([])
  const [orgTree, setOrgTree] = useState<OrgNode[]>([])
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingBasic, setSavingBasic] = useState(false)
  const [savingPermissions, setSavingPermissions] = useState(false)
  const [savingScopes, setSavingScopes] = useState(false)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingRole, setEditingRole] = useState<RoleRecord | null>(null)
  const [form, setForm] = useState<RoleFormState>(emptyForm)
  const [permissionDraft, setPermissionDraft] = useState<string[]>([])
  const [scopeDraft, setScopeDraft] = useState<Record<string, RoleDataScopeItem>>({})

  const flatOrgs = useMemo(() => flattenOrgs(orgTree), [orgTree])
  const selectedRole = roles.find((item) => item.id === selectedRoleId) || null

  const groupedPermissions = useMemo(() => {
    return permissions.reduce<Record<string, PermissionItem[]>>((acc, item) => {
      const key = item.module || 'other'
      acc[key] = acc[key] || []
      acc[key].push(item)
      return acc
    }, {})
  }, [permissions])

  const applyRoleDrafts = (role: RoleRecord | null) => {
    if (!role) {
      setPermissionDraft([])
      setScopeDraft({})
      return
    }

    setPermissionDraft(role.permissions.map((item) => item.code))

    const nextScopes: Record<string, RoleDataScopeItem> = {}
    for (const resource of Object.keys(resourceLabels)) {
      const current = role.data_scopes.find((item) => item.resource_type === resource)
      nextScopes[resource] = current
        ? {
            resource_type: resource,
            scope_type: current.scope_type,
            org_ids: [...current.org_ids],
          }
        : {
            resource_type: resource,
            scope_type: 'ORG_ONLY',
            org_ids: [],
          }
    }
    setScopeDraft(nextScopes)
  }

  const fetchAll = async (preferredSelectedId?: number) => {
    setLoading(true)
    const [roleResult, permissionResult, orgResult] = await Promise.all([
      roleApi.list(),
      roleApi.listPermissions(),
      orgApi.getTree(),
    ])

    const nextError = roleResult.error || permissionResult.error || orgResult.error
    if (nextError || !roleResult.data || !permissionResult.data || !orgResult.data) {
      setError(nextError || '角色权限数据加载失败')
      setLoading(false)
      return
    }

    const nextRoles = roleResult.data.items
    setRoles(nextRoles)
    setPermissions(permissionResult.data.items)
    setOrgTree(orgResult.data.items)
    setError('')

    const candidateSelectedId = preferredSelectedId ?? selectedRoleId
    const nextSelectedId = nextRoles.some((item) => item.id === candidateSelectedId)
      ? candidateSelectedId
      : (nextRoles[0]?.id ?? null)
    setSelectedRoleId(nextSelectedId)
    applyRoleDrafts(nextRoles.find((item) => item.id === nextSelectedId) || null)
    setLoading(false)
  }

  useEffect(() => {
    fetchAll()
  }, [])

  const openCreate = () => {
    setEditingRole(null)
    setForm(emptyForm)
    setError('')
    setShowForm(true)
  }

  const openEdit = (role: RoleRecord) => {
    setEditingRole(role)
    setForm({
      code: role.code,
      name: role.name,
      description: role.description || '',
      status: role.status,
    })
    setError('')
    setShowForm(true)
  }

  const handleSaveBasic = async () => {
    if (!form.code.trim() && !editingRole) {
      setError('角色编码不能为空')
      return
    }
    if (!form.name.trim()) {
      setError('角色名称不能为空')
      return
    }

    setSavingBasic(true)
    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      status: form.status,
    }

    const result = editingRole
      ? await roleApi.update(editingRole.id, {
          name: payload.name,
          description: payload.description,
          status: payload.status,
        })
      : await roleApi.create(payload)

    setSavingBasic(false)
    if (result.error || !result.data) {
      setError(result.error || '角色保存失败')
      return
    }

    setShowForm(false)
    setEditingRole(null)
    setSelectedRoleId(result.data.id)
    await fetchAll(result.data.id)
  }

  const handleDelete = async (role: RoleRecord) => {
    if (!window.confirm(`确定删除角色「${role.name}」吗？`)) return
    const result = await roleApi.delete(role.id)
    if (result.error) {
      setError(result.error)
      return
    }
    await fetchAll()
  }

  const togglePermission = (code: string) => {
    setPermissionDraft((prev) => (
      prev.includes(code) ? prev.filter((item) => item !== code) : [...prev, code]
    ))
  }

  const updateScopeType = (resourceType: string, scopeType: string) => {
    setScopeDraft((prev) => ({
      ...prev,
      [resourceType]: {
        resource_type: resourceType,
        scope_type: scopeType,
        org_ids: prev[resourceType]?.org_ids || [],
      },
    }))
  }

  const toggleScopeOrg = (resourceType: string, orgId: number) => {
    setScopeDraft((prev) => {
      const current = prev[resourceType] || {
        resource_type: resourceType,
        scope_type: 'ORG_ONLY',
        org_ids: [],
      }
      const nextOrgIds = current.org_ids.includes(orgId)
        ? current.org_ids.filter((item) => item !== orgId)
        : [...current.org_ids, orgId]

      return {
        ...prev,
        [resourceType]: {
          ...current,
          org_ids: nextOrgIds,
        },
      }
    })
  }

  const handleSavePermissions = async () => {
    if (!selectedRole) return
    setSavingPermissions(true)
    const result = await roleApi.updatePermissions(selectedRole.id, permissionDraft)
    setSavingPermissions(false)
    if (result.error) {
      setError(result.error)
      return
    }
    await fetchAll()
  }

  const handleSaveScopes = async () => {
    if (!selectedRole) return
    setSavingScopes(true)
    const scopes = Object.values(scopeDraft).map((item) => ({
      resource_type: item.resource_type,
      scope_type: item.scope_type,
      org_ids: item.org_ids,
    }))
    const result = await roleApi.updateDataScopes(selectedRole.id, scopes)
    setSavingScopes(false)
    if (result.error) {
      setError(result.error)
      return
    }
    await fetchAll()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">角色权限</h1>
          <p className="text-sm text-muted-foreground">配置角色的功能权限与数据权限范围</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-1 h-4 w-4" />
          新增角色
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{editingRole ? '编辑角色' : '新增角色'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium">角色编码</label>
                <Input
                  value={form.code}
                  onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
                  disabled={!!editingRole}
                  placeholder="例如：contract_operator"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">角色名称</label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="例如：合同经办人"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-sm font-medium">角色说明</label>
                <Input
                  value={form.description}
                  onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="说明该角色适用场景"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">状态</label>
                <Select
                  value={form.status}
                  onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}
                >
                  <option value="active">启用</option>
                  <option value="inactive">停用</option>
                </Select>
              </div>
            </div>
            {error && <div className="text-sm text-destructive">{error}</div>}
            <div className="flex gap-2">
              <Button onClick={handleSaveBasic} disabled={savingBasic}>
                {savingBasic ? '保存中...' : '保存角色'}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>
                取消
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 xl:grid-cols-[360px,1fr]">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">角色列表</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">加载中...</div>
            ) : roles.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">暂无角色</div>
            ) : (
              roles.map((role) => (
                <div
                  key={role.id}
                  onClick={() => {
                    setSelectedRoleId(role.id)
                    applyRoleDrafts(role)
                  }}
                  className={`w-full rounded-lg border p-4 text-left transition-colors ${
                    selectedRoleId === role.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/30'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{role.name}</span>
                        {role.is_system && <Badge variant="secondary">系统角色</Badge>}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{role.code}</div>
                      <div className="mt-2 text-xs text-muted-foreground">
                        {role.description || '暂无说明'}
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); openEdit(role) }}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      {!role.is_system && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(role)
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {selectedRole ? (
          <div className="space-y-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <ShieldCheck className="h-4 w-4" />
                  {selectedRole.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg border p-4">
                  <div className="text-xs text-muted-foreground">角色编码</div>
                  <div className="mt-2 font-medium">{selectedRole.code}</div>
                </div>
                <div className="rounded-lg border p-4">
                  <div className="text-xs text-muted-foreground">功能权限数</div>
                  <div className="mt-2 font-medium">{selectedRole.permissions.length}</div>
                </div>
                <div className="rounded-lg border p-4">
                  <div className="text-xs text-muted-foreground">状态</div>
                  <div className="mt-2">
                    <Badge variant={selectedRole.status === 'active' ? 'success' : 'secondary'}>
                      {selectedRole.status === 'active' ? '启用' : '停用'}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-lg border p-4 md:col-span-3">
                  <div className="text-xs text-muted-foreground">角色说明</div>
                  <div className="mt-2 text-sm">{selectedRole.description || '暂无说明'}</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base">功能权限</CardTitle>
                <Button size="sm" onClick={handleSavePermissions} disabled={savingPermissions}>
                  <Save className="mr-1 h-3.5 w-3.5" />
                  {savingPermissions ? '保存中...' : '保存权限'}
                </Button>
              </CardHeader>
              <CardContent className="space-y-5">
                {Object.entries(groupedPermissions).map(([module, items]) => (
                  <div key={module} className="rounded-lg border p-4">
                    <div className="mb-3 font-medium">{module}</div>
                    <div className="grid gap-3 md:grid-cols-2">
                      {items.map((item) => (
                        <label key={item.code} className="flex cursor-pointer items-start gap-2 rounded-md border p-3">
                          <input
                            type="checkbox"
                            checked={permissionDraft.includes(item.code)}
                            onChange={() => togglePermission(item.code)}
                            className="mt-1"
                          />
                          <div>
                            <div className="text-sm font-medium">{item.name}</div>
                            <div className="text-xs text-muted-foreground">{item.code}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base">数据权限</CardTitle>
                <Button size="sm" onClick={handleSaveScopes} disabled={savingScopes}>
                  <Save className="mr-1 h-3.5 w-3.5" />
                  {savingScopes ? '保存中...' : '保存范围'}
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {Object.keys(resourceLabels).map((resourceType) => {
                  const currentScope = scopeDraft[resourceType] || {
                    resource_type: resourceType,
                    scope_type: 'ORG_ONLY',
                    org_ids: [],
                  }
                  const orgSelectionEnabled = currentScope.scope_type === 'ORG_ONLY' || currentScope.scope_type === 'ORG_AND_CHILDREN'

                  return (
                    <div key={resourceType} className="rounded-lg border p-4">
                      <div className="mb-3 flex items-center justify-between gap-4">
                        <div>
                          <div className="font-medium">{resourceLabels[resourceType]}</div>
                          <div className="text-xs text-muted-foreground">
                            当前范围：{scopeLabel(currentScope.scope_type)}
                          </div>
                        </div>
                        <Select
                          className="max-w-[220px]"
                          value={currentScope.scope_type}
                          onChange={(e) => updateScopeType(resourceType, e.target.value)}
                        >
                          <option value="ALL">全部数据</option>
                          <option value="ORG_ONLY">本组织</option>
                          <option value="ORG_AND_CHILDREN">本组织及下级</option>
                          <option value="SELF">仅本人</option>
                        </Select>
                      </div>
                      <div className={`grid gap-2 md:grid-cols-2 ${orgSelectionEnabled ? '' : 'opacity-50'}`}>
                        {flatOrgs.map((org) => (
                          <label key={`${resourceType}-${org.id}`} className="flex items-center gap-2 rounded border px-3 py-2 text-sm">
                            <input
                              type="checkbox"
                              disabled={!orgSelectionEnabled}
                              checked={currentScope.org_ids.includes(org.id)}
                              onChange={() => toggleScopeOrg(resourceType, org.id)}
                            />
                            <span>{'　'.repeat(org.depth)}{org.name}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              请选择左侧角色后继续配置权限
            </CardContent>
          </Card>
        )}
      </div>

      {error && <div className="text-sm text-destructive">{error}</div>}
    </div>
  )
}
