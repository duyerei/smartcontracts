import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload,
  FileText,
  X,
  CheckCircle,
  Loader2,
  AlertCircle,
  Sparkles,
  CreditCard,
  Download,
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
import { cn } from '@/lib/utils'
import { contractApi, paymentManagementApi } from '@/lib/api'

// ─── 合同上传 ────────────────────────────────────────────────────────────────

interface UploadFile {
  id: string
  file: File
  status: 'pending' | 'uploading' | 'completed' | 'error'
  progress: number
  contractId?: number
  extractedData?: { contractNumber?: string; title?: string; type?: string; amount?: number }
  error?: string
}

function ContractUploadTab() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<UploadFile[]>([])
  const [dragActive, setDragActive] = useState(false)
  const uploadingRef = useRef<Set<string>>(new Set())

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave') setDragActive(false)
  }, [])

  const uploadSingleFile = useCallback(async (uploadFile: UploadFile) => {
    if (uploadingRef.current.has(uploadFile.id)) return
    uploadingRef.current.add(uploadFile.id)
    setFiles(p => p.map(f => f.id === uploadFile.id ? { ...f, status: 'uploading' as const, progress: 30 } : f))
    try {
      const result = await contractApi.upload(uploadFile.file)
      const data = result.data || result
      const contractId = data.contract_id

      // 上传成功后，轮询等待后台完成第一次解析（title不再是"解析中..."），再跳转
      // 最多等10秒，超时直接跳转
      if (contractId) {
        const parsingTitles = ['解析中...', '扫描件识别中...', '识别中...']
        let waited = 0
        const maxWait = 10000
        const pollInterval = 800

        const waitAndNavigate = async () => {
          while (waited < maxWait) {
            await new Promise(r => setTimeout(r, pollInterval))
            waited += pollInterval
            try {
              const check = await contractApi.get(contractId)
              if (check.data && !parsingTitles.includes((check.data as any).title)) {
                break  // 后台已完成第一次解析
              }
            } catch {}
          }
          setFiles(p => p.map(f => f.id === uploadFile.id ? {
            ...f, status: 'completed' as const, progress: 100, contractId,
            extractedData: {
              contractNumber: data.contract_number || '',
              title: data.extracted_data?.title || uploadFile.file.name.replace('.pdf', ''),
              amount: data.extracted_data?.amount || 0,
              type: data.extracted_data?.contract_type || '服务合同',
            }
          } : f))
          navigate(`/contracts/${contractId}`)
        }
        waitAndNavigate()
      }
    } catch (error) {
      setFiles(p => p.map(f => f.id === uploadFile.id ? {
        ...f, status: 'error' as const, error: error instanceof Error ? error.message : '上传失败'
      } : f))
    }
  }, [navigate])

  const processFiles = useCallback((fileList: FileList) => {
    const newFiles: UploadFile[] = Array.from(fileList)
      .filter(file => file.type === 'application/pdf')
      .map(file => ({ id: Math.random().toString(36).substring(7), file, status: 'pending' as const, progress: 0 }))
    setFiles(prev => [...prev, ...newFiles])
    newFiles.forEach((f, i) => setTimeout(() => uploadSingleFile(f), i * 300))
  }, [uploadSingleFile])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files?.length) processFiles(e.dataTransfer.files)
  }, [processFiles])

  const completedCount = files.filter(f => f.status === 'completed').length

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            上传合同PDF
          </CardTitle>
          <CardDescription>拖拽PDF文件到下方区域，或点击选择文件，支持批量上传，AI自动解析合同内容</CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={cn(
              "border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer",
              dragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => document.getElementById('contract-file-input')?.click()}
          >
            <input type="file" id="contract-file-input" accept=".pdf" multiple className="hidden"
              onChange={(e) => { if (e.target.files?.length) processFiles(e.target.files) }} />
            <Upload className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
            <p className="text-lg font-medium mb-2">拖拽PDF文件到此处</p>
            <p className="text-sm text-muted-foreground mb-4">或点击选择文件，支持批量上传</p>
            <p className="text-xs text-muted-foreground">支持 PDF 格式，单个文件最大 50MB</p>
          </div>
        </CardContent>
      </Card>

      {files.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>上传队列</CardTitle>
            <CardDescription>共 {files.length} 个文件，已完成 {completedCount} 个</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {files.map((f) => (
                <div key={f.id} className="flex items-center gap-4 p-4 border rounded-lg">
                  {f.status === 'uploading' ? <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
                    : f.status === 'completed' ? <CheckCircle className="h-5 w-5 text-green-500" />
                    : f.status === 'error' ? <AlertCircle className="h-5 w-5 text-red-500" />
                    : <FileText className="h-5 w-5 text-muted-foreground" />}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{f.file.name}</p>
                    {f.status === 'uploading' && (
                      <p className="text-sm text-muted-foreground flex items-center gap-1">
                        <Sparkles className="h-3 w-3" />AI 正在解析合同内容...
                      </p>
                    )}
                    {f.status === 'completed' && f.extractedData && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {f.extractedData.contractNumber && <Badge variant="outline">{f.extractedData.contractNumber}</Badge>}
                        {f.extractedData.type && <Badge variant="secondary">{f.extractedData.type}</Badge>}
                        {f.extractedData.amount ? <Badge variant="outline">¥{f.extractedData.amount.toLocaleString()}</Badge> : null}
                      </div>
                    )}
                    {f.error && <p className="text-sm text-red-500 mt-1">{f.error}</p>}
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => setFiles(p => p.filter(x => x.id !== f.id))}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            {completedCount > 0 && (
              <div className="mt-4">
                <Button onClick={() => navigate('/contracts')}>查看已上传合同 ({completedCount})</Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ─── 付款单导入 ───────────────────────────────────────────────────────────────

function PaymentImportTab() {
  const navigate = useNavigate()
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave') setDragActive(false)
  }

  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) { alert('请上传PDF文件'); return }
    setUploading(true)
    try {
      const result = await paymentManagementApi.importPdf(file)
      if (result.data) {
        const paymentId = (result.data as any).payment_id
        navigate(`/payments/${paymentId}`)
      } else {
        alert(result.error || '导入失败')
      }
    } finally {
      setUploading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CreditCard className="h-5 w-5" />
          上传付款申请单
        </CardTitle>
        <CardDescription>上传OA付款申请PDF，自动解析付款信息并关联合同</CardDescription>
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            "border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer",
            dragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
          )}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); const f = e.dataTransfer.files?.[0]; if (f) handleUpload(f) }}
          onClick={() => fileRef.current?.click()}
        >
          <input ref={fileRef} type="file" accept=".pdf" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = '' }} />
          <CreditCard className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <p className="text-lg font-medium mb-2">拖拽付款申请PDF到此处</p>
          <p className="text-sm text-muted-foreground mb-4">或点击选择文件</p>
          <Button variant="outline" disabled={uploading} onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}>
            <Upload className="h-4 w-4 mr-2" />
            {uploading ? '解析中...' : '选择文件'}
          </Button>
          <p className="text-xs text-muted-foreground mt-4">支持 PDF 格式，自动提取付款信息</p>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── OA导入 ───────────────────────────────────────────────────────────────────

