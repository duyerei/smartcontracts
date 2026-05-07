import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft,
  FileText,
  Calendar,
  DollarSign,
  User,
  Building,
  Folder,
  Hash,
  File,
  Download,
  Clock,
  Edit,
  Eye,
  Search,
  Plus,
  Trash2,
  Save,
  X
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { paymentManagementApi, PaymentRecord, contractApi } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'

interface PaymentDetail extends PaymentRecord {
  contract?: {
    id: number
    title: string
    contract_number: string
    amount?: number
    status?: string
    department?: string
    contract_type?: string
    start_date?: string
    end_date?: string
    parties_a?: string
    parties_b?: string
  }
  updated_at?: string
}

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return dateStr
  }
}

// 获取 YYYY-MM-DD 格式用于 input[type=date]
const toDateInputValue = (dateStr?: string) => {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return ''
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return ''
  }
}

export function PaymentManagementDetail() {
  const { id } = useParams<{ id: string }>()
  const { hasPermission } = useAuth()
  const navigate = useNavigate()
  const [payment, setPayment] = useState<PaymentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [showContractSelector, setShowContractSelector] = useState(false)
  const [contractSearchQuery, setContractSearchQuery] = useState('')
  const [contractSearchResults, setContractSearchResults] = useState<any[]>([])
  const [contractSearchLoading, setContractSearchLoading] = useState(false)

  // 编辑状态
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  // 删除确认
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const canEditPayment = hasPermission('payment.edit')
  const canDeletePayment = hasPermission('payment.delete')
  const canDownloadPayment = hasPermission('payment.download')

  const startEditing = () => {
    if (!payment) return
    setEditForm({
      payment_theme: payment.payment_theme || '',
      payment_date: toDateInputValue(payment.payment_date),
      amount: payment.amount != null ? String(payment.amount) : '',
      operator: payment.operator || '',
      cost_center: payment.cost_center || '',
      project_name: payment.project_name || '',
      contract_number: payment.contract_number || '',
      application_number: payment.application_number || '',
      payment_reason: payment.payment_reason || '',
    })
    setIsEditing(true)
  }

  const cancelEditing = () => {
    setIsEditing(false)
    setEditForm({})
  }

  const handleSave = async () => {
    if (!id) return
    setSaving(true)
    try {
      const updateData: Record<string, unknown> = { ...editForm }
      if (editForm.amount) updateData.amount = parseFloat(editForm.amount)
      else updateData.amount = null
      const result = await paymentManagementApi.update(Number(id), updateData)
      if (result.data || !result.error) {
        // 重新加载数据
        const refreshed = await paymentManagementApi.get(Number(id))
        if (refreshed.data) setPayment(refreshed.data as PaymentDetail)
        setIsEditing(false)
      } else if (result.error) {
        alert('保存失败: ' + result.error)
      }
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!id) return
    setDeleting(true)
    try {
      const result = await paymentManagementApi.delete(Number(id))
      if (result.data) {
        navigate('/payments')
      } else if (result.error) {
        alert('删除失败: ' + result.error)
      }
    } catch (error) {
      console.error('删除失败:', error)
      alert('删除失败')
    } finally {
      setDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  const handleOpenContractSelector = () => {
    setShowContractSelector(true)
    setContractSearchQuery('')
    setContractSearchResults([])
  }

  const handleSearchContract = async () => {
    if (!contractSearchQuery.trim()) return
    setContractSearchLoading(true)
    try {
      const result = await contractApi.list({ search: contractSearchQuery, page_size: 20 })
      if (result.data) {
        setContractSearchResults(result.data.contracts || [])
      }
    } catch (error) {
      console.error('搜索合同失败:', error)
    } finally {
      setContractSearchLoading(false)
    }
  }

  const handleLinkContract = async (contractId: number) => {
    if (!id) return
    try {
      const result = await paymentManagementApi.linkContract(Number(id), contractId)
      if (result.data?.contract) {
        const contractData = result.data.contract
        setPayment(prev => prev ? {
          ...prev,
          contract_id: contractId,
          contract: contractData
        } : null)
      }
      setShowContractSelector(false)
    } catch (error) {
      console.error('关联合同失败:', error)
    }
  }

  useEffect(() => {
    const fetchPayment = async () => {
      if (!id) return
      try {
        const result = await paymentManagementApi.get(Number(id))
        if (result.data) {
          setPayment(result.data as PaymentDetail)
        }
      } catch (error) {
        console.error('获取付款记录详情失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchPayment()
  }, [id])

  const formatAmount = (amount?: number) => {
    if (amount === undefined || amount === null) return '-'
    return new Intl.NumberFormat('zh-CN', { 
      style: 'decimal',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      </div>
    )
  }

  if (!payment) {
    return (
      <div className="container mx-auto py-6">
        <div className="text-center py-8">
          <p className="text-muted-foreground mb-4">付款记录不存在</p>
          <Button variant="outline" onClick={() => navigate('/payments')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回列表
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/payments')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回列表
          </Button>
          <h1 className="text-2xl font-bold">{payment.payment_theme}</h1>
        </div>
        {canDeletePayment && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            删除
          </Button>
        )}
      </div>

      {/* 删除确认对话框 */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground">
            确定要删除付款记录「{payment.payment_theme}」吗？此操作不可撤销。
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteConfirm(false)} disabled={deleting}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? '删除中...' : '确认删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Tabs defaultValue="info" className="space-y-6">
        <TabsList>
          <TabsTrigger value="info">基本信息</TabsTrigger>
          <TabsTrigger value="details">详细信息</TabsTrigger>
          {payment.payment_reason && <TabsTrigger value="reason">付款事由</TabsTrigger>}
          <TabsTrigger value="contract">关联合同</TabsTrigger>
          {payment.file_path && <TabsTrigger value="attachments">相关附件</TabsTrigger>}
        </TabsList>

        <TabsContent value="info" className="space-y-6 mt-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>基本信息</CardTitle>
              {canEditPayment && isEditing ? (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={cancelEditing} disabled={saving}>
                    <X className="h-4 w-4 mr-2" />
                    取消
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={saving}>
                    <Save className="h-4 w-4 mr-2" />
                    {saving ? '保存中...' : '保存'}
                  </Button>
                </div>
              ) : canEditPayment ? (
                <Button variant="outline" size="sm" onClick={startEditing}>
                  <Edit className="h-4 w-4 mr-2" />
                  编辑
                </Button>
              ) : null}
            </CardHeader>
            <CardContent>
              {isEditing ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">付款主题</p>
                    <Input
                      value={editForm.payment_theme || ''}
                      onChange={e => setEditForm(f => ({ ...f, payment_theme: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">申请日期</p>
                    <Input
                      type="date"
                      value={editForm.payment_date || ''}
                      onChange={e => setEditForm(f => ({ ...f, payment_date: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">付款金额</p>
                    <Input
                      type="number"
                      step="0.01"
                      value={editForm.amount || ''}
                      onChange={e => setEditForm(f => ({ ...f, amount: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">经办人</p>
                    <Input
                      value={editForm.operator || ''}
                      onChange={e => setEditForm(f => ({ ...f, operator: e.target.value }))}
                    />
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">申请日期</p>
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{formatDate(payment.payment_date)}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">付款金额</p>
                    <div className="flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{formatAmount(payment.amount)}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">经办人</p>
                    <div className="flex items-center gap-2">
                      <User className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{payment.operator || '-'}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">创建时间</p>
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{payment.created_at || '-'}</span>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="details" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>详细信息</CardTitle>
            </CardHeader>
            <CardContent>
              {isEditing ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">归属成本中心</p>
                    <Input
                      value={editForm.cost_center || ''}
                      onChange={e => setEditForm(f => ({ ...f, cost_center: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">项目名称</p>
                    <Input
                      value={editForm.project_name || ''}
                      onChange={e => setEditForm(f => ({ ...f, project_name: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">合同编号</p>
                    <Input
                      value={editForm.contract_number || ''}
                      onChange={e => setEditForm(f => ({ ...f, contract_number: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">申请单号</p>
                    <Input
                      value={editForm.application_number || ''}
                      onChange={e => setEditForm(f => ({ ...f, application_number: e.target.value }))}
                    />
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">归属成本中心</p>
                    <div className="flex items-center gap-2">
                      <Building className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{payment.cost_center || '-'}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">项目名称</p>
                    <div className="flex items-center gap-2">
                      <Folder className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{payment.project_name || '-'}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">合同编号</p>
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{payment.contract_number || '-'}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">申请单号</p>
                    <div className="flex items-center gap-2">
                      <Hash className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{payment.application_number || '-'}</span>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {payment.payment_reason && (
          <TabsContent value="reason" className="space-y-6 mt-6">
            <Card>
              <CardHeader>
                <CardTitle>付款事由</CardTitle>
              </CardHeader>
              <CardContent>
                {isEditing ? (
                  <textarea
                    className="w-full min-h-[120px] p-3 border rounded-md text-sm"
                    value={editForm.payment_reason || ''}
                    onChange={e => setEditForm(f => ({ ...f, payment_reason: e.target.value }))}
                  />
                ) : (
                  <p className="whitespace-pre-wrap">{payment.payment_reason}</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="contract" className="space-y-6 mt-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>关联合同</CardTitle>
                {canEditPayment && (
                  <Button variant="outline" size="sm" onClick={handleOpenContractSelector}>
                    <Plus className="h-4 w-4 mr-2" />
                    {payment.contract ? '更换关联' : '关联合同'}
                  </Button>
                )}
              </CardHeader>
              <CardContent>
                {payment.contract ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Link
                        to={`/contracts/${payment.contract.id}`}
                        className="flex items-center gap-2 text-primary hover:underline text-lg font-semibold"
                      >
                        <FileText className="h-5 w-5" />
                        {payment.contract.title}
                      </Link>
                      <Link to={`/contracts/${payment.contract.id}`}>
                        <Button variant="outline" size="sm">
                          <Eye className="h-4 w-4 mr-2" />
                          查看详情
                        </Button>
                      </Link>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 pt-2 border-t">
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">合同编号</p>
                        <p className="text-sm font-medium">{payment.contract.contract_number || '-'}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">合同金额</p>
                        <p className="text-sm font-medium">
                          {payment.contract.amount != null ? formatAmount(payment.contract.amount) : '-'}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">合同状态</p>
                        <p className="text-sm font-medium">{payment.contract.status || '-'}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">合同类型</p>
                        <p className="text-sm font-medium">{payment.contract.contract_type || '-'}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">发起部门</p>
                        <p className="text-sm font-medium">{payment.contract.department || '-'}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">合同期限</p>
                        <p className="text-sm font-medium">
                          {payment.contract.start_date || '-'} ~ {payment.contract.end_date || '-'}
                        </p>
                      </div>
                      {payment.contract.parties_a && (
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">甲方</p>
                          <p className="text-sm font-medium">{payment.contract.parties_a}</p>
                        </div>
                      )}
                      {payment.contract.parties_b && (
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">乙方</p>
                          <p className="text-sm font-medium">{payment.contract.parties_b}</p>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-muted-foreground text-center py-4">
                    <p>暂无关联合同</p>
                    {canEditPayment && (
                      <Button variant="link" onClick={handleOpenContractSelector}>
                        点击关联合同
                      </Button>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

        <Dialog open={showContractSelector} onOpenChange={setShowContractSelector}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>选择关联合同</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="搜索合同名称或编号..."
                  value={contractSearchQuery}
                  onChange={(e) => setContractSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchContract()}
                />
                <Button onClick={handleSearchContract} disabled={contractSearchLoading}>
                  <Search className="h-4 w-4 mr-2" />
                  搜索
                </Button>
              </div>
              <div className="max-h-96 overflow-y-auto border rounded-lg">
                {contractSearchLoading ? (
                  <div className="text-center py-8 text-muted-foreground">加载中...</div>
                ) : contractSearchResults.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    {contractSearchQuery ? '未找到匹配的合同' : '请输入关键词搜索合同'}
                  </div>
                ) : (
                  <div className="divide-y">
                    {contractSearchResults.map((contract) => (
                      <div
                        key={contract.id}
                        className="p-3 hover:bg-muted/50 cursor-pointer"
                        onClick={() => handleLinkContract(contract.id)}
                      >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{contract.title}</p>
                      <p className="text-sm text-muted-foreground">
                        合同编号: {contract.contract_number}
                      </p>
                    </div>
                    {canEditPayment && (
                      <Button variant="ghost" size="sm">
                        关联
                      </Button>
                    )}
                  </div>
                </div>
              ))}
                  </div>
                )}
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {payment.file_path && (
          <TabsContent value="attachments" className="space-y-6 mt-6">
            <Card>
              <CardHeader>
                <CardTitle>相关附件</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <File className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">{payment.description || '付款附件'}</p>
                      <p className="text-sm text-muted-foreground">
                        {formatFileSize(payment.file_size)}
                      </p>
                    </div>
                  </div>
                  {canDownloadPayment && (
                    <Button variant="outline" size="sm" onClick={async () => {
                      try {
                        const token = localStorage.getItem('token')
                        const response = await fetch(`/api/v1/payments/${payment.id}/download`, {
                          headers: { 'Authorization': `Bearer ${token}` }
                        })
                        if (!response.ok) throw new Error('下载失败')
                        const blob = await response.blob()
                        const url = window.URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        const ext = payment.file_path?.split('.').pop() || 'pdf'
                        a.download = `${payment.description || '付款附件'}.${ext}`
                        document.body.appendChild(a)
                        a.click()
                        window.URL.revokeObjectURL(url)
                        document.body.removeChild(a)
                      } catch (e) {
                        alert('下载失败')
                      }
                    }}>
                      <Download className="h-4 w-4 mr-2" />
                      下载
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
