import { useEffect, useMemo, useState } from 'react'
import { Plus, Pencil, Trash2, Network } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { orgApi, type OrgNode } from '@/lib/api'

interface OrgFormState {
  name: string
  code: string
  parent_id: string
  org_type: string
  status: string
  sort: string
}

const emptyForm: OrgFormState = {
  name: '',
  code: '',
  parent_id: '',
  org_type: 'department',
  status: 'active',
  sort: '0',
}

function orgTypeLabel(type: string) {
  switch (type) {
    case 'business_unit':
      return '事业部'
    case 'center':
      return '中心'
    case 'office':
      return '办公室'
    case 'group':
      return '小组'
    case 'company':
      return '公司'
    case 'department':
      return '部门'
    case 'team':
      return '团队'
    default:
      return type
  }
}

function flattenOrgs(items: OrgNode[], depth = 0): Array<OrgNode & { depth: number }> {
  return items.flatMap((item) => [
    { ...item, depth },
    ...flattenOrgs(item.children || [], depth + 1),
  ])
}

export function OrgManagement() {
  const [orgTree, setOrgTree] = useState<OrgNode[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingOrg, setEditingOrg] = useState<OrgNode | null>(null)
  const [form, setForm] = useState<OrgFormState>(emptyForm)

  const flatOrgs = useMemo(() => flattenOrgs(orgTree), [orgTree])

  const fetchOrgs = async () => {
    setLoading(true)
    const result = await orgApi.getTree()
    if (result.error || !result.data) {
      setError(result.error || '组织架构加载失败')
      setLoading(false)
      return
    }
    setOrgTree(result.data.items)
    setError('')
    setLoading(false)
  }

  useEffect(() => {
    fetchOrgs()
  }, [])

  const openCreate = (parentId?: number) => {
    setEditingOrg(null)
    setForm({
      ...emptyForm,
      parent_id: parentId ? String(parentId) : '',
    })
    setError('')
    setShowForm(true)
  }

  const openEdit = (org: OrgNode) => {
    setEditingOrg(org)
    setForm({
      name: org.name,
      code: org.code,
      parent_id: org.parent_id ? String(org.parent_id) : '',
      org_type: org.org_type,
      status: org.status,
      sort: String(org.sort ?? 0),
    })
    setError('')
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError('组织名称不能为空')
      return
    }

    setSaving(true)
    const payload = {
      name: form.name.trim(),
      code: form.code.trim() || undefined,
      parent_id: form.parent_id ? Number(form.parent_id) : null,
      org_type: form.org_type,
      status: form.status,
      sort: Number(form.sort || '0'),
    }

    const result = editingOrg
      ? await orgApi.update(editingOrg.id, payload)
      : await orgApi.create(payload)

    setSaving(false)
    if (result.error) {
      setError(result.error)
      return
    }

    setShowForm(false)
    setEditingOrg(null)
    setForm(emptyForm)
    fetchOrgs()
  }

  const handleDelete = async (org: OrgNode) => {
    if (!window.confirm(`确定删除组织「${org.name}」吗？`)) return
    const result = await orgApi.delete(org.id)
    if (result.error) {
      setError(result.error)
      return
    }
    fetchOrgs()
  }

  const availableParents = flatOrgs.filter((item) => {
    if (!editingOrg) return true
    if (item.id === editingOrg.id) return false
    return !item.path.startsWith(`${editingOrg.path}/`)
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">组织架构</h1>
          <p className="text-sm text-muted-foreground">维护组织树、上下级关系与数据归属基础信息</p>
        </div>
        <Button onClick={() => openCreate()}>
          <Plus className="mr-1 h-4 w-4" />
          新增组织
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{editingOrg ? '编辑组织' : '新增组织'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium">组织名称</label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="例如：科技中心"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">组织编码</label>
                <Input
                  value={form.code}
                  onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
                  placeholder="留空则自动生成"
                  disabled={!!editingOrg}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">上级组织</label>
                <Select
                  value={form.parent_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, parent_id: e.target.value }))}
                >
                  <option value="">顶级组织</option>
                  {availableParents.map((item) => (
                    <option key={item.id} value={item.id}>
                      {'　'.repeat(item.depth)}
                      {item.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">组织类型</label>
                <Select
                  value={form.org_type}
                  onChange={(e) => setForm((prev) => ({ ...prev, org_type: e.target.value }))}
                >
                  <option value="company">公司</option>
                  <option value="business_unit">事业部</option>
                  <option value="center">中心</option>
                  <option value="department">部门</option>
                  <option value="office">办公室</option>
                  <option value="team">团队</option>
                  <option value="group">小组</option>
                </Select>
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
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Network className="h-4 w-4" />
            组织树
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="px-4 py-3 text-left font-medium">名称</th>
                <th className="px-4 py-3 text-left font-medium">编码</th>
                <th className="px-4 py-3 text-left font-medium">类型</th>
                <th className="px-4 py-3 text-left font-medium">状态</th>
                <th className="px-4 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              ) : flatOrgs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                    暂无组织
                  </td>
                </tr>
              ) : (
                flatOrgs.map((org) => (
                  <tr key={org.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span>{'　'.repeat(org.depth)}{org.name}</span>
                        {org.code === 'ROOT' && <Badge variant="secondary">根组织</Badge>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{org.code}</td>
                    <td className="px-4 py-3">{orgTypeLabel(org.org_type)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={org.status === 'active' ? 'success' : 'secondary'}>
                        {org.status === 'active' ? '启用' : '停用'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => openCreate(org.id)} title="新增下级">
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => openEdit(org)} title="编辑">
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        {org.code !== 'ROOT' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => handleDelete(org)}
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
    </div>
  )
}
