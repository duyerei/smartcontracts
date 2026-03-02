import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  Search, 
  Download, 
  Eye, 
  Trash2,
  AlertCircle
} from 'lucide-react'
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { 
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
} from '@/components/ui/select'
import { contractApi } from '@/lib/api'
import type { Contract, ContractType, Department, ContractStatus } from '@/types'

const contractTypes: ContractType[] = ['采购合同', '销售合同', '人力合同', 'NDA保密协议', '租赁合同', '服务合同', '投资协议', '其他']
const departments: Department[] = ['科技中心', '财务中心', '法务合规中心', '风控中心', '普惠金融', '人力行政中心', '其他']
const statuses: ContractStatus[] = ['待审核', '已签署', '执行中', '已到期', '已终止']

export function ContractList() {
  const [contracts, setContracts] = useState<Contract[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [departmentFilter, setDepartmentFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const loadContracts = async () => {
    setLoading(true)
    const result = await contractApi.list({
      page,
      page_size: 10,
      search: searchQuery || undefined,
      contract_type: typeFilter !== 'all' ? typeFilter : undefined,
      department: departmentFilter !== 'all' ? departmentFilter : undefined,
      status: statusFilter !== 'all' ? statusFilter : undefined,
    })
    if (result.data) {
      setContracts(result.data.contracts as Contract[])
      setTotal(result.data.total)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadContracts()
  }, [page, typeFilter, departmentFilter, statusFilter])

  useEffect(() => {
    const timer = setTimeout(() => {
      if (page !== 1) {
        setPage(1)
      } else {
        loadContracts()
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const getStatusBadge = (status?: string, endDate?: string) => {
    if (!status || !endDate) return null
    
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'warning' | 'success'> = {
      '合同履行中': 'success',
      '即将到期': 'destructive',
      '履行完成': 'secondary',
      '待审核': 'warning',
      '已签署': 'success',
      '执行中': 'default',
      '已到期': 'destructive',
      '已终止': 'secondary',
    }
    return <Badge variant={variants[status] || 'default'}>{status}</Badge>
  }

  const getRiskBadge = (risk?: 'low' | 'medium' | 'high') => {
    if (!risk) return null
    const variants = {
      low: 'success',
      medium: 'warning',
      high: 'destructive',
    }
    const labels = {
      low: '低风险',
      medium: '中风险',
      high: '高风险',
    }
    return (
      <Badge variant={variants[risk]} className="ml-2">
        <AlertCircle className="h-3 w-3 mr-1" />
        {labels[risk]}
      </Badge>
    )
  }

  const formatAmount = (amount: number | null, currency: string) => {
    if (amount === null) return '-'
    return new Intl.NumberFormat('zh-CN', { style: 'currency', currency }).format(amount)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">合同管理</h1>
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
                placeholder="搜索合同编号、名称、签约方..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="all">全部类型</option>
              {contractTypes.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </Select>
            <Select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)}>
              <option value="all">全部部门</option>
              {departments.map((dept) => (
                <option key={dept} value={dept}>{dept}</option>
              ))}
            </Select>
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="all">全部状态</option>
              {statuses.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>合同编号</TableHead>
                <TableHead>合同名称</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>发起部门</TableHead>
                <TableHead>签约方</TableHead>
                <TableHead>金额</TableHead>
                <TableHead>有效期</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-8">
                    加载中...
                  </TableCell>
                </TableRow>
              ) : (
                <>
                  {contracts.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center py-8">
                        暂无合同数据
                      </TableCell>
                    </TableRow>
                  ) : (
                    contracts.map((contract) => (
                      <TableRow key={contract.id}>
                        <TableCell className="font-medium">
                          <Link to={`/contracts/${contract.id}`} className="hover:underline text-primary">
                            {contract.contractNumber}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Link to={`/contracts/${contract.id}`} className="hover:underline text-primary">
                            {contract.title}
                          </Link>
                        </TableCell>
                        <TableCell>{contract.type}</TableCell>
                        <TableCell>{contract.department}</TableCell>
                        <TableCell>
                          {Array.isArray(contract.parties) && contract.parties.length >= 2 ? (
                            <div className="text-xs space-y-1">
                              <div><span className="text-muted-foreground">甲方：</span>{contract.parties[0]}</div>
                              <div><span className="text-muted-foreground">乙方：</span>{contract.parties[1]}</div>
                              {contract.parties.length >= 3 && contract.parties[2] && contract.parties[2] !== 'null' && contract.parties[2] !== '待填写' && contract.parties[2] !== '未识别' && (
                                <div><span className="text-muted-foreground">丙方：</span>{contract.parties[2]}</div>
                              )}
                            </div>
                          ) : (
                            <span>{Array.isArray(contract.parties) ? contract.parties[0] : String(contract.parties || '-')}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {contract.amount ? `${(contract.amount).toLocaleString()} ${contract.currency || 'CNY'}` : '-'}
                        </TableCell>
                        <TableCell>
                          {contract.startDate && contract.endDate 
                            ? `${contract.startDate} ~ ${contract.endDate}` 
                            : '-'}
                        </TableCell>
                        <TableCell>{getStatusBadge(contract.status, contract.endDate)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Link to={`/contracts/${contract.id}`}>
                              <Button variant="ghost" size="icon">
                                <Eye className="h-4 w-4" />
                              </Button>
                            </Link>
                            <Button variant="ghost" size="icon" onClick={async () => {
                              try {
                                const token = localStorage.getItem('token')
                                const response = await fetch(`/api/v1/contracts/${contract.id}/download`, {
                                  headers: { 'Authorization': `Bearer ${token}` }
                                })
                                if (response.ok) {
                                  const blob = await response.blob()
                                  const url = window.URL.createObjectURL(blob)
                                  const a = document.createElement('a')
                                  a.href = url
                                  a.download = `${contract.title || 'contract'}.pdf`
                                  document.body.appendChild(a)
                                  a.click()
                                  window.URL.revokeObjectURL(url)
                                  document.body.removeChild(a)
                                }
                              } catch (error) {
                                console.error('下载失败:', error)
                              }
                            }}>
                              <Download className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" onClick={async () => {
                              if (!confirm(`确定要删除合同 ${contract.contractNumber} 吗？`)) return
                              const result = await contractApi.delete(Number(contract.id))
                              if (result.data) {
                                loadContracts()
                              } else {
                                alert('删除失败: ' + result.error)
                              }
                            }}>
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          共 {total} 条记录
        </p>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
            上一页
          </Button>
          <span className="text-sm">第 {page} 页</span>
          <Button variant="outline" size="sm" disabled={contracts.length < 10} onClick={() => setPage(p => p + 1)}>
            下一页
          </Button>
        </div>
      </div>
    </div>
  )
}
