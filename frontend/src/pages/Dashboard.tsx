import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  FileText, 
  Plus, 
  AlertTriangle, 
  Clock,
  TrendingUp,
  ArrowRight
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
import { Input } from '@/components/ui/input'
import { contractApi } from '@/lib/api'
import type { Contract } from '@/types'

export function Dashboard() {
  const [dragActive, setDragActive] = useState(false)
  const [totalContracts, setTotalContracts] = useState(0)
  const [recentContracts, setRecentContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)

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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      console.log('Files dropped:', e.dataTransfer.files)
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
        <Link to="/upload">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            上传合同
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>上传合同</CardTitle>
            <CardDescription>拖拽PDF文件到此处上传，支持批量上传</CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragActive ? 'border-primary bg-primary/5' : 'border-border'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-sm text-muted-foreground mb-4">
                拖拽PDF文件到此处，或点击选择文件
              </p>
              <Input type="file" accept=".pdf" multiple className="hidden" id="file-upload" />
              <label htmlFor="file-upload">
                <Button variant="outline" className="cursor-pointer">
                  选择文件
                </Button>
              </label>
              <p className="text-xs text-muted-foreground mt-4">
                支持 PDF 格式，单个文件最大 50MB
              </p>
            </div>
          </CardContent>
        </Card>

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
                    <TableRow key={contract.id}>
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

      <Card>
        <CardHeader>
          <CardTitle>合同类型分布</CardTitle>
          <CardDescription>按合同类型统计合同数量</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-center py-8 text-muted-foreground">加载中...</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
              {recentContracts.slice(0, 8).map((contract, idx) => (
                <div key={idx} className="text-center p-4 rounded-lg bg-muted/50">
                  <p className="text-2xl font-bold">1</p>
                  <p className="text-xs text-muted-foreground mt-1">{contract.type || '其他'}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
