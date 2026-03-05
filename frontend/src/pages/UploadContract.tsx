import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload,
  FileText,
  X,
  CheckCircle,
  Loader2,
  AlertCircle,
  Sparkles
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
import { cn } from '@/lib/utils'
import { contractApi as api } from '@/lib/api'
import type { ContractType, Department } from '@/types'

interface UploadFile {
  id: string
  file: File
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error'
  progress: number
  contractId?: number
  extractedData?: {
    contractNumber?: string
    title?: string
    parties?: string[]
    amount?: number
    type?: string
  }
  error?: string
}

const contractTypes: ContractType[] = ['采购合同', '销售合同', '人力合同', 'NDA保密协议', '租赁合同', '服务合同', '投资协议', '其他']
const departments: Department[] = ['科技中心', '财务中心', '法务合规中心', '风控中心', '普惠金融', '人力行政中心', '其他']

export function UploadContract() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<UploadFile[]>([])
  const [dragActive, setDragActive] = useState(false)
  const uploadingRef = useRef<Set<string>>(new Set())

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const uploadSingleFile = useCallback(async (uploadFile: UploadFile) => {
    // 防止重复上传
    if (uploadingRef.current.has(uploadFile.id)) return
    uploadingRef.current.add(uploadFile.id)

    setFiles(p => p.map(f =>
      f.id === uploadFile.id ? { ...f, status: 'uploading' as const, progress: 30 } : f
    ))

    try {
      const result = await api.upload(uploadFile.file)
      const data = result.data || result
      const contractId = data.contract_id
      setFiles(p => p.map(f =>
        f.id === uploadFile.id ? {
          ...f,
          status: 'completed' as const,
          progress: 100,
          contractId,
          extractedData: {
            contractNumber: data.contract_number || '',
            title: data.extracted_data?.title || uploadFile.file.name.replace('.pdf', ''),
            parties: data.extracted_data?.parties || [],
            amount: data.extracted_data?.amount || 0,
            type: data.extracted_data?.contract_type || '服务合同',
          }
        } : f
      ))
      // 单文件上传时自动跳转到详情页
      if (contractId) {
        setTimeout(() => navigate(`/contracts/${contractId}?autoparse=1`), 800)
      }
    } catch (error) {
      setFiles(p => p.map(f =>
        f.id === uploadFile.id ? {
          ...f,
          status: 'error' as const,
          error: error instanceof Error ? error.message : '上传失败'
        } : f
      ))
    }
  }, [])

  const processFiles = useCallback((fileList: FileList) => {
    const newFiles: UploadFile[] = Array.from(fileList)
      .filter(file => file.type === 'application/pdf')
      .map(file => ({
        id: Math.random().toString(36).substring(7),
        file,
        status: 'pending' as const,
        progress: 0,
      }))

    setFiles(prev => [...prev, ...newFiles])

    // 在 setState 外部发起上传，避免重复
    newFiles.forEach((uploadFile, index) => {
      setTimeout(() => uploadSingleFile(uploadFile), index * 300)
    })
  }, [uploadSingleFile])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(e.dataTransfer.files)
    }
  }, [processFiles])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(e.target.files)
    }
  }

  const removeFile = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId))
  }

  const getStatusIcon = (status: UploadFile['status']) => {
    switch (status) {
      case 'pending':
        return <FileText className="h-5 w-5 text-muted-foreground" />
      case 'uploading':
      case 'processing':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'error':
        return <AlertCircle className="h-5 w-5 text-red-500" />
    }
  }

  const completedCount = files.filter(f => f.status === 'completed').length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">上传合同</h1>
        {completedCount > 0 && (
          <Button onClick={() => navigate('/contracts')}>
            查看已上传合同 ({completedCount})
          </Button>
        )}
      </div>

      <div className="space-y-6">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                选择文件
              </CardTitle>
              <CardDescription>
                拖拽PDF文件到下方区域，或点击选择文件，支持批量上传
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className={cn(
                  "border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer",
                  dragActive 
                    ? "border-primary bg-primary/5" 
                    : "border-border hover:border-primary/50"
                )}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => document.getElementById('file-input')?.click()}
              >
                <input
                  type="file"
                  id="file-input"
                  accept=".pdf"
                  multiple
                  className="hidden"
                  onChange={handleFileInput}
                />
                <Upload className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
                <p className="text-lg font-medium mb-2">
                  拖拽PDF文件到此处
                </p>
                <p className="text-sm text-muted-foreground mb-4">
                  或点击选择文件
                </p>
                <p className="text-xs text-muted-foreground">
                  支持 PDF 格式，单个文件最大 50MB
                </p>
              </div>
            </CardContent>
          </Card>

          {files.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>上传队列</CardTitle>
                <CardDescription>
                  共 {files.length} 个文件，已完成 {completedCount} 个
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {files.map((uploadFile) => (
                    <div
                      key={uploadFile.id}
                      className="flex items-center gap-4 p-4 border rounded-lg"
                    >
                      {getStatusIcon(uploadFile.status)}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{uploadFile.file.name}</p>
                        {uploadFile.status === 'processing' && (
                          <p className="text-sm text-muted-foreground flex items-center gap-1">
                            <Sparkles className="h-3 w-3" />
                            AI 正在解析合同内容...
                          </p>
                        )}
                        {uploadFile.status === 'completed' && uploadFile.extractedData && (
                          <div className="flex flex-wrap gap-2 mt-2">
                            <Badge variant="outline">
                              {uploadFile.extractedData.contractNumber}
                            </Badge>
                            <Badge variant="secondary">
                              {uploadFile.extractedData.type}
                            </Badge>
                            {uploadFile.extractedData.amount && (
                              <Badge variant="outline">
                                ¥{uploadFile.extractedData.amount.toLocaleString()}
                              </Badge>
                            )}
                          </div>
                        )}
                        {uploadFile.error && (
                          <p className="text-sm text-red-500 mt-1">
                            {uploadFile.error}
                          </p>
                        )}
                      </div>
                      {(uploadFile.status === 'uploading' || uploadFile.status === 'processing') && (
                        <div className="w-24">
                          <div className="h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300"
                              style={{ width: `${uploadFile.progress}%` }}
                            />
                          </div>
                        </div>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeFile(uploadFile.id)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>



      </div>
    </div>
  )
}
