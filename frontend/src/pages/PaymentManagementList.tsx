import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Search, 
  Download,
  Upload,
  FileText,
  Calendar,
  DollarSign,
  User,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  X,
  CheckCircle,
  AlertCircle,
  Loader2
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { paymentManagementApi, PaymentRecord } from '@/lib/api'

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

export function PaymentManagementList() {
  const navigate = useNavigate()
  const [payments, setPayments] = useState<PaymentRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortField, setSortField] = useState<string>('payment_date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  // PDF导入状态
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ success: boolean; message: string; detail?: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchPayments = async () => {
    setLoading(true)
    try {
      const result = await paymentManagementApi.list({ 
        page, 
        page_size: pageSize,
        search: searchQuery || undefined
      })
      if (result.data) {
        let data = result.data.payments || []
        
        // Sort on client side
        data = data.sort((a: PaymentRecord, b: PaymentRecord) => {
          let aVal: any, bVal: any
          
          switch (sortField) {
            case 'payment_date':
              aVal = a.payment_date || ''
              bVal = b.payment_date || ''
              break
            case 'amount':
              aVal = a.amount || 0
              bVal = b.amount || 0
              break
            case 'operator':
              aVal = a.operator || ''
              bVal = b.operator || ''
              break
            case 'payment_theme':
            default:
              aVal = a.payment_theme || ''
              bVal = b.payment_theme || ''
          }
          
          if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1
          if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1
          return 0
        })
        
        setPayments(data)
        setTotal(result.data.total || 0)
      }
    } catch (error) {
      console.error('获取付款记录失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPayments()
  }, [page, pageSize])

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault()
    setPage(1)
    fetchPayments()
  }

  const formatAmount = (amount?: number) => {
    if (amount === undefined || amount === null) return '-'
    return new Intl.NumberFormat('zh-CN', { 
      style: 'decimal',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
    fetchPayments()
  }

  const getSortIcon = (field: string) => {
    if (sortField !== field) return <ArrowUpDown className="h-4 w-4 ml-1 opacity-50" />
    return sortOrder === 'asc' 
      ? <ArrowUpDown className="h-4 w-4 ml-1 rotate-180" />
      : <ArrowUpDown className="h-4 w-4 ml-1" />
  }

  const handleImportPdf = async () => {
    if (!importFile) return
    setImporting(true)
    setImportResult(null)
    try {
      const result = await paymentManagementApi.importPdf(importFile)
      if (result.error) {
        setImportResult({ success: false, message: result.error })
      } else {
        const autoLinked = result.data?.auto_linked
        setImportResult({
          success: true,
          message: '导入成功',
          detail: autoLinked ? `已自动关联合同（${result.data?.parsed_data?.contract_number}）` : '未找到匹配合同，可手动关联'
        })
        fetchPayments()
      }
    } catch (e: any) {
      setImportResult({ success: false, message: e.message || '导入失败' })
    } finally {
      setImporting(false)
    }
  }

  const handleCloseImport = () => {
    setShowImportDialog(false)
    setImportFile(null)
    setImportResult(null)
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">付款管理</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowImportDialog(true)}>
            <Upload className="h-4 w-4 mr-2" />
            导入付款PDF
          </Button>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            导出
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>筛选条件</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索付款主题、经办人、合同编号..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={() => handleSearch()}>
                <Search className="h-4 w-4 mr-2" />
                搜索
              </Button>
              <Button variant="outline" onClick={() => { setSearchQuery(''); setPage(1); fetchPayments() }}>
                重置
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead 
                  className="w-[400px] cursor-pointer hover:bg-muted/50"
                  onClick={() => handleSort('payment_theme')}
                >
                  <div className="flex items-center">
                    付款主题
                    {getSortIcon('payment_theme')}
                  </div>
                </TableHead>
                <TableHead 
                  className="w-[120px] cursor-pointer hover:bg-muted/50"
                  onClick={() => handleSort('payment_date')}
                >
                  <div className="flex items-center">
                    申请日期
                    {getSortIcon('payment_date')}
                  </div>
                </TableHead>
                <TableHead 
                  className="w-[150px] cursor-pointer hover:bg-muted/50"
                  onClick={() => handleSort('amount')}
                >
                  <div className="flex items-center">
                    付款金额
                    {getSortIcon('amount')}
                  </div>
                </TableHead>
                <TableHead 
                  className="w-[100px] cursor-pointer hover:bg-muted/50"
                  onClick={() => handleSort('operator')}
                >
                  <div className="flex items-center">
                    经办人
                    {getSortIcon('operator')}
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                    加载中...
                  </TableCell>
                </TableRow>
              ) : payments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                    暂无付款记录
                  </TableCell>
                </TableRow>
              ) : (
                payments.map((payment) => (
                  <TableRow 
                    key={payment.id} 
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/payments/${payment.id}`)}
                  >
                    <TableCell className="font-medium">
                      {payment.payment_theme}
                    </TableCell>
                    <TableCell className="w-[120px]">
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        {formatDate(payment.payment_date)}
                      </div>
                    </TableCell>
                    <TableCell className="w-[150px]">
                      <div className="flex items-center gap-2">
                        <DollarSign className="h-4 w-4 text-muted-foreground" />
                        {formatAmount(payment.amount)}
                      </div>
                    </TableCell>
                    <TableCell className="w-[100px]">
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        {payment.operator || '-'}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between p-4 border-t">
            <div className="text-sm text-muted-foreground">
              共 {total} 条记录，第 {page}/{totalPages || 1} 页
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-1">
                {[...Array(Math.min(5, totalPages))].map((_, i) => {
                  const pageNum = i + 1
                  return (
                    <Button
                      key={pageNum}
                      variant={page === pageNum ? "default" : "ghost"}
                      size="sm"
                      onClick={() => setPage(pageNum)}
                    >
                      {pageNum}
                    </Button>
                  )
                })}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 导入付款PDF对话框 */}
      {showImportDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">导入OA付款申请PDF</h2>
              <button onClick={handleCloseImport} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-sm text-muted-foreground">
              将OA系统中的付款申请表单导出为PDF，上传后系统将自动解析付款信息并创建记录。
            </p>

            {!importResult ? (
              <>
                <div
                  className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    const f = e.dataTransfer.files[0]
                    if (f?.name.toLowerCase().endsWith('.pdf')) setImportFile(f)
                  }}
                >
                  <FileText className="h-10 w-10 mx-auto text-gray-400 mb-2" />
                  {importFile ? (
                    <p className="text-sm font-medium text-blue-600">{importFile.name}</p>
                  ) : (
                    <p className="text-sm text-gray-500">点击或拖拽PDF文件到此处</p>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  />
                </div>

                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={handleCloseImport}>取消</Button>
                  <Button onClick={handleImportPdf} disabled={!importFile || importing}>
                    {importing ? (
                      <><Loader2 className="h-4 w-4 mr-2 animate-spin" />解析中...</>
                    ) : (
                      <><Upload className="h-4 w-4 mr-2" />开始导入</>
                    )}
                  </Button>
                </div>
              </>
            ) : (
              <div className="space-y-4">
                <div className={`flex items-start gap-3 p-4 rounded-lg ${importResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
                  {importResult.success
                    ? <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                    : <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
                  }
                  <div>
                    <p className={`font-medium ${importResult.success ? 'text-green-800' : 'text-red-800'}`}>
                      {importResult.message}
                    </p>
                    {importResult.detail && (
                      <p className="text-sm mt-1 text-gray-600">{importResult.detail}</p>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={handleCloseImport}>关闭</Button>
                  {importResult.success && (
                    <Button onClick={() => { setImportFile(null); setImportResult(null) }}>
                      继续导入
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
