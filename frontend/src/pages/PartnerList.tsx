import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, RefreshCw, Building2, Phone, User, FileText } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { partnerApi, PartnerRecord } from '@/lib/api'

export function PartnerList() {
  const navigate = useNavigate()
  const [partners, setPartners] = useState<PartnerRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', contact_name: '', contact_phone: '', address: '' })
  const [saving, setSaving] = useState(false)

  const pageSize = 20

  const fetchPartners = async () => {
    setLoading(true)
    try {
      const res = await partnerApi.list({ page, page_size: pageSize, search: search || undefined })
      if (res.data) {
        setPartners(res.data.partners)
        setTotal(res.data.total)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchPartners() }, [page])

  const handleSearch = () => { setPage(1); fetchPartners() }

  const handleSync = async () => {
    setSyncing(true)
    try {
      const res = await partnerApi.syncFromContracts()
      if (res.data) {
        alert(res.data.message)
        fetchPartners()
      }
    } finally {
      setSyncing(false)
    }
  }

  const handleCreate = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      const res = await partnerApi.create(form)
      if (res.data?.id) {
        setShowCreate(false)
        setForm({ name: '', contact_name: '', contact_phone: '', address: '' })
        navigate(`/partners/${res.data.id}`)
      }
    } catch (e: any) {
      alert(e.message || '创建失败')
    } finally {
      setSaving(false)
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">合作伙伴</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSync} disabled={syncing}>
            <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
            从合同同步
          </Button>
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-2" />
            新建
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>筛选</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索名称、联系人、电话..."
                className="pl-9"
                value={search}
                onChange={e => setSearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <Button onClick={handleSearch}><Search className="h-4 w-4 mr-2" />搜索</Button>
            <Button variant="outline" onClick={() => { setSearch(''); setPage(1); fetchPartners() }}>重置</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>合作伙伴名称</TableHead>
                <TableHead className="w-[120px]">联系人</TableHead>
                <TableHead className="w-[140px]">联系电话</TableHead>
                <TableHead>地址</TableHead>
                <TableHead className="w-[80px] text-center">合同数</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={5} className="text-center py-8 text-muted-foreground">加载中...</TableCell></TableRow>
              ) : partners.length === 0 ? (
                <TableRow><TableCell colSpan={5} className="text-center py-8 text-muted-foreground">暂无合作伙伴，可点击"从合同同步"自动提取</TableCell></TableRow>
              ) : partners.map(p => (
                <TableRow key={p.id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/partners/${p.id}`)}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="font-medium">{p.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {p.contact_name ? (
                      <div className="flex items-center gap-1">
                        <User className="h-3 w-3 text-muted-foreground" />
                        {p.contact_name}
                      </div>
                    ) : '-'}
                  </TableCell>
                  <TableCell>
                    {p.contact_phone ? (
                      <div className="flex items-center gap-1">
                        <Phone className="h-3 w-3 text-muted-foreground" />
                        {p.contact_phone}
                      </div>
                    ) : '-'}
                  </TableCell>
                  <TableCell className="text-muted-foreground truncate max-w-[200px]">{p.address || '-'}</TableCell>
                  <TableCell className="text-center">
                    <Badge variant={p.contract_count ? 'default' : 'secondary'}>
                      <FileText className="h-3 w-3 mr-1" />
                      {p.contract_count ?? 0}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between p-4 border-t text-sm text-muted-foreground">
            <span>共 {total} 个合作伙伴</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</Button>
              <span className="px-2 py-1">第 {page}/{totalPages || 1} 页</span>
              <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader><DialogTitle>新建合作伙伴</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1">
              <Label>名称 *</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="合作伙伴名称" />
            </div>
            <div className="space-y-1">
              <Label>联系人</Label>
              <Input value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} placeholder="联系人姓名" />
            </div>
            <div className="space-y-1">
              <Label>联系电话</Label>
              <Input value={form.contact_phone} onChange={e => setForm(f => ({ ...f, contact_phone: e.target.value }))} placeholder="联系电话" />
            </div>
            <div className="space-y-1">
              <Label>地址</Label>
              <Input value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))} placeholder="地址" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
            <Button onClick={handleCreate} disabled={saving || !form.name.trim()}>
              {saving ? '创建中...' : '创建'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
