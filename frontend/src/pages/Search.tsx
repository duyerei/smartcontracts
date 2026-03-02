import { useState } from 'react'
import { Link } from 'react-router-dom'
import { 
  Search as SearchIcon, 
  FileText, 
  Sparkles,
  Clock,
  ArrowRight,
  Filter
} from 'lucide-react'
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Contract } from '@/types'

const mockSearchResults: Contract[] = [
  {
    id: '1',
    contractNumber: 'CT-2025-001',
    title: '华为服务器采购合同',
    type: '采购合同',
    department: '科技中心',
    status: '执行中',
    parties: ['华为技术有限公司'],
    amount: 500000,
    currency: 'CNY',
    startDate: '2025-01-15',
    endDate: '2025-12-31',
    createdAt: '2025-01-15',
    updatedAt: '2025-01-15',
    fileUrl: '#',
  },
  {
    id: '4',
    contractNumber: 'CT-2025-004',
    title: '办公场地租赁合同',
    type: '租赁合同',
    department: '人力行政中心',
    status: '执行中',
    parties: ['XX物业管理有限公司'],
    amount: 1200000,
    currency: 'CNY',
    startDate: '2024-01-01',
    endDate: '2025-12-31',
    createdAt: '2024-01-01',
    updatedAt: '2025-01-10',
    fileUrl: '#',
  },
]

const suggestionQueries = [
  '帮我找和华为签的合同',
  '查询2023年的采购合同',
  '找财务中心的所有NDA',
  '即将到期的合同有哪些',
  '金额超过100万的合同',
]

const recentSearches = [
  '华为采购合同',
  '腾讯云服务',
  '2024年租赁合同',
]

export function Search() {
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [results, setResults] = useState<Contract[]>([])
  const [searchType, setSearchType] = useState('semantic')

  const handleSearch = (searchQuery: string = query) => {
    if (!searchQuery.trim()) return
    
    setIsSearching(true)
    setHasSearched(true)
    
    setTimeout(() => {
      setResults(mockSearchResults)
      setIsSearching(false)
    }, 1500)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
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
      <div>
        <h1 className="text-2xl font-bold mb-2">智能搜索</h1>
        <p className="text-muted-foreground">
          支持自然语言搜索，如："帮我找和华为签的那个关于服务器采购的合同"
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <SearchIcon className="absolute left-3 top-3 h-5 w-5 text-muted-foreground" />
              <Input
                placeholder="输入自然语言查询，如：帮我找和华为签的那个关于服务器采购的合同"
                className="pl-10 h-12 text-lg"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <Select value={searchType} onValueChange={setSearchType}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="semantic">语义搜索</SelectItem>
                <SelectItem value="keyword">关键词搜索</SelectItem>
                <SelectItem value="fuzzy">模糊搜索</SelectItem>
              </SelectContent>
            </Select>
            <Button size="lg" onClick={() => handleSearch()} disabled={isSearching}>
              {isSearching ? (
                <>
                  <Sparkles className="h-4 w-4 mr-2 animate-spin" />
                  搜索中...
                </>
              ) : (
                <>
                  <SearchIcon className="h-4 w-4 mr-2" />
                  搜索
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {!hasSearched && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                示例查询
              </CardTitle>
              <CardDescription>点击以下示例快速体验智能搜索</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {suggestionQueries.map((suggestion, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    className="w-full justify-start text-left h-auto py-3"
                    onClick={() => {
                      setQuery(suggestion)
                      handleSearch(suggestion)
                    }}
                  >
                    <SearchIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                    {suggestion}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                最近搜索
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {recentSearches.map((search, index) => (
                  <Button
                    key={index}
                    variant="ghost"
                    className="w-full justify-start text-left"
                    onClick={() => {
                      setQuery(search)
                      handleSearch(search)
                    }}
                  >
                    <Clock className="h-4 w-4 mr-2" />
                    {search}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {hasSearched && !isSearching && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>搜索结果</span>
              <Badge variant="secondary">
                找到 {results.length} 条相关合同
              </Badge>
            </CardTitle>
            <CardDescription>
              基于语义理解的结果，已按相关度排序
            </CardDescription>
          </CardHeader>
          <CardContent>
            {results.length > 0 ? (
              <div className="space-y-4">
                {results.map((contract) => (
                  <div
                    key={contract.id}
                    className="p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="h-5 w-5 text-primary" />
                          <span className="font-medium">{contract.title}</span>
                          {getStatusBadge(contract.status)}
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-muted-foreground">
                          <div>
                            <span className="text-xs">合同编号</span>
                            <p className="font-medium text-foreground">{contract.contractNumber}</p>
                          </div>
                          <div>
                            <span className="text-xs">合同类型</span>
                            <p className="font-medium text-foreground">{contract.type}</p>
                          </div>
                          <div>
                            <span className="text-xs">发起部门</span>
                            <p className="font-medium text-foreground">{contract.department}</p>
                          </div>
                          <div>
                            <span className="text-xs">金额</span>
                            <p className="font-medium text-foreground">
                              {contract.amount 
                                ? `¥${contract.amount.toLocaleString()}` 
                                : '-'}
                            </p>
                          </div>
                        </div>
                      </div>
                      <Link to={`/contracts/${contract.id}`}>
                        <Button variant="ghost" size="sm">
                          查看详情
                          <ArrowRight className="h-4 w-4 ml-1" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <SearchIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-lg font-medium">未找到相关合同</p>
                <p className="text-muted-foreground">
                  试试其他搜索词或调整筛选条件
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
