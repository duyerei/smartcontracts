import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { renderAsync } from 'docx-preview'
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
  Plus
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { paymentManagementApi, PaymentRecord, contractApi } from '@/lib/api'

interface ContractAttachment {
  id: number
  file_name: string
  file_path: string
  file_size: number
}

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

export function PaymentManagementDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [payment, setPayment] = useState<PaymentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedAttachment, setSelectedAttachment] = useState<{id: number; file_name: string} | null>(null)
  const [attachmentPreviewUrl, setAttachmentPreviewUrl] = useState<string>('')
  const [attachmentPreviewType, setAttachmentPreviewType] = useState<'pdf' | 'image' | 'word' | 'unknown'>('unknown')
  const [isLoadingAttachment, setIsLoadingAttachment] = useState(false)
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const [wordArrayBuffer, setWordArrayBuffer] = useState<ArrayBuffer | null>(null)
  const wordDocxContainerRef = useRef<HTMLDivElement>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [showContractSelector, setShowContractSelector] = useState(false)
  const [contractSearchQuery, setContractSearchQuery] = useState('')
  const [contractSearchResults, setContractSearchResults] = useState<any[]>([])
  const [contractSearchLoading, setContractSearchLoading] = useState(false)

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
        setPayment(prev => prev ? {
          ...prev,
          contract_id: contractId,
          contract: result.data.contract
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

  useEffect(() => {
    if (wordArrayBuffer && wordDocxContainerRef.current) {
      wordDocxContainerRef.current.innerHTML = ''
      renderAsync(wordArrayBuffer, wordDocxContainerRef.current).catch(console.error)
    }
  }, [wordArrayBuffer])

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

  const handleAttachmentPreview = async (attachment: ContractAttachment) => {
    if (!payment?.contract_id) return
    
    setSelectedAttachment(attachment)
    setShowPreview(true)
    setIsLoadingAttachment(true)
    setAttachmentError(null)
    setWordArrayBuffer(null)
    
    if (attachmentPreviewUrl) {
      window.URL.revokeObjectURL(attachmentPreviewUrl)
      setAttachmentPreviewUrl('')
    }
    
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/contracts/${payment.contract_id}/attachments/${attachment.id}/download`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (!response.ok) {
        throw new Error(`获取附件失败 (HTTP ${response.status})`)
      }
      
      const blob = await response.blob()
      
      if (blob.type === 'text/html' || blob.type === 'application/json') {
        throw new Error('服务器返回错误响应')
      }
      
      const ext = attachment.file_name.toLowerCase().split('.').pop() || ''
      
      if (ext === 'docx') {
        setAttachmentPreviewType('word')
        const reader = new FileReader()
        reader.onload = (e) => {
          const arrayBuffer = e.target?.result as ArrayBuffer
          setWordArrayBuffer(arrayBuffer)
          setIsLoadingAttachment(false)
        }
        reader.onerror = () => {
          setAttachmentError('读取Word文件失败')
          setIsLoadingAttachment(false)
        }
        reader.readAsArrayBuffer(blob)
      } else if (ext === 'doc') {
        // .doc 文件：通过后端转 PDF 后预览
        try {
          const pdfResponse = await fetch(`/api/v1/contracts/${payment.contract_id}/attachments/${attachment.id}/preview-pdf`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (!pdfResponse.ok) {
            const errData = await pdfResponse.json().catch(() => ({}))
            throw new Error(errData.detail || '.doc 转 PDF 失败')
          }
          const pdfBlob = await pdfResponse.blob()
          const url = window.URL.createObjectURL(pdfBlob)
          setAttachmentPreviewUrl(url)
          setAttachmentPreviewType('pdf')
          setIsLoadingAttachment(false)
        } catch (docErr) {
          setAttachmentPreviewType('unknown')
          setAttachmentError(`.doc 转 PDF 预览失败: ${(docErr as Error).message}，请下载后查看`)
          setIsLoadingAttachment(false)
        }
      } else if (ext === 'pdf') {
        const url = window.URL.createObjectURL(blob)
        setAttachmentPreviewUrl(url)
        setAttachmentPreviewType('pdf')
        setIsLoadingAttachment(false)
      } else if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext)) {
        const url = window.URL.createObjectURL(blob)
        setAttachmentPreviewUrl(url)
        setAttachmentPreviewType('image')
        setIsLoadingAttachment(false)
      } else {
        setAttachmentPreviewType('unknown')
        setAttachmentError('不支持的文件格式，请下载后查看')
        setIsLoadingAttachment(false)
      }
    } catch (error) {
      console.error('预览附件失败:', error)
      setAttachmentError(`预览附件失败: ${(error as Error).message}`)
      setAttachmentPreviewType('unknown')
      setIsLoadingAttachment(false)
    }
  }

  useEffect(() => {
    return () => {
      if (attachmentPreviewUrl) {
        window.URL.revokeObjectURL(attachmentPreviewUrl)
      }
    }
  }, [attachmentPreviewUrl])

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
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" size="sm" onClick={() => navigate('/payments')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          返回列表
        </Button>
        <h1 className="text-2xl font-bold">{payment.payment_theme}</h1>
      </div>

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
              <Button variant="outline" size="sm">
                <Edit className="h-4 w-4 mr-2" />
                编辑
              </Button>
            </CardHeader>
            <CardContent>
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
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="details" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>详细信息</CardTitle>
            </CardHeader>
            <CardContent>
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
                <p className="whitespace-pre-wrap">{payment.payment_reason}</p>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="contract" className="space-y-6 mt-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>关联合同</CardTitle>
                <Button variant="outline" size="sm" onClick={handleOpenContractSelector}>
                  <Plus className="h-4 w-4 mr-2" />
                  {payment.contract ? '更换关联' : '关联合同'}
                </Button>
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
                      <Button variant="outline" size="sm" asChild>
                        <Link to={`/contracts/${payment.contract.id}`}>
                          <Eye className="h-4 w-4 mr-2" />
                          查看详情
                        </Link>
                      </Button>
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
                    <Button variant="link" onClick={handleOpenContractSelector}>
                      点击关联合同
                    </Button>
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
                          <Button variant="ghost" size="sm">
                            关联
                          </Button>
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
                      // 从 file_path 提取后缀名
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
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
