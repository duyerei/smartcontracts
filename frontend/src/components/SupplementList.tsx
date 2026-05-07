import { useState, useEffect, useCallback } from 'react'
import { Link2, FileText, Trash2, ExternalLink, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

interface LinkedContract {
  id: number
  contract_number: string | null
  title: string | null
  amount: number | null
  signed_date: string | null
  status: string | null
}

interface Supplement {
  id: number
  contract_id: number
  linked_contract_id: number | null
  title: string
  signed_date: string | null
  amount: number | null
  file_path: string | null
  file_size: number | null
  created_at: string
  linked_contract: LinkedContract | null
}

interface ContractSearchResult {
  id: number
  contract_number: string | null
  title: string | null
  amount: number | null
  signed_date: string | null
  status: string | null
  parties: string | null
}

interface SupplementListProps {
  contractId: number
}

export function SupplementList({ contractId }: SupplementListProps) {
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const [supplements, setSupplements] = useState<Supplement[]>([])
  const [loading, setLoading] = useState(false)
  const [showLinkDialog, setShowLinkDialog] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ContractSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [linking, setLinking] = useState(false)
  const canCreateSupplement = hasPermission('supplement.create')
  const canDeleteSupplement = hasPermission('supplement.delete')

  useEffect(() => {
    loadSupplements()
  }, [contractId])

  const loadSupplements = async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/supplements/${contractId}/list`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.ok) {
        const data = await response.json()
        setSupplements(data.supplements || [])
      }
    } catch (error) {
      console.error('加载补充协议失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const searchContracts = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults([])
      return
    }
    setSearching(true)
    try {
      const token = localStorage.getItem('token')
      const params = new URLSearchParams({ search: query, page_size: '20' })
      const response = await fetch(`/api/v1/contracts?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.ok) {
        const data = await response.json()
        // Exclude current contract and already-linked ones
        const linkedIds = new Set(supplements.map(s => s.linked_contract_id).filter(Boolean))
        const filtered = (data.contracts || []).filter(
          (c: ContractSearchResult) => c.id !== contractId && !linkedIds.has(c.id)
        )
        setSearchResults(filtered)
      }
    } catch (error) {
      console.error('搜索合同失败:', error)
    } finally {
      setSearching(false)
    }
  }, [contractId, supplements])

  useEffect(() => {
    const timer = setTimeout(() => searchContracts(searchQuery), 400)
    return () => clearTimeout(timer)
  }, [searchQuery, searchContracts])

  const handleLink = async (linkedContractId: number) => {
    setLinking(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/supplements/${contractId}/link`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ linked_contract_id: linkedContractId })
      })
      if (response.ok) {
        setShowLinkDialog(false)
        setSearchQuery('')
        setSearchResults([])
        loadSupplements()
      } else {
        const err = await response.json()
        alert(err.detail || '关联失败')
      }
    } catch (error) {
      console.error('关联失败:', error)
      alert('关联失败')
    } finally {
      setLinking(false)
    }
  }

  const handleDelete = async (supplementId: number) => {
    if (!confirm('确定要解除此补充协议关联吗？')) return
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/supplements/${supplementId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.ok) {
        loadSupplements()
      } else {
        alert('删除失败')
      }
    } catch (error) {
      alert('删除失败')
    }
  }

  const formatAmount = (amount: number | null) => {
    if (!amount) return '-'
    return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(amount)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    return dateStr.split('T')[0]
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>补充协议</CardTitle>
        {canCreateSupplement && (
          <Button variant="outline" size="sm" onClick={() => setShowLinkDialog(true)}>
            <Link2 className="h-4 w-4 mr-2" />
            关联补充协议
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-muted-foreground text-center py-4">加载中...</p>
        ) : supplements.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">暂无补充协议</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">补充协议</th>
                  <th className="text-left px-4 py-3 font-medium">合同编号</th>
                  <th className="text-left px-4 py-3 font-medium">签约时间</th>
                  <th className="text-left px-4 py-3 font-medium">金额</th>
                  <th className="text-right px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {supplements.map((supplement, index) => {
                  const lc = supplement.linked_contract
                  return (
                    <tr
                      key={supplement.id}
                      className={`border-t hover:bg-muted/50 transition-colors ${
                        index % 2 === 0 ? 'bg-background' : 'bg-muted/20'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          {lc ? (
                            <button
                              onClick={() => navigate(`/contracts/${lc.id}`)}
                              className="font-medium text-primary hover:underline text-left"
                            >
                              {lc.title || supplement.title}
                            </button>
                          ) : (
                            <span className="font-medium">{supplement.title}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-sm">
                        {lc?.contract_number || '-'}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(lc?.signed_date || supplement.signed_date)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatAmount(lc?.amount ?? supplement.amount)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          {lc && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => navigate(`/contracts/${lc.id}`)}
                              title="查看合同详情"
                            >
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          )}
                          {canDeleteSupplement && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDelete(supplement.id)}
                              title="解除关联"
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      {/* 关联补充协议对话框 */}
      <Dialog open={showLinkDialog} onOpenChange={(open) => {
        setShowLinkDialog(open)
        if (!open) { setSearchQuery(''); setSearchResults([]) }
      }}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>关联补充协议</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="搜索合同名称、编号或合作方..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
              />
            </div>

            <div className="min-h-[200px] max-h-[360px] overflow-y-auto border rounded-lg">
              {searching ? (
                <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
                  搜索中...
                </div>
              ) : !searchQuery.trim() ? (
                <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
                  输入关键词搜索合同
                </div>
              ) : searchResults.length === 0 ? (
                <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
                  未找到匹配的合同
                </div>
              ) : (
                <table className="w-full">
                  <thead className="bg-muted sticky top-0">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium text-sm">合同名称</th>
                      <th className="text-left px-4 py-2 font-medium text-sm">编号</th>
                      <th className="text-left px-4 py-2 font-medium text-sm">金额</th>
                      <th className="text-left px-4 py-2 font-medium text-sm">状态</th>
                      <th className="px-4 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchResults.map((c, i) => (
                      <tr
                        key={c.id}
                        className={`border-t hover:bg-muted/50 transition-colors ${
                          i % 2 === 0 ? 'bg-background' : 'bg-muted/20'
                        }`}
                      >
                        <td className="px-4 py-3 text-sm">
                          <div className="font-medium line-clamp-2">{c.title || '-'}</div>
                          {c.parties && (
                            <div className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{c.parties}</div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
                          {c.contract_number || '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
                          {c.amount ? new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(c.amount) : '-'}
                        </td>
                        <td className="px-4 py-3">
                          {c.status && (
                            <Badge variant="outline" className="text-xs whitespace-nowrap">{c.status}</Badge>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            size="sm"
                            disabled={linking}
                            onClick={() => handleLink(c.id)}
                          >
                            关联
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLinkDialog(false)}>
              取消
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
