import { useState, useEffect, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { 
  Search, 
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

const contractTypes: ContractType[] = ['采购合同', '销售合同', '人力合同', 'NDA保密协议', '租赁合同', '服务合同', '投资协议', '其他']
const departments: Department[] = ['科技中心', '财务中心', '法务合规中心', '风控中心', '普惠金融', '人力行政中心', '其他']
const statuses: ContractStatus[] = ['待审核', '已签署', '执行中', '已到期', '已终止']

export function ContractList() {
  const [contracts, setContracts] = useState<Contract[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [loading, setLoading] = useState(true)
  const [searchParams] = useSearchParams()
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [departmentFilter, setDepartmentFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortField, setSortField] = useState<string>('updated_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const navigate = useNavigate()

  const loadContracts = async () => {
    setLoading(true)
    const result = await contractApi.list({
      page,
      page_size: pageSize,
      search: searchQuery || undefined,
      contract_type: typeFilter !== 'all' ? typeFilter : undefined,
      department: departmentFilter !== 'all' ? departmentFilter : undefined,
      status: statusFilter !== 'all' ? statusFilter : undefined,
      sort_field: sortField,
      sort_order: sortOrder,
    })
    if (result.data) {
      setContracts(result.data.contracts as unknown as Contract[])
      setTotal(result.data.total)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadContracts()
  }, [page, pageSize, typeFilter, departmentFilter, statusFilter, sortField, sortOrder])

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

  // 如果列表中有"解析中..."的合同，每5秒自动刷新
  useEffect(() => {
    const hasParsing = contracts.some(c => c.title === '解析中...')
    if (!hasParsing) return
    const timer = setInterval(() => {
      loadContracts()
    }, 5000)
    return () => clearInterval(timer)
  }, [contracts])

  // 构建树形渲染列表：补充协议合同插入到主合同行后面
  const flatRows = useMemo(() => {
    const rows: Array<{ contract: any; isChild: boolean }> = []
    contracts.forEach(c => {
      const raw = c as any
      // 如果这条合同本身是某个主合同的补充协议，跳过
      if (raw.is_supplement_child) return

      rows.push({ contract: c, isChild: false })

      // 插入子合同行
      const children: any[] = raw.supplement_children || []
      children.forEach(child => {
        rows.push({ contract: child, isChild: true })
      })
    })
    return rows
  }, [contracts])

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
    } as const
    return <Badge variant={variants[status as keyof typeof variants] || 'default'}>{status}</Badge>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">合同管理</h1>
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
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'contract_number') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('contract_number')
                    setSortOrder('asc')
                  }
                }}>
                  合同编号 {sortField === 'contract_number' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'title') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('title')
                    setSortOrder('asc')
                  }
                }}>
                  合同名称 {sortField === 'title' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'contract_type') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('contract_type')
                    setSortOrder('asc')
                  }
                }}>
                  类型 {sortField === 'contract_type' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'department') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('department')
                    setSortOrder('asc')
                  }
                }}>
                  发起部门 {sortField === 'department' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
                <TableHead>签约方</TableHead>
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'amount') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('amount')
                    setSortOrder('asc')
                  }
                }}>
                  金额 {sortField === 'amount' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'signed_date') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('signed_date')
                    setSortOrder('asc')
                  }
                }}>
                  签订时间 {sortField === 'signed_date' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'start_date') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('start_date')
                    setSortOrder('asc')
                  }
                }}>
                  有效期 {sortField === 'start_date' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
                <TableHead className="cursor-pointer hover:bg-muted" onClick={() => {
                  if (sortField === 'status') {
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
                  } else {
                    setSortField('status')
                    setSortOrder('asc')
                  }
                }}>
                  状态 {sortField === 'status' && (sortOrder === 'asc' ? '↑' : '↓')}
                </TableHead>
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
                    flatRows.map(({ contract, isChild }, rowIndex) => {
                      // 判断这行是否是某个主合同的最后一个子合同（用于连接线截止）
                      const nextRow = flatRows[rowIndex + 1]
                      const isLastChild = isChild && (!nextRow || !nextRow.isChild)

                      return (
                      <TableRow 
                        key={contract.id}
                        className={`cursor-pointer transition-colors ${isChild ? 'bg-slate-50/60 hover:bg-slate-100/80 dark:bg-slate-900/30' : 'hover:bg-muted/50'}`}
                        onClick={() => navigate(`/contracts/${contract.id}`)}
                      >
                        {/* 合同编号列 */}
                        <TableCell className="font-medium whitespace-nowrap">
                          {contract.contractNumber}
                        </TableCell>
                        {/* 合同名称列：连接线 + 主/补标签 */}
                        <TableCell className="relative min-w-[260px] max-w-[320px]">
                          <div className="flex items-center gap-2">
                            {/* 主合同：向下延伸的竖线（连接到子合同） */}
                            {!isChild && (contract as any).supplement_children?.length > 0 && (
                              <div className="absolute left-[15px] top-[50%] w-[2px] h-[50%] bg-gray-300 z-10" />
                            )}
                            {/* 补充协议：L形连接线 */}
                            {isChild && (
                              <>
                                {/* 竖线：从上方延伸到行中间 */}
                                <div className="absolute left-[15px] top-0 w-[2px] h-[50%] bg-gray-300" />
                                {/* 如果不是最后一个子合同，竖线继续向下 */}
                                {!isLastChild && (
                                  <div className="absolute left-[15px] top-[50%] w-[2px] h-[50%] bg-gray-300" />
                                )}
                                {/* 横线：从竖线到文字 */}
                                <div className="absolute left-[15px] top-[50%] w-[14px] h-[2px] bg-gray-300" />
                                {/* 缩进占位 */}
                                <div className="w-7 flex-shrink-0" />
                              </>
                            )}
                            <span className="truncate overflow-hidden" title={contract.title !== '解析中...' && contract.title !== '解析失败' ? contract.title : undefined}>
                              {contract.title === '解析中...' ? (
                                <span className="inline-flex items-center gap-1.5 text-primary">
                                  <span className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                  正在解析中...
                                </span>
                              ) : contract.title === '解析失败' ? (
                                <span className="text-destructive">{contract.title}</span>
                              ) : (
                                contract.title
                              )}
                            </span>
                            {!isChild && (contract as any).supplement_children?.length > 0 && (
                              <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-600 border border-blue-200">主</span>
                            )}
                            {isChild && (
                              <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-50 text-orange-600 border border-orange-200">补</span>
                            )}
                          </div>
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
                          {contract.amount ? `${(contract.amount).toLocaleString()}` : '-'}
                        </TableCell>
                        <TableCell>
                          {formatDate(contract.signedDate)}
                        </TableCell>
                        <TableCell className="whitespace-nowrap">
                          {contract.startDate && contract.endDate 
                            ? <div className="text-xs"><div>{formatDate(contract.startDate)}</div><div>{formatDate(contract.endDate)}</div></div>
                            : '-'}
                        </TableCell>
                        <TableCell>{getStatusBadge(contract.status, contract.endDate)}</TableCell>
                      </TableRow>
                    )})
                  )}
                </>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          共 {total} 条记录，共 {Math.ceil(total / pageSize)} 页
        </p>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 whitespace-nowrap">
            <span className="text-sm text-muted-foreground">每页显示：</span>
            <Select value={String(pageSize)} onChange={(e) => {
              setPageSize(Number(e.target.value))
              setPage(1)
            }}>
              <option value="10">10条</option>
              <option value="20">20条</option>
              <option value="50">50条</option>
              <option value="100">100条</option>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
              上一页
            </Button>
            <span className="text-sm whitespace-nowrap">第 {page} / {Math.ceil(total / pageSize)} 页</span>
            <Button variant="outline" size="sm" disabled={contracts.length < pageSize} onClick={() => setPage(p => p + 1)}>
              下一页
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
