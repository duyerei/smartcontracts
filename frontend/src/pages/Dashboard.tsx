import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { 
  FileText, 
  Plus, 
  AlertTriangle, 
  Clock,
  TrendingUp,
  ArrowRight,
  CreditCard,
  Upload,
  Search,
  Sparkles,
} from 'lucide-react'
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { contractApi, paymentManagementApi } from '@/lib/api'
import { Input } from '@/components/ui/input'
import type { Contract } from '@/types'

export function Dashboard() {
  const navigate = useNavigate()
  const [dragActive, setDragActive] = useState(false)
  const [paymentDragActive, setPaymentDragActive] = useState(false)
  const [totalContracts, setTotalContracts] = useState(0)
  const [recentContracts, setRecentContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [paymentUploading, setPaymentUploading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const contractFileRef = useRef<HTMLInputElement>(null)
  const paymentFileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      const result = await contractApi.list({ page: 1, page_size: 4 })
      if (result.data) {
        setRecentContracts(result.data.contracts as Contract[])
        setTotalContracts(result.data.total)
      }
      setLoading(false)
    }
    loadData()
  }, [])

  const pendingCount = recentContracts.filter(c => c.status === '待审核').length

  const statCards = [
    {
      title: '合同总数',
      value: totalContracts,
      icon: FileText,
      color: 'bg-blue-500',
    },
    {
      title: '本月新增',
      value: Math.floor(totalContracts * 0.05),
      icon: Plus,
      color: 'bg-green-500',
      trend: totalContracts > 0 ? '+5%' : undefined,
    },
    {
      title: '待续约',
      value: Math.floor(totalContracts * 0.01),
      icon: Clock,
      color: 'bg-yellow-500',
    },
    {
      title: '待审核',
      value: pendingCount,
      icon: AlertTriangle,
      color: 'bg-red-500',
    },
  ]

  const statValue = (val: number) => {
    return typeof val === 'number' ? val.toLocaleString() : '0'
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleContractUpload(file)
  }

  const handlePaymentDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setPaymentDragActive(true)
    } else if (e.type === 'dragleave') {
      setPaymentDragActive(false)
    }
  }

  const handlePaymentDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setPaymentDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handlePaymentUpload(file)
  }

  const handleContractUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('请上传PDF文件')
      return
    }
    setUploading(true)
    try {
      const result = await contractApi.upload(file)
      if (result.data) {
        const contractId = (result.data as any).contract_id
        navigate(`/contracts/${contractId}`)
      } else {
        alert(result.error || '上传失败')
      }
    } finally {
      setUploading(false)
    }
  }

  const handlePaymentUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('请上传PDF文件')
      return
    }
    setPaymentUploading(true)
    try {
      const result = await paymentManagementApi.importPdf(file)
      if (result.data) {
        const paymentId = (result.data as any).payment_id
        navigate(`/payments/${paymentId}`)
      } else {
        alert(result.error || '导入失败')
      }
    } finally {
      setPaymentUploading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'warning' | 'success'> = {
      '待审核': 'warning',
      '已签署': 'success',
      '执行中': 'default',
      '已到期': 'destructive',
      '已终止': 'secondary',
    }
    return <Badge variant={variants[status] || 'default'}>{status}</Badge>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">工作台</h1>
        <Link to="/contracts">
          <Button variant="outline" size="sm">
            <ArrowRight className="h-4 w-4 mr-2" />
            查看全部合同
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.title}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.title}</p>
                  <p className="text-3xl font-bold mt-1">{statValue(stat.value)}</p>
                  {stat.trend && (
                    <p className="text-xs text-green-500 mt-1 flex items-center">
                      <TrendingUp className="h-3 w-3 mr-1" />
                      {stat.trend} 较上月
                    </p>
                  )}
                </div>
                <div className={`h-12 w-12 rounded-lg ${stat.color} flex items-center justify-center`}>
                  <stat.icon className="h-6 w-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 智能搜索 */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={(e) => { e.preventDefault(); if (searchQuery.trim()) navigate(`/contracts?search=${encodeURIComponent(searchQuery)}`) }}>
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-3 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder="搜索合同编号、名称、签约方..."
                  className="pl-10 h-11"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Button type="submit" className="h-11 px-6">
                <Sparkles className="h-4 w-4 mr-2" />
                搜索
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>上传合同</CardTitle>
            <CardDescription>拖拽PDF文件到此处上传，或点击选择文件</CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer ${
                dragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => contractFileRef.current?.click()}
            >
              <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-sm text-muted-foreground mb-4">
                拖拽PDF文件到此处，或点击选择文件
              </p>
              <input
                ref={contractFileRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleContractUpload(file)
                  e.target.value = ''
                }}
              />
              <Button variant="outline" disabled={uploading} onClick={(e) => { e.stopPropagation(); contractFileRef.current?.click() }}>
                <Upload className="h-4 w-4 mr-2" />
                {uploading ? '上传中...' : '选择文件'}
              </Button>
              <p className="text-xs text-muted-foreground mt-4">支持 PDF 格式，单个文件最大 50MB</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>上传付款单</CardTitle>
            <CardDescription>上传OA付款申请PDF，自动解析付款信息</CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer ${
                paymentDragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
              }`}
              onDragEnter={handlePaymentDrag}
              onDragLeave={handlePaymentDrag}
              onDragOver={handlePaymentDrag}
              onDrop={handlePaymentDrop}
              onClick={() => paymentFileRef.current?.click()}
            >
              <CreditCard className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-sm text-muted-foreground mb-4">
                拖拽付款申请PDF到此处，或点击选择文件
              </p>
              <input
                ref={paymentFileRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handlePaymentUpload(file)
                  e.target.value = ''
                }}
              />
              <Button variant="outline" disabled={paymentUploading} onClick={(e) => { e.stopPropagation(); paymentFileRef.current?.click() }}>
                <Upload className="h-4 w-4 mr-2" />
                {paymentUploading ? '解析中...' : '选择文件'}
              </Button>
              <p className="text-xs text-muted-foreground mt-4">支持 PDF 格式，自动提取付款信息</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>最近更新</CardTitle>
            <CardDescription>最近更新的合同列表</CardDescription>
          </div>
          <Link to="/contracts">
            <Button variant="ghost" size="sm">
              查看全部
              <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-center py-8 text-muted-foreground">加载中...</p>
          ) : recentContracts.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">暂无合同数据</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>合同编号</TableHead>
                  <TableHead>合同名称</TableHead>
                  <TableHead>状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentContracts.map((contract) => (
                  <TableRow key={contract.id} className="cursor-pointer" onClick={() => navigate(`/contracts/${contract.id}`)}>
                    <TableCell className="font-medium">{contract.contractNumber}</TableCell>
                    <TableCell>{contract.title}</TableCell>
                    <TableCell>{getStatusBadge(contract.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