function OAImportTab() {
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const token = (window as any).__auth_token__ || localStorage.getItem('token') || ''
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      if (f.name.endsWith('.json')) { setFile(f); setError(''); setResult(null) }
      else { setError('请选择JSON格式的文件'); setFile(null) }
    }
  }

  const handleImport = async () => {
    if (!file) { setError('请先选择文件'); return }
    setImporting(true)
    setError('')
    setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const authToken = localStorage.getItem('token') || token
      const response = await fetch(`${API_BASE_URL}/import/contracts`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
        body: formData,
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `导入失败: ${response.status}`)
      }
      setResult(await response.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败')
    } finally {
      setImporting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="h-5 w-5" />
          OA系统批量导入
        </CardTitle>
        <CardDescription>上传从OA系统导出的JSON数据文件，批量导入合同及附件</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="border rounded-lg p-4 bg-muted/30 text-sm text-muted-foreground space-y-1">
          <p>1. 从OA系统导出合同数据为JSON格式</p>
          <p>2. 选择导出的JSON文件上传</p>
          <p>3. 系统自动解析并导入合同信息及附件</p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex-1">
            <div className={cn(
              "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
              file ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
            )}>
              <input type="file" accept=".json" className="hidden" onChange={handleFileChange} />
              {file ? (
                <div className="flex items-center justify-center gap-2 text-primary">
                  <CheckCircle className="h-5 w-5" />
                  <span className="font-medium">{file.name}</span>
                </div>
              ) : (
                <>
                  <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm">点击选择JSON文件</p>
                </>
              )}
            </div>
          </label>
        </div>
        {error && (
          <div className="flex items-center gap-2 text-destructive text-sm p-3 bg-destructive/10 rounded-lg">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}
        <Button onClick={handleImport} disabled={!file || importing} className="w-full">
          {importing ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />导入中...</> : '开始导入'}
        </Button>
        {result && (
          <div className="border rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2 text-green-600 font-medium">
              <CheckCircle className="h-5 w-5" />
              导入完成
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div className="text-center p-2 bg-green-50 rounded"><p className="text-2xl font-bold text-green-600">{result.imported}</p><p className="text-muted-foreground">成功</p></div>
              <div className="text-center p-2 bg-yellow-50 rounded"><p className="text-2xl font-bold text-yellow-600">{result.skipped}</p><p className="text-muted-foreground">跳过</p></div>
              <div className="text-center p-2 bg-red-50 rounded"><p className="text-2xl font-bold text-red-600">{result.failed}</p><p className="text-muted-foreground">失败</p></div>
            </div>
            {result.errors?.length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="text-sm font-medium text-destructive">失败详情：</p>
                {result.errors.map((e: any, i: number) => (
                  <p key={i} className="text-xs text-muted-foreground">{e.contract_number}: {e.error}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── 主页面 ───────────────────────────────────────────────────────────────────

type TabKey = 'contract' | 'payment' | 'oa'

const tabs: { key: TabKey; label: string; icon: React.ReactNode; desc: string }[] = [
  { key: 'contract', label: '合同导入', icon: <FileText className="h-4 w-4" />, desc: '上传PDF，AI自动解析' },
  { key: 'payment', label: '付款单导入', icon: <CreditCard className="h-4 w-4" />, desc: '上传OA付款申请PDF' },
  { key: 'oa', label: 'OA批量导入', icon: <Download className="h-4 w-4" />, desc: '从OA系统批量导入' },
]

export function UploadContract() {
  const [activeTab, setActiveTab] = useState<TabKey>('contract')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">数据导入</h1>
        <p className="text-muted-foreground text-sm mt-1">支持合同PDF上传、付款单导入、OA系统批量导入</p>
      </div>

      {/* Tab 导航 */}
      <div className="grid grid-cols-3 gap-3">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "flex items-center gap-3 p-4 rounded-lg border text-left transition-colors",
              activeTab === tab.key
                ? "border-primary bg-primary/5 text-primary"
                : "border-border hover:border-primary/30 hover:bg-muted/50 text-muted-foreground"
            )}
          >
            <div className={cn("p-2 rounded-md", activeTab === tab.key ? "bg-primary/10" : "bg-muted")}>
              {tab.icon}
            </div>
            <div>
              <p className="font-medium text-sm text-foreground">{tab.label}</p>
              <p className="text-xs text-muted-foreground">{tab.desc}</p>
            </div>
          </button>
        ))}
      </div>

      {activeTab === 'contract' && <ContractUploadTab />}
      {activeTab === 'payment' && <PaymentImportTab />}
      {activeTab === 'oa' && <OAImportTab />}
    </div>
  )
}
