import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Search, 
  Download,
  FileText,
  Calendar,
  DollarSign,
  User,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown
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

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">付款管理</h1>
        <Button variant="outline">
          <Download className="h-4 w-4 mr-2" />
          导出
        </Button>
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
    </div>
  )
}
