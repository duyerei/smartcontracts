import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  FileText, 
  Download, 
  Edit, 
  Trash2,
  Sparkles,
  AlertTriangle,
  Clock,
  Building,
  Calendar,
  DollarSign,
  Shield,
  User,
  Save,
  X
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
import { SupplementList } from '@/components/SupplementList'
import { PaymentList } from '@/components/PaymentList'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { contractApi } from '@/lib/api'
import type { Contract } from '@/types'

export function ContractDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [contract, setContract] = useState<Contract | null>(null)
  const [contractText, setContractText] = useState<string>('')
  const [contractStructured, setContractStructured] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingText, setLoadingText] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isReparsing, setIsReparsing] = useState(false)
  const [isLlmParsing, setIsLlmParsing] = useState(false)
  const [showFullRisk, setShowFullRisk] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('info')
  const [previewUrl, setPreviewUrl] = useState<string>('')
  const [editForm, setEditForm] = useState({
    title: '',
    contractType: '',
    department: '',
    parties: '',
    amount: '',
    signedDate: '',
    startDate: '',
    endDate: ''
  })

  // 判断summary是否为LLM生成（含Markdown格式标记或长度较长）
  const isLlmSummary = (summary?: string) => {
    if (!summary) return false
    // 检查是否包含Markdown格式标记
    if (/^#{1,3}\s|\*\*|^>\s|^-\s.*：/m.test(summary)) return true
    // 检查是否包含"主要合作内容"、"付款方式"等关键词（LLM生成的摘要通常包含这些）
    if (/主要合作内容|付款方式|服务内容|产品.*明细|价格明细/.test(summary)) return true
    // 如果摘要很长（超过500字符），也认为是LLM生成的
    if (summary.length > 500) return true
    return false
  }

  useEffect(() => {
    const loadContract = async () => {
      if (!id) return
      setLoading(true)
      const result = await contractApi.get(id)
      if (result.data) {
        const c = result.data as unknown as Contract
        setContract(c)
        // 如果summary存在但不是LLM格式，说明后台还在解析
        if (c.summary && !isLlmSummary(c.summary)) {
          setIsLlmParsing(true)
        }
        
        // 加载预览URL
        loadPreviewUrl(id)
      }
      setLoading(false)
    }
    loadContract()
  }, [id])

  // 加载预览URL
  const loadPreviewUrl = async (contractId: string) => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/contracts/${contractId}/download?mode=preview`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        setPreviewUrl(url)
      }
    } catch (error) {
      console.error('加载预览失败:', error)
    }
  }

  // 清理blob URL
  useEffect(() => {
    return () => {
      if (previewUrl) {
        window.URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  // 轮询检测LLM解析是否完成
  useEffect(() => {
    if (!isLlmParsing || !id) return
    
    let pollCount = 0
    const maxPolls = 24 // 最多轮询24次（2分钟）
    
    const interval = setInterval(async () => {
      pollCount++
      
      const result = await contractApi.get(id)
      if (result.data) {
        const c = result.data as unknown as Contract
        if (isLlmSummary(c.summary)) {
          setContract(c)
          setIsLlmParsing(false)
        } else if (pollCount >= maxPolls) {
          // 超时，停止轮询
          console.log('LLM解析超时，停止轮询')
          setContract(c)
          setIsLlmParsing(false)
        }
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [isLlmParsing, id])

  const handleEdit = () => {
    if (!contract) return
    setEditForm({
      title: contract.title || '',
      contractType: contract.type || '',
      department: contract.department || '',
      parties: Array.isArray(contract.parties) ? contract.parties.join('\n') : '',
      amount: contract.amount ? String(contract.amount) : '',
      signedDate: contract.signedDate || '',
      startDate: contract.startDate || '',
      endDate: contract.endDate || ''
    })
    setIsEditing(true)
  }

  const handleSaveEdit = async () => {
    if (!id || !contract) return
    
    setIsSaving(true)
    try {
      const parties = editForm.parties.split('\n').filter(p => p.trim())
      
      const updateData: Record<string, unknown> = {
        title: editForm.title,
        contract_type: editForm.contractType,
        department: editForm.department,
        parties: parties,
        amount: editForm.amount ? parseFloat(editForm.amount) : null,
        signed_date: editForm.signedDate ? editForm.signedDate : null,
        start_date: editForm.startDate ? editForm.startDate : null,
        end_date: editForm.endDate ? editForm.endDate : null,
      }
      
      const result = await contractApi.update(Number(id), updateData)
      if (result.data) {
        const updated = result.data as unknown as Contract
        setContract(updated)
        setIsEditing(false)
      }
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败，请重试')
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
  }

  const handleDelete = async () => {
    if (!id) return
    if (!confirm('确定要删除这份合同吗？此操作不可恢复。')) return
    
    setIsDeleting(true)
    const result = await contractApi.delete(id)
    if (result.data) {
      navigate('/contracts')
    } else {
      alert('删除失败: ' + result.error)
    }
    setIsDeleting(false)
  }

  const handleAnalyze = async () => {
    if (!id) return
    setIsAnalyzing(true)
    try {
      const result = await contractApi.analyze(Number(id))
      if (result.data) {
        // 重新加载合同数据以获取最新的风险分析结果
        const contractResult = await contractApi.get(id)
        if (contractResult.data) {
          setContract(contractResult.data as unknown as Contract)
        }
      }
    } catch (error) {
      alert('风险分析失败: ' + (error as Error).message)
    }
    setIsAnalyzing(false)
  }

  const loadContractText = async () => {
    if (!id) return
    setLoadingText(true)
    const result = await contractApi.getText(Number(id))
    if (result.data) {
      setContractText(result.data.text || '')
      setContractStructured(result.data.structured || null)
    }
    setLoadingText(false)
  }

  const handleReparse = async () => {
    if (!id) return

    setIsReparsing(true)
    setIsLlmParsing(true)
    try {
      const result = await contractApi.reparse(Number(id))
      if (result) {
        // 立即重新加载合同数据，显示基础解析结果
        const contractResult = await contractApi.get(id)
        if (contractResult.data) {
          setContract(contractResult.data as unknown as Contract)
        }
        // 不再弹窗提示，让轮询机制自动检测LLM解析完成
      }
    } catch (error) {
      alert('重新解析失败: ' + (error as Error).message)
      setIsLlmParsing(false)
    }
    setIsReparsing(false)
  }

  const handleDownload = async () => {
    if (!contract?.id) return
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/contracts/${contract.id}/download`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        alert('下载失败')
        return
      }
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${contract.title || 'contract'}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('下载失败:', error)
      alert('下载失败')
    }
  }

  const handlePreview = async () => {
    if (!contract?.id) return
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/contracts/${contract.id}/download?mode=preview`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        alert('预览失败')
        return
      }
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      window.open(url, '_blank')
    } catch (error) {
      console.error('预览失败:', error)
      alert('预览失败')
    }
  }

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

  const getRiskBadge = (severity: string) => {
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
    return <Badge variant={variants[severity as keyof typeof variants] || 'default'}>{labels[severity as keyof typeof labels] || '未知'}</Badge>
  }

  const formatAmount = (amount: number | null | undefined, currency: string) => {
    if (!amount) return '-'
    return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: currency || 'CNY' }).format(amount)
  }

  const formatDate = (date: string | null | undefined) => {
    if (!date) return '-'
    return date.split('T')[0]
  }

  const getParties = (parties: string | string[] | unknown) => {
    if (typeof parties === 'string') {
      try {
        const parsed = JSON.parse(parties)
        return Array.isArray(parsed) ? parsed.join(', ') : parties
      } catch {
        return parties
      }
    }
    if (Array.isArray(parties)) {
      return parties.join(', ')
    }
    return String(parties || '-')
  }

  // 分离甲方、乙方、丙方显示（支持三方合同）
  const getPartyInfo = (parties: string | string[] | unknown) => {
    let partyList: string[] = []
    
    if (typeof parties === 'string') {
      try {
        const parsed = JSON.parse(parties)
        partyList = Array.isArray(parsed) ? parsed : [parties]
      } catch {
        // 如果解析失败，尝试按逗号分割
        partyList = parties.split(',').map(p => p.trim())
      }
    } else if (Array.isArray(parties)) {
      partyList = parties.map(p => String(p))
    } else if (parties) {
      partyList = [String(parties)]
    }

    // 过滤掉空值、null、待填写、未识别等无效值
    partyList = partyList.filter(p => {
      const str = String(p).trim()
      return str && str !== 'null' && str !== '待填写' && str !== 'undefined' && str !== '未识别'
    })

    // 第一个是甲方，第二个是乙方，第三个是丙方（如果存在）
    const partyA = partyList[0] || ''
    const partyB = partyList[1] || ''
    const partyC = partyList[2] || ''
    const other = partyList.slice(3)

    return { partyA, partyB, partyC, other }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    )
  }

  if (!contract) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">合同不存在</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/contracts">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{contract.title || '未命名合同'}</h1>
            <p className="text-muted-foreground">{contract.contractNumber || '-'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleDownload}>
            <Download className="h-4 w-4 mr-2" />
            下载
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
            <Trash2 className="h-4 w-4 mr-2" />
            {isDeleting ? '删除中...' : '删除'}
          </Button>
        </div>
      </div>

      {/* 顶部标签导航 */}
      <div className="border-b">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab('info')}
            className={`pb-3 px-1 border-b-2 transition-colors ${
              activeTab === 'info'
                ? 'border-primary text-primary font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            合同信息
          </button>
          <button
            onClick={() => setActiveTab('risk')}
            className={`pb-3 px-1 border-b-2 transition-colors ${
              activeTab === 'risk'
                ? 'border-primary text-primary font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            风险分析
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`pb-3 px-1 border-b-2 transition-colors ${
              activeTab === 'history'
                ? 'border-primary text-primary font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            操作记录
          </button>
        </div>
      </div>

      {activeTab === 'info' && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
              <Card className={`ai-analyzing-card ${isLlmParsing || isReparsing ? "is-loading" : ""}`}>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle>基本信息</CardTitle>
                  <Button variant="outline" size="sm" onClick={handleEdit}>
                    <Edit className="h-4 w-4 mr-2" />
                    编辑
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-6">
                    <div className="flex items-start gap-3">
                      <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm text-muted-foreground">合同类型</p>
                        <p className="font-medium">{contract.type || '-'}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Building className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm text-muted-foreground">发起部门</p>
                        <p className="font-medium">{contract.department || '-'}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm text-muted-foreground">签约方</p>
                        {(() => {
                          const { partyA, partyB, partyC, other } = getPartyInfo(contract.parties)
                          return (
                            <div className="space-y-1">
                              {partyA && <p className="font-medium">甲方：{partyA}</p>}
                              {partyB && <p className="font-medium">乙方：{partyB}</p>}
                              {partyC && <p className="font-medium">丙方：{partyC}</p>}
                              {other.length > 0 && <p className="font-medium">{other.join(', ')}</p>}
                              {!partyA && !partyB && !partyC && other.length === 0 && <p className="font-medium text-muted-foreground">未识别</p>}
                            </div>
                          )
                        })()}
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <DollarSign className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm text-muted-foreground">合同金额</p>
                        <p className="font-medium">{formatAmount(contract.amount, contract.currency)}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm text-muted-foreground">签订时间</p>
                        <p className="font-medium">{contract.signedDate ? formatDate(contract.signedDate) : '未识别'}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm text-muted-foreground">有效期</p>
                        <p className="font-medium">
                          {contract.startDate && contract.endDate 
                            ? `${formatDate(contract.startDate)} ~ ${formatDate(contract.endDate)}`
                            : contract.startDate 
                              ? `${formatDate(contract.startDate)} ~ 未识别`
                              : contract.endDate
                                ? `未识别 ~ ${formatDate(contract.endDate)}`
                                : '未识别'}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Clock className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm text-muted-foreground">合同状态</p>
                        <div className="mt-1">{getStatusBadge(contract.status, contract.endDate)}</div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className={`ai-analyzing-card ${isLlmParsing || isReparsing ? "is-loading" : ""}`}>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle>主要合作内容与付款方式</CardTitle>
                  {isLlmParsing || isReparsing ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Sparkles className="h-4 w-4 animate-spin text-primary" />
                      <span>AI正在智能解析中，请稍候...</span>
                    </div>
                  ) : (
                    <Button variant="outline" size="sm" onClick={handleReparse}>
                      <Sparkles className="h-4 w-4 mr-2" />
                      重新解析
                    </Button>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:text-foreground prose-p:text-muted-foreground prose-li:text-muted-foreground prose-strong:text-foreground prose-td:text-muted-foreground prose-th:text-foreground">
                    {contract.summary ? (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          table: ({ children }) => (
                            <div className="overflow-x-auto my-4">
                              <table className="w-full text-sm border-collapse border border-border">
                                {children}
                              </table>
                            </div>
                          ),
                          thead: ({ children }) => (
                            <thead className="bg-muted">{children}</thead>
                          ),
                          th: ({ children }) => (
                            <th className="border border-border px-3 py-2 text-left font-medium">{children}</th>
                          ),
                          td: ({ children }) => (
                            <td className="border border-border px-3 py-2">{children}</td>
                          ),
                          tr: ({ children }) => (
                            <tr className="hover:bg-muted/50">{children}</tr>
                          ),
                        }}
                      >
                        {(() => {
                          // 预处理：将嵌套在列表项内的Markdown表格提取为独立段落
                          const lines = contract.summary.split('\n')
                          const result: string[] = []
                          let i = 0
                          while (i < lines.length) {
                            const trimmed = lines[i].trimStart()
                            // 检测以 | 开头的表格行（可能被缩进或嵌套在列表中）
                            if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
                              // 收集连续的表格行
                              const tableLines: string[] = []
                              while (i < lines.length) {
                                const t = lines[i].trimStart()
                                if (t.startsWith('|') && t.endsWith('|')) {
                                  tableLines.push(t) // 去掉缩进
                                  i++
                                } else {
                                  break
                                }
                              }
                              // 在表格前后插入空行，确保作为独立块解析
                              result.push('')
                              result.push(...tableLines)
                              result.push('')
                            } else {
                              result.push(lines[i])
                              i++
                            }
                          }
                          return result.join('\n')
                        })()}
                      </ReactMarkdown>
                    ) : (
                      <p className="text-muted-foreground">暂无内容</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* 补充协议列表 */}
              {id && <SupplementList contractId={parseInt(id)} />}

              {/* 付款管理列表 */}
              {id && <PaymentList contractId={parseInt(id)} />}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>合同预览</CardTitle>
            </CardHeader>
            <CardContent>
              {contract?.fileUrl ? (
                <div className="space-y-4">
                  <div className="aspect-[3/4] bg-muted rounded-lg overflow-hidden">
                    {previewUrl ? (
                      <iframe
                        src={previewUrl}
                        className="w-full h-full"
                        title="合同预览"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <p className="text-muted-foreground">加载预览中...</p>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1" onClick={handlePreview}>
                      <FileText className="h-4 w-4 mr-2" />
                      预览
                    </Button>
                    <Button variant="outline" className="flex-1" onClick={handleDownload}>
                      <Download className="h-4 w-4 mr-2" />
                      下载
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="aspect-[3/4] bg-muted rounded-lg flex items-center justify-center">
                  <div className="text-center">
                    <FileText className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
                    <p className="text-muted-foreground">暂无合同文件</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      )}

      {activeTab === 'risk' && (
        <Card className={`ai-analyzing-card ${isAnalyzing ? "is-loading" : ""}`}>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>AI风险分析</CardTitle>
              <CardDescription>基于千帆大模型智能分析合同风险</CardDescription>
            </div>
            {isAnalyzing ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Sparkles className="h-4 w-4 animate-spin text-primary" />
                <span>AI正在智能解析中，请稍候...</span>
              </div>
            ) : (
              <Button variant="outline" size="sm" onClick={handleAnalyze}>
                <Sparkles className="h-4 w-4 mr-2" />
                {contract.riskAnalysis ? '重新分析' : '开始分析'}
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {contract.riskAnalysis ? (
              <div>
                <div className="flex items-center gap-2 mb-4 pb-4 border-b">
                  <span className="text-sm text-muted-foreground">整体风险等级：</span>
                  {getRiskBadge(contract.riskLevel || 'low')}
                  <span className="text-xs text-muted-foreground ml-auto">
                    分析时间：{contract.updatedAt || '-'}
                  </span>
                </div>
                <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:text-foreground prose-p:text-muted-foreground prose-li:text-muted-foreground prose-strong:text-foreground">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {contract.riskAnalysis}
                  </ReactMarkdown>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <AlertTriangle className="h-12 w-12 text-muted-foreground mb-4" />
                <h4 className="font-medium mb-2">尚未进行风险分析</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  点击上方"开始分析"按钮，AI将从条款完整性、付款风险、知识产权、违约责任等维度进行全面分析
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 'history' && (
        <Card>
          <CardHeader>
            <CardTitle>操作记录</CardTitle>
            <CardDescription>合同的所有操作历史</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">创建合同</span>
                    <span className="text-sm text-muted-foreground">{contract.createdAt || '-'}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    操作人：管理员 - 上传了合同文件
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={isEditing} onOpenChange={setIsEditing}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>编辑合同信息</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
            <div className="grid gap-2">
              <Label htmlFor="title">合同标题</Label>
              <Input
                id="title"
                value={editForm.title}
                onChange={(e) => setEditForm({...editForm, title: e.target.value})}
                placeholder="请输入合同标题"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="contractType">合同类型</Label>
                <Input
                  id="contractType"
                  value={editForm.contractType}
                  onChange={(e) => setEditForm({...editForm, contractType: e.target.value})}
                  placeholder="请输入合同类型"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="department">发起部门</Label>
                <Input
                  id="department"
                  value={editForm.department}
                  onChange={(e) => setEditForm({...editForm, department: e.target.value})}
                  placeholder="请输入发起部门"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="parties">签约方（每行一个）</Label>
              <Input
                id="parties"
                value={editForm.parties}
                onChange={(e) => setEditForm({...editForm, parties: e.target.value})}
                placeholder="每行一个签约方"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="amount">合同金额</Label>
              <Input
                id="amount"
                type="number"
                value={editForm.amount}
                onChange={(e) => setEditForm({...editForm, amount: e.target.value})}
                placeholder="请输入合同金额"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="signedDate">签订时间</Label>
                <Input
                  id="signedDate"
                  type="date"
                  value={editForm.signedDate}
                  onChange={(e) => setEditForm({...editForm, signedDate: e.target.value})}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="startDate">有效期开始</Label>
                <Input
                  id="startDate"
                  type="date"
                  value={editForm.startDate}
                  onChange={(e) => setEditForm({...editForm, startDate: e.target.value})}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="endDate">有效期结束</Label>
                <Input
                  id="endDate"
                  type="date"
                  value={editForm.endDate}
                  onChange={(e) => setEditForm({...editForm, endDate: e.target.value})}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCancelEdit}>
              <X className="h-4 w-4 mr-2" />
              取消
            </Button>
            <Button onClick={handleSaveEdit} disabled={isSaving}>
              <Save className="h-4 w-4 mr-2" />
              {isSaving ? '保存中...' : '保存'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
