import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom'
import { renderAsync } from 'docx-preview'
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
  User,
  Save,
  X,
  Upload
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { SupplementList } from '@/components/SupplementList'
import { PaymentList } from '@/components/PaymentList'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { contractApi, paymentManagementApi } from '@/lib/api'
import type { Contract } from '@/types'

export function ContractDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [contract, setContract] = useState<Contract | null>(null)
  const [loading, setLoading] = useState(true)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isReparsing, setIsReparsing] = useState(false)
  const [isLlmParsing, setIsLlmParsing] = useState(false)
  const [streamingSummary, setStreamingSummary] = useState('')
  const sseRef = useRef<EventSource | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('info')
  const [contractPayments, setContractPayments] = useState<any[]>([])
  const [paymentsLoading, setPaymentsLoading] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string>('')
  const [mainPreviewType, setMainPreviewType] = useState<'pdf' | 'image' | 'word' | 'unknown'>('unknown')
  const [mainWordBuffer, setMainWordBuffer] = useState<ArrayBuffer | null>(null)
  const mainWordContainerRef = useRef<HTMLDivElement>(null)
  const [wordZoom, setWordZoom] = useState(100)
  const [attachments, setAttachments] = useState<any[]>([])
  const [selectedAttachment, setSelectedAttachment] = useState<any | null>(null)
  const [attachmentPreviewUrl, setAttachmentPreviewUrl] = useState<string>('')
  const [attachmentPreviewType, setAttachmentPreviewType] = useState<'pdf' | 'image' | 'word' | 'unknown'>('unknown')
  const [isLoadingAttachment, setIsLoadingAttachment] = useState(false)
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const wordDocxContainerRef = useRef<HTMLDivElement>(null)
  const [wordArrayBuffer, setWordArrayBuffer] = useState<ArrayBuffer | null>(null)
  const [contractTypes, setContractTypes] = useState<string[]>([])
  const [uploadingAttachment, setUploadingAttachment] = useState(false)
  const uploadInputRef = useRef<HTMLInputElement>(null)
  // 付款PDF导入弹窗状态
  const [showPaymentPdfImport, setShowPaymentPdfImport] = useState(false)
  const [paymentPdfFile, setPaymentPdfFile] = useState<File | null>(null)
  const [importingPaymentPdf, setImportingPaymentPdf] = useState(false)
  const [paymentPdfResult, setPaymentPdfResult] = useState<{ success: boolean; message: string; detail?: string } | null>(null)
  const paymentPdfInputRef = useRef<HTMLInputElement>(null)
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
        
        // 只有非OA导入的合同才加载主文件预览
        if (c.source !== 'oa_import') {
          loadPreviewUrl(id)
        }
        
        // 加载附件列表（OA合同和普通合同都加载）
        loadAttachments(id)

        // 如果是从上传页跳转过来（autoparse=1），且合同还在解析中，自动触发SSE解析
        const searchParams = new URLSearchParams(location.search)
        if (searchParams.get('autoparse') === '1' && c.source !== 'oa_import') {
          // 标题还是"解析中..."说明后台异步解析还没完成，等待后台完成即可
          // 如果后台已完成（title不是解析中），直接启动SSE重新解析以获取LLM摘要
          if (c.title !== '解析中...') {
            setTimeout(() => startParseStream(id), 500)
          }
        }
      }
      setLoading(false)
    }
    loadContract()
  }, [id])

  // 加载合同类型列表（编辑时用）
  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) return
    fetch('/api/v1/contracts/contract-types', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d => setContractTypes(d.types || []))
      .catch(e => console.error('加载合同类型失败:', e))
  }, [])

  // 获取合同的付款记录
  const fetchContractPayments = async () => {
    if (!id) return
    setPaymentsLoading(true)
    try {
      const result = await paymentManagementApi.getByContract(Number(id))
      if (result.data) {
        setContractPayments(result.data.payments || [])
      }
    } catch (error) {
      console.error('获取付款记录失败:', error)
    } finally {
      setPaymentsLoading(false)
    }
  }

  // 加载附件列表
  const autoPreviewTriggered = useRef(false)
  const loadAttachments = async (contractId: string) => {
    try {
      autoPreviewTriggered.current = false  // 重新加载时允许自动预览
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/contracts/${contractId}/attachments`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        const atts = data.attachments || []
        // 主附件排在最上方
        atts.sort((a: any, b: any) => {
          if (a.is_primary && !b.is_primary) return -1
          if (!a.is_primary && b.is_primary) return 1
          return 0
        })
        setAttachments(atts)
        // 默认选择主附件，如果没有主附件则选第一个
        if (atts.length > 0) {
          const primaryAtt = atts.find((a: any) => a.is_primary) || atts[0]
          setSelectedAttachment(primaryAtt)
        }
      }
    } catch (error) {
      console.error('加载附件失败:', error)
    }
  }

  // 当选中附件且contract已加载时，自动触发预览
  useEffect(() => {
    if (selectedAttachment && contract?.id && !autoPreviewTriggered.current) {
      autoPreviewTriggered.current = true
      handleAttachmentPreview(selectedAttachment)
    }
  }, [selectedAttachment, contract?.id])

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
        const contentType = blob.type || response.headers.get('content-type') || ''
        
        if (contentType.includes('pdf')) {
          setMainPreviewType('pdf')
          const url = window.URL.createObjectURL(blob)
          setPreviewUrl(url)
        } else if (contentType.includes('image')) {
          setMainPreviewType('image')
          const url = window.URL.createObjectURL(blob)
          setPreviewUrl(url)
        } else if (contentType.includes('officedocument')) {
          // .docx格式（openxmlformats），支持在线预览
          setMainPreviewType('word')
          const arrayBuffer = await blob.arrayBuffer()
          setMainWordBuffer(arrayBuffer)
        } else if (contentType.includes('msword')) {
          // .doc旧格式，不支持在线预览
          setMainPreviewType('unknown')
        } else {
          // 兜底：尝试当PDF处理
          setMainPreviewType('pdf')
          const url = window.URL.createObjectURL(blob)
          setPreviewUrl(url)
        }
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
      if (attachmentPreviewUrl) {
        window.URL.revokeObjectURL(attachmentPreviewUrl)
      }
    }
  }, [previewUrl, attachmentPreviewUrl])

  // 处理Word文档渲染（附件）
  useEffect(() => {
    if (!wordArrayBuffer || !wordDocxContainerRef.current) return

    const renderWord = async () => {
      try {
        if (wordDocxContainerRef.current) {
          wordDocxContainerRef.current.innerHTML = ''
          await renderAsync(wordArrayBuffer, wordDocxContainerRef.current, undefined, {
            className: 'docx-preview-container',
            inWrapper: true,
            ignoreWidth: false,
            ignoreHeight: false,
            debug: false,
          })
        }
      } catch (error) {
        console.error('Word文档渲染失败:', error)
        setAttachmentError(`Word文档渲染失败: ${(error as Error).message}`)
      }
    }

    renderWord()
  }, [wordArrayBuffer])

  // 处理Word文档渲染（主合同）
  useEffect(() => {
    if (!mainWordBuffer || !mainWordContainerRef.current) return

    const renderMainWord = async () => {
      try {
        if (mainWordContainerRef.current) {
          mainWordContainerRef.current.innerHTML = ''
          await renderAsync(mainWordBuffer, mainWordContainerRef.current, undefined, {
            className: 'docx-preview-container',
            inWrapper: true,
            ignoreWidth: false,
            ignoreHeight: false,
            debug: false,
          })
        }
      } catch (error) {
        console.error('主合同Word渲染失败:', error)
      }
    }

    renderMainWord()
  }, [mainWordBuffer])

  // SSE流式解析
  const startParseStream = (contractId: string) => {
    // 关闭已有连接
    if (sseRef.current) {
      sseRef.current.close()
      sseRef.current = null
    }

    setStreamingSummary('')
    setIsLlmParsing(true)

    const token = localStorage.getItem('token')
    const url = `/api/v1/contracts/${contractId}/parse-stream?token=${encodeURIComponent(token || '')}`
    const es = new EventSource(url)
    sseRef.current = es

    es.addEventListener('fields', (e) => {
      try {
        const data = JSON.parse(e.data)
        // 立即更新标题和基本字段
        setContract(prev => {
          if (!prev) return prev
          return {
            ...prev,
            title: data.title || prev.title,
          }
        })
      } catch {}
    })

    es.addEventListener('chunk', (e) => {
      try {
        const data = JSON.parse(e.data)
        setStreamingSummary(prev => prev + (data.text || ''))
      } catch {}
    })

    es.addEventListener('done', () => {
      es.close()
      sseRef.current = null
      setIsLlmParsing(false)
      setIsReparsing(false)
      // 重新加载合同数据以获取最终状态
      contractApi.get(contractId).then(result => {
        if (result.data) {
          setContract(result.data as unknown as Contract)
          setStreamingSummary('')
        }
      })
    })

    es.addEventListener('error', () => {
      es.close()
      sseRef.current = null
      setIsLlmParsing(false)
      setIsReparsing(false)
    })

    es.onerror = () => {
      es.close()
      sseRef.current = null
      setIsLlmParsing(false)
      setIsReparsing(false)
    }
  }

  // 清理SSE连接
  useEffect(() => {
    return () => {
      if (sseRef.current) {
        sseRef.current.close()
      }
    }
  }, [])

  // OA合同解析轮询（OA合同使用旧的reparse接口，需要轮询）
  useEffect(() => {
    if (!isLlmParsing || !id || contract?.source !== 'oa_import') return

    let pollCount = 0
    const maxPolls = 60

    const interval = setInterval(async () => {
      pollCount++
      const result = await contractApi.get(id)
      if (result.data) {
        const c = result.data as unknown as Contract
        setContract(c)
        let parseComplete = false
        if ((c as any).extractedData) {
          try {
            const ed = JSON.parse((c as any).extractedData)
            if ((ed.llm_summary && ed.llm_summary.length > 50) || (ed.parsed_summary && ed.parsed_summary.length > 50)) {
              parseComplete = true
            }
          } catch {}
        }
        if (parseComplete || pollCount >= maxPolls) {
          setIsLlmParsing(false)
          setIsReparsing(false)
        }
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [isLlmParsing, id, contract?.source])

  // 普通合同"解析中..."轮询：后台异步解析完成后自动刷新并触发SSE
  useEffect(() => {
    if (!contract || contract.title !== '解析中...' || contract.source === 'oa_import') return
    if (!id) return

    let pollCount = 0
    const maxPolls = 60

    const interval = setInterval(async () => {
      pollCount++
      const result = await contractApi.get(id)
      if (result.data) {
        const c = result.data as unknown as Contract
        if (c.title !== '解析中...' || pollCount >= maxPolls) {
          setContract(c)
          clearInterval(interval)
          // 后台OCR+正则解析完成，自动触发SSE LLM解析
          if (c.title !== '解析中...' && c.title !== '解析失败') {
            startParseStream(id)
          }
        }
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [contract?.title, id])

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
    const result = await contractApi.delete(Number(id))
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

  const handleReparse = async () => {
    if (!id) return

    setIsReparsing(true)
    // 直接启动SSE流式解析（非OA合同）
    startParseStream(id)
  }

  const handleAnalyzeOaAttachment = async () => {
    if (!id) return

    // 优先使用当前选中的附件，否则使用主附件
    const targetAttachment = selectedAttachment || attachments.find(a => a.is_primary) || attachments[0]
    if (!targetAttachment) return

    setIsReparsing(true)
    setIsLlmParsing(true)
    try {
      const result = await contractApi.analyzeAttachment(Number(id), targetAttachment.id)
      if (result) {
        const contractResult = await contractApi.get(id)
        if (contractResult.data) {
          setContract(contractResult.data as unknown as Contract)
        }
      }
    } catch (error) {
      alert('分析附件失败: ' + (error as Error).message)
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

  // 处理附件上传
  const handleAttachmentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !id) return
    setUploadingAttachment(true)
    try {
      const token = localStorage.getItem('token')
      const formData = new FormData()
      formData.append('file', file)
      const resp = await fetch(`/api/v1/contracts/${id}/attachments/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '上传失败')
      }
      // 刷新附件列表
      await loadAttachments(id)
    } catch (err) {
      alert(`上传失败: ${(err as Error).message}`)
    } finally {
      setUploadingAttachment(false)
      if (uploadInputRef.current) uploadInputRef.current.value = ''
    }
  }

  // 处理附件预览 - 在页面内预览
  const handleAttachmentPreview = async (attachment: any) => {
    if (!attachment) return
    
    const fileName = attachment.file_name.toLowerCase()
    const ext = fileName.split('.').pop()
    
    setIsLoadingAttachment(true)
    setAttachmentError(null)
    setWordArrayBuffer(null)
    
    try {
      // 清理之前的预览URL
      if (attachmentPreviewUrl) {
        window.URL.revokeObjectURL(attachmentPreviewUrl)
        setAttachmentPreviewUrl('')
      }
      
      // 通过后端API获取附件
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/contracts/${contract?.id}/attachments/${attachment.id}/download`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `获取附件失败 (HTTP ${response.status})`)
      }
      
      const blob = await response.blob()
      
      // 验证blob是否为有效的文件内容
      console.log(`附件信息 - 名称: ${attachment.file_name}, 大小: ${blob.size} bytes, 类型: ${blob.type}`)
      
      // 检查是否为错误响应（如HTML错误页面）
      if (blob.type === 'text/html' || blob.type === 'application/json') {
        const text = await blob.text()
        console.error('响应内容:', text)
        throw new Error('服务器返回错误响应，请检查附件是否存在')
      }
      
      // 对于.docx文档，验证是否为有效的ZIP文件
      if (ext === 'docx') {
        const arrayBuffer = await blob.arrayBuffer()
        const view = new Uint8Array(arrayBuffer)
        const header = view.slice(0, 4)
        const headerHex = Array.from(header).map(b => b.toString(16).padStart(2, '0')).join('')
        console.log(`Word文件头: ${headerHex}`)
        
        const isValidDocx = header[0] === 0x50 && header[1] === 0x4B  // PK (ZIP)
        if (!isValidDocx) {
          console.error('无效的.docx文件格式')
          throw new Error(`无效的Word文件格式 (文件头: ${headerHex})，可能是旧版.doc格式`)
        }
      }
      
      // 根据文件类型设置预览类型
      if (ext === 'docx') {
        // .docx文档：读取为ArrayBuffer，通过renderAsync渲染
        setAttachmentPreviewType('word')
        const reader = new FileReader()
        reader.onload = (e) => {
          const arrayBuffer = e.target?.result as ArrayBuffer
          console.log(`Word文件已读取，大小: ${arrayBuffer.byteLength} bytes`)
          setWordArrayBuffer(arrayBuffer)
          setIsLoadingAttachment(false)
        }
        reader.onerror = () => {
          setAttachmentError('读取Word文件失败')
          setIsLoadingAttachment(false)
        }
        reader.readAsArrayBuffer(blob)
      } else if (ext === 'doc') {
        // .doc 文件：通过后端转 PDF 后预览
        try {
          const pdfResponse = await fetch(`/api/v1/contracts/${contract?.id}/attachments/${attachment.id}/preview-pdf`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (!pdfResponse.ok) {
            const errData = await pdfResponse.json().catch(() => ({}))
            throw new Error(errData.detail || '.doc 转 PDF 失败')
          }
          const pdfBlob = await pdfResponse.blob()
          const url = window.URL.createObjectURL(pdfBlob)
          setAttachmentPreviewUrl(url)
          setAttachmentPreviewType('pdf')
          setIsLoadingAttachment(false)
        } catch (docErr) {
          setAttachmentPreviewType('unknown')
          setAttachmentError(`.doc 转 PDF 预览失败: ${(docErr as Error).message}，请下载后查看`)
          setIsLoadingAttachment(false)
        }
      } else if (ext === 'pdf') {
        // PDF和图片：使用Blob URL
        const url = window.URL.createObjectURL(blob)
        setAttachmentPreviewUrl(url)
        setAttachmentPreviewType('pdf')
        setIsLoadingAttachment(false)
      } else if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext || '')) {
        const url = window.URL.createObjectURL(blob)
        setAttachmentPreviewUrl(url)
        setAttachmentPreviewType('image')
        setIsLoadingAttachment(false)
      } else {
        setAttachmentPreviewType('unknown')
        setAttachmentError('不支持的文件格式，请下载后查看')
        setIsLoadingAttachment(false)
      }
    } catch (error) {
      console.error('预览附件失败:', error)
      setAttachmentError(`预览附件失败: ${(error as Error).message}`)
      setIsLoadingAttachment(false)
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
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'success' | 'warning'> = {
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
          <button
            onClick={() => { setActiveTab('payments'); fetchContractPayments(); }}
            className={`pb-3 px-1 border-b-2 transition-colors ${
              activeTab === 'payments'
                ? 'border-primary text-primary font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            付款记录
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
                <CardContent className="space-y-6">
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

                  {/* 主要合作内容与付款方式 */}
                  <div className="border-t pt-6">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-sm font-semibold">主要合作内容与付款方式</h4>
                      {isLlmParsing || isReparsing ? (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Sparkles className="h-3 w-3 animate-spin text-primary" />
                          <span>AI正在智能解析中...</span>
                        </div>
                      ) : contract.source === 'oa_import' ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleAnalyzeOaAttachment}
                          disabled={attachments.length === 0}
                          title={selectedAttachment ? `解析: ${selectedAttachment.file_name}` : attachments.find(a => a.is_primary)?.file_name ? `解析主附件: ${attachments.find(a => a.is_primary)?.file_name}` : ''}
                        >
                          <Sparkles className="h-3 w-3 mr-1" />
                          合同解析
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" onClick={handleReparse}>
                          <Sparkles className="h-3 w-3 mr-1" />
                          重新解析
                        </Button>
                      )}
                    </div>
                    <div className="bg-muted rounded-lg p-4 max-h-[30vh] overflow-auto">
                      <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:text-foreground prose-p:text-muted-foreground prose-li:text-muted-foreground prose-strong:text-foreground prose-td:text-muted-foreground prose-th:text-foreground">
                        {(() => {
                          // 流式输出优先显示
                          if (streamingSummary) {
                            return (
                              <ReactMarkdown remarkPlugins={[remarkGfm]}
                                components={{
                                  table: ({ children }) => <div className="overflow-x-auto my-4"><table className="w-full text-sm border-collapse border border-border">{children}</table></div>,
                                  thead: ({ children }) => <thead className="bg-muted">{children}</thead>,
                                  th: ({ children }) => <th className="border border-border px-3 py-2 text-left font-medium">{children}</th>,
                                  td: ({ children }) => <td className="border border-border px-3 py-2">{children}</td>,
                                  tr: ({ children }) => <tr className="hover:bg-muted/50">{children}</tr>,
                                }}
                              >{streamingSummary}</ReactMarkdown>
                            )
                          }

                          // 对于OA导入的合同，从extracted_data.llm_summary读取LLM生成的摘要
                          let displaySummary = contract.summary
                          if (contract.source === 'oa_import' && contract.extractedData) {
                            try {
                              const extracted = JSON.parse(contract.extractedData)
                              if (extracted.llm_summary) {
                                displaySummary = extracted.llm_summary
                              } else if (extracted.parsed_summary) {
                                displaySummary = extracted.parsed_summary
                              }
                            } catch {
                              // 如果解析失败，使用原始summary
                            }
                          }
                          
                          return displaySummary ? (
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
                              {displaySummary}
                            </ReactMarkdown>
                          ) : (
                            <p className="text-muted-foreground text-sm">暂无内容</p>
                          )
                        })()}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 合同概况（所有合同都显示） */}
              {(true) && (
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>合同概况</CardTitle>
                      <CardDescription>{contract.source === 'oa_import' ? '从OA系统导入的流程信息' : '合同基本概况信息'}</CardDescription>
                    </div>
                    {contract.source === 'oa_import' && (
                      <Button variant="outline" size="sm" onClick={() => setShowPaymentPdfImport(true)}>
                        <Upload className="h-4 w-4 mr-2" />
                        导入流程表单PDF
                      </Button>
                    )}
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      // 解析raw_data中的OA字段
                      let oaRaw: Record<string, any> = {}
                      if ((contract as any).rawData) {
                        try {
                          oaRaw = typeof (contract as any).rawData === 'string' 
                            ? JSON.parse((contract as any).rawData) 
                            : (contract as any).rawData
                        } catch {}
                      }
                      return (
                        <>
                          {/* 流程基本信息 */}
                          <div className="mb-6">
                            <h4 className="text-sm font-semibold mb-3">流程基本信息</h4>
                            <div className="grid grid-cols-2 gap-6">
                              {oaRaw['doc_subject'] && (
                                <div className="flex items-start gap-3 col-span-2">
                                  <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">OA主题</p>
                                    <p className="font-medium">{oaRaw['doc_subject']}</p>
                                  </div>
                                </div>
                              )}
                              {contract.applicant && (
                                <div className="flex items-start gap-3">
                                  <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">申请人</p>
                                    <p className="font-medium">{contract.applicant}</p>
                                  </div>
                                </div>
                              )}
                              {(oaRaw['申请人岗位'] || contract.position) && (
                                <div className="flex items-start gap-3">
                                  <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">申请人岗位</p>
                                    <p className="font-medium">{oaRaw['申请人岗位'] || contract.position}</p>
                                  </div>
                                </div>
                              )}
                              {contract.department && (
                                <div className="flex items-start gap-3">
                                  <Building className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">发起部门</p>
                                    <p className="font-medium">{contract.department}</p>
                                  </div>
                                </div>
                              )}
                              {contract.company && (
                                <div className="flex items-start gap-3">
                                  <Building className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">我方公司</p>
                                    <p className="font-medium">{contract.company}</p>
                                  </div>
                                </div>
                              )}
                              {contract.counterparty && (
                                <div className="flex items-start gap-3">
                                  <Building className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">对方单位</p>
                                    <p className="font-medium">{contract.counterparty}</p>
                                  </div>
                                </div>
                              )}
                              {contract.counterpartyContact && (
                                <div className="flex items-start gap-3">
                                  <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">对方联系人</p>
                                    <p className="font-medium">{contract.counterpartyContact}</p>
                                  </div>
                                </div>
                              )}
                              {contract.counterpartyAddress && (
                                <div className="flex items-start gap-3">
                                  <Building className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">对方地址</p>
                                    <p className="font-medium">{contract.counterpartyAddress}</p>
                                  </div>
                                </div>
                              )}
                              {contract.amount && (
                                <div className="flex items-start gap-3">
                                  <DollarSign className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">合同金额</p>
                                    <p className="font-medium">{formatAmount(contract.amount, contract.currency)}</p>
                                  </div>
                                </div>
                              )}
                              {contract.paymentType && (
                                <div className="flex items-start gap-3">
                                  <DollarSign className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">付款方式</p>
                                    <p className="font-medium">{contract.paymentType}</p>
                                  </div>
                                </div>
                              )}
                              {contract.copies && (
                                <div className="flex items-start gap-3">
                                  <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">合同份数</p>
                                    <p className="font-medium">{contract.copies}</p>
                                  </div>
                                </div>
                              )}
                              {oaRaw['是否为已审批定稿制式业务合同'] && (
                                <div className="flex items-start gap-3">
                                  <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">是否制式合同</p>
                                    <p className="font-medium">{oaRaw['是否为已审批定稿制式业务合同']}</p>
                                  </div>
                                </div>
                              )}
                              {contract.signedDate && (
                                <div className="flex items-start gap-3">
                                  <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">签订时间</p>
                                    <p className="font-medium">{formatDate(contract.signedDate)}</p>
                                  </div>
                                </div>
                              )}
                              {contract.startDate && contract.endDate && (
                                <div className="flex items-start gap-3">
                                  <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
                                  <div>
                                    <p className="text-sm text-muted-foreground">有效期</p>
                                    <p className="font-medium">
                                      {formatDate(contract.startDate)} ~ {formatDate(contract.endDate)}
                                    </p>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* OA审批流程信息 */}
                          {(oaRaw['doc_status'] || oaRaw['node_name'] || oaRaw['当前处理人'] || oaRaw['已经处理人']) && (
                            <div className="mb-6 pt-4 border-t">
                              <h4 className="text-sm font-semibold mb-3">审批流程信息</h4>
                              <div className="grid grid-cols-2 gap-6">
                                {oaRaw['doc_status'] && (
                                  <div className="flex items-start gap-3">
                                    <AlertTriangle className="h-5 w-5 text-muted-foreground mt-0.5" />
                                    <div>
                                      <p className="text-sm text-muted-foreground">OA文档状态</p>
                                      <p className="font-medium">{oaRaw['doc_status']}</p>
                                    </div>
                                  </div>
                                )}
                                {oaRaw['node_name'] && (
                                  <div className="flex items-start gap-3">
                                    <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                                    <div>
                                      <p className="text-sm text-muted-foreground">当前审批节点</p>
                                      <p className="font-medium">{oaRaw['node_name']}</p>
                                    </div>
                                  </div>
                                )}
                                {oaRaw['handler_name'] && oaRaw['handler_name'] !== '<无>' && (
                                  <div className="flex items-start gap-3">
                                    <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                                    <div>
                                      <p className="text-sm text-muted-foreground">当前处理人</p>
                                      <p className="font-medium">{oaRaw['当前处理人'] || oaRaw['handler_name']}</p>
                                    </div>
                                  </div>
                                )}
                                {oaRaw['已经处理人'] && (
                                  <div className="flex items-start gap-3">
                                    <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                                    <div>
                                      <p className="text-sm text-muted-foreground">已处理人</p>
                                      <p className="font-medium">{oaRaw['已经处理人']}</p>
                                    </div>
                                  </div>
                                )}
                                {oaRaw['模板名称'] && (
                                  <div className="flex items-start gap-3 col-span-2">
                                    <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                                    <div>
                                      <p className="text-sm text-muted-foreground">OA流程模板</p>
                                      <p className="font-medium">{oaRaw['模板名称']}</p>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </>
                      )
                    })()}
                    
                    {/* 申请摘要 - OA合同只显示原始事由说明 */}
                    {(() => {
                      let oaSummary = ''
                      // 优先级1：从rawData['合同摘要']读取（最可靠的OA原始数据源）
                      let oaRawForSummary: Record<string, any> = {}
                      if ((contract as any).rawData) {
                        try {
                          oaRawForSummary = typeof (contract as any).rawData === 'string'
                            ? JSON.parse((contract as any).rawData)
                            : (contract as any).rawData
                        } catch {}
                      }
                      if (oaRawForSummary['合同摘要']) {
                        oaSummary = oaRawForSummary['合同摘要']
                      }
                      // 优先级2：从extracted_data.oa_original_summary
                      if (!oaSummary && contract.extractedData) {
                        try {
                          const ed = JSON.parse(contract.extractedData)
                          if (ed.oa_original_summary) oaSummary = ed.oa_original_summary
                        } catch {}
                      }
                      // 优先级3：contract.summary（但排除LLM内容和错误信息）
                      if (!oaSummary && contract.summary) {
                        const s = contract.summary
                        if (!s.startsWith('正在解析') && !s.startsWith('附件文本提取') && !s.startsWith('## ') && !s.startsWith('### ') && s !== '由AI自动解析提取') {
                          oaSummary = s
                        }
                      }
                      return oaSummary ? (
                        <div className="pt-4 border-t">
                          <h4 className="text-sm font-semibold mb-3">申请摘要</h4>
                          <div className="whitespace-pre-wrap">
                            {oaSummary}
                          </div>
                        </div>
                      ) : null
                    })()}
                  </CardContent>
                </Card>
              )}

              {/* 补充协议列表 */}
              {id && <SupplementList contractId={parseInt(id)} />}

              {/* 付款管理列表 */}
              {id && <PaymentList contractId={parseInt(id)} />}

              {/* 注意：OA合同的附件在右侧附件清单中显示，不使用ContractAttachments组件 */}
        </div>

        <div className="space-y-6">
          {/* 附件清单（OA导入的合同） */}
          {contract?.source === 'oa_import' && attachments.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>附件清单 ({attachments.length})</CardTitle>
                    <CardDescription>选择要预览或解析的附件</CardDescription>
                  </div>
                  <div>
                    <input
                      ref={uploadInputRef}
                      type="file"
                      className="hidden"
                      accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.bmp,.webp,.xls,.xlsx"
                      onChange={handleAttachmentUpload}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={uploadingAttachment}
                      onClick={() => uploadInputRef.current?.click()}
                    >
                      <Upload className="h-4 w-4 mr-1" />
                      {uploadingAttachment ? '上传中...' : '上传附件'}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {attachments.map((att) => (
                    <div
                      key={att.id}
                      className={`flex items-center justify-between p-3 border rounded cursor-pointer transition-colors ${
                        selectedAttachment?.id === att.id
                          ? 'bg-primary/10 border-primary'
                          : 'hover:bg-gray-50'
                      }`}
                      onClick={() => {
                        setSelectedAttachment(att)
                        setAttachmentError(null)
                        setIsLoadingAttachment(false)
                        handleAttachmentPreview(att)
                      }}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate flex items-center gap-2">
                            {att.file_name}
                            <Badge variant="outline" className="text-xs">OA</Badge>
                          </div>
                          <div className="text-sm text-gray-500">
                            {(att.file_size / 1024).toFixed(2)} KB
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {selectedAttachment?.id === att.id && (
                          <Badge variant="default">预览中</Badge>
                        )}
                        {att.is_primary ? (
                          <Badge variant="default" className="text-xs bg-primary">主附件</Badge>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs border-primary text-primary hover:bg-primary hover:text-white"
                            onClick={async (e) => {
                              e.stopPropagation()
                              try {
                                const token = localStorage.getItem('token')
                                const response = await fetch(`/api/v1/contracts/${contract?.id}/attachments/${att.id}/set-primary`, {
                                  method: 'PUT',
                                  headers: {
                                    'Authorization': `Bearer ${token}`
                                  }
                                })
                                if (response.ok) {
                                  // 重新加载附件列表（会自动排序主附件到最上方）
                                  loadAttachments(id!)
                                }
                              } catch (error) {
                                console.error('设置主附件失败:', error)
                              }
                            }}
                          >
                            ★ 设为主附件
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 非OA合同的附件上传入口 */}
          {contract?.source !== 'oa_import' && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>附件</CardTitle>
                  <div>
                    <input
                      ref={uploadInputRef}
                      type="file"
                      className="hidden"
                      accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.bmp,.webp,.xls,.xlsx"
                      onChange={handleAttachmentUpload}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={uploadingAttachment}
                      onClick={() => uploadInputRef.current?.click()}
                    >
                      <Upload className="h-4 w-4 mr-1" />
                      {uploadingAttachment ? '上传中...' : '上传附件'}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                  <div className="space-y-2">
                    {/* 显示合同主文件 */}
                    {contract?.filePath && (
                      <div
                        className={`flex items-center justify-between p-3 border rounded cursor-pointer transition-colors ${
                          !selectedAttachment ? 'bg-primary/10 border-primary' : 'hover:bg-gray-50'
                        }`}
                        onClick={() => {
                          setSelectedAttachment(null)
                          setAttachmentError(null)
                          setIsLoadingAttachment(false)
                        }}
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate">
                              {(() => {
                                // 优先显示上传时的原始文件名
                                if (contract.originalFilename) {
                                  return contract.originalFilename
                                }
                                const ext = contract.filePath.split('.').pop() || 'pdf'
                                const name = contract.title && contract.title !== '未识别'
                                  ? contract.title
                                  : contract.contractNumber
                                return `${name}.${ext}`
                              })()}
                            </div>
                            <div className="text-sm text-gray-500">合同主文件</div>
                          </div>
                        </div>
                        {!selectedAttachment && <Badge variant="default">预览中</Badge>}
                        {attachments.length === 0 || !attachments.some(a => a.is_primary) ? (
                          <Badge variant="default" className="text-xs bg-primary">主附件</Badge>
                        ) : null}
                      </div>
                    )}
                    {/* 显示额外附件 */}
                    {attachments.map((att) => (
                      <div
                        key={att.id}
                        className={`flex items-center justify-between p-3 border rounded cursor-pointer transition-colors ${
                          selectedAttachment?.id === att.id ? 'bg-primary/10 border-primary' : 'hover:bg-gray-50'
                        }`}
                        onClick={() => {
                          setSelectedAttachment(att)
                          setAttachmentError(null)
                          setIsLoadingAttachment(false)
                          handleAttachmentPreview(att)
                        }}
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate">{att.file_name}</div>
                            <div className="text-sm text-gray-500">{(att.file_size / 1024).toFixed(2)} KB</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {selectedAttachment?.id === att.id && <Badge variant="default">预览中</Badge>}
                          {att.is_primary ? (
                            <Badge variant="default" className="text-xs bg-primary">主附件</Badge>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-xs border-primary text-primary hover:bg-primary hover:text-white"
                              onClick={async (e) => {
                                e.stopPropagation()
                                try {
                                  const token = localStorage.getItem('token')
                                  const response = await fetch(`/api/v1/contracts/${contract?.id}/attachments/${att.id}/set-primary`, {
                                    method: 'PUT',
                                    headers: { 'Authorization': `Bearer ${token}` }
                                  })
                                  if (response.ok) loadAttachments(id!)
                                } catch (error) {
                                  console.error('设置主附件失败:', error)
                                }
                              }}
                            >
                              ★ 设为主附件
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex-1 min-w-0">
                <CardTitle className="truncate">
                  {selectedAttachment
                    ? selectedAttachment.file_name
                    : contract?.originalFilename || contract?.title || '合同预览'}
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {selectedAttachment ? '附件预览' : '合同主文件预览'}
                </p>
              </div>
              {((selectedAttachment && attachmentPreviewType === 'word') || (!selectedAttachment && mainPreviewType === 'word')) && (
                <div className="flex items-center gap-2 text-sm">
                  <button onClick={() => setWordZoom(Math.max(50, wordZoom - 10))} className="px-2 py-1 rounded border hover:bg-muted" title="缩小">−</button>
                  <span className="w-12 text-center">{wordZoom}%</span>
                  <button onClick={() => setWordZoom(Math.min(200, wordZoom + 10))} className="px-2 py-1 rounded border hover:bg-muted" title="放大">+</button>
                  <button onClick={() => setWordZoom(100)} className="px-2 py-1 rounded border hover:bg-muted text-xs" title="重置">重置</button>
                </div>
              )}
            </CardHeader>
            <CardContent>
              {contract?.fileUrl || contract?.source === 'oa_import' || selectedAttachment ? (
                <div className="space-y-4">
                  <div className="bg-muted rounded-lg overflow-auto" style={{ height: '70vh' }}>
                    {selectedAttachment && (attachmentPreviewUrl || attachmentPreviewType === 'word') ? (
                      // 附件预览
                      <>
                        {isLoadingAttachment && (
                          <div className="w-full h-full flex items-center justify-center">
                            <div className="flex flex-col items-center gap-4">
                              <div className="w-8 h-8 border-2 border-zinc-300 border-t-zinc-900 rounded-full animate-spin" />
                              <p className="text-sm text-muted-foreground font-medium">正在加载文档...</p>
                            </div>
                          </div>
                        )}
                        
                        {attachmentError && (
                          <div className="w-full h-full flex items-center justify-center">
                            <div className="text-center">
                              <AlertTriangle className="h-16 w-16 mx-auto text-destructive mb-4" />
                              <p className="text-muted-foreground mb-2">预览失败</p>
                              <p className="text-sm text-muted-foreground">{attachmentError}</p>
                            </div>
                          </div>
                        )}
                        
                        {!isLoadingAttachment && !attachmentError && (
                          <>
                            {attachmentPreviewType === 'pdf' && (
                              <iframe
                                src={attachmentPreviewUrl}
                                className="w-full h-full"
                                title="附件预览"
                              />
                            )}
                            {attachmentPreviewType === 'image' && (
                              <div className="w-full h-full flex items-center justify-center bg-black">
                                <img
                                  src={attachmentPreviewUrl}
                                  alt={selectedAttachment.file_name}
                                  className="max-w-full max-h-full object-contain"
                                />
                              </div>
                            )}
                            {attachmentPreviewType === 'word' && (
                              <div 
                                ref={wordDocxContainerRef}
                                className="docx-preview-wrapper w-full h-full overflow-auto p-4 md:p-8 bg-white"
                                style={{ zoom: `${wordZoom}%` }}
                              />
                            )}
                            {attachmentPreviewType === 'unknown' && (
                              <div className="w-full h-full flex items-center justify-center">
                                <div className="text-center">
                                  <FileText className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
                                  <p className="text-muted-foreground">不支持的文件格式</p>
                                  <p className="text-sm text-muted-foreground mt-2">
                                    请下载后查看
                                  </p>
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </>
                    ) : (previewUrl || mainPreviewType === 'word') ? (
                      // 主合同预览 - 支持PDF/Word/图片
                      <>
                        {mainPreviewType === 'pdf' && (
                          <iframe
                            src={previewUrl}
                            className="w-full h-full"
                            title="合同预览"
                          />
                        )}
                        {mainPreviewType === 'image' && (
                          <div className="w-full h-full flex items-center justify-center bg-black">
                            <img
                              src={previewUrl}
                              alt={contract?.title || '合同预览'}
                              className="max-w-full max-h-full object-contain"
                            />
                          </div>
                        )}
                        {mainPreviewType === 'word' && (
                          <div 
                            ref={mainWordContainerRef}
                            className="docx-preview-wrapper w-full h-full overflow-auto p-4 md:p-8 bg-white"
                            style={{ zoom: `${wordZoom}%` }}
                          />
                        )}
                      </>
                    ) : contract?.source === 'oa_import' ? (
                      <div className="w-full h-full flex items-center justify-center">
                        <div className="text-center">
                          <FileText className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
                          <p className="text-muted-foreground">OA导入的合同</p>
                          <p className="text-sm text-muted-foreground mt-2">
                            请从上方附件清单中选择要预览的文件
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <p className="text-muted-foreground">加载预览中...</p>
                      </div>
                    )}
                  </div>
                  
                  {contract?.source !== 'oa_import' && !selectedAttachment && (
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
                  )}
                  {selectedAttachment && (
                    <div className="flex gap-2">
                      <Button 
                        variant="outline" 
                        className="flex-1"
                        onClick={() => {
                          setSelectedAttachment(null)
                          setAttachmentPreviewUrl('')
                        }}
                      >
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        返回主合同
                      </Button>
                    </div>
                  )}
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

      {activeTab === 'payments' && (
        <Card>
          <CardHeader>
            <CardTitle>关联付款记录</CardTitle>
            <CardDescription>与此合同关联的所有付款记录</CardDescription>
          </CardHeader>
          <CardContent>
            {paymentsLoading ? (
              <div className="text-center py-8 text-muted-foreground">加载中...</div>
            ) : contractPayments.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                暂无关联的付款记录
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>付款主题</TableHead>
                    <TableHead>申请日期</TableHead>
                    <TableHead>付款金额</TableHead>
                    <TableHead>经办人</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contractPayments.map((payment) => (
                    <TableRow key={payment.id}>
                      <TableCell className="font-medium">
                        <Link to={`/payments/${payment.id}`} className="hover:underline text-primary">
                          {payment.payment_theme}
                        </Link>
                      </TableCell>
                      <TableCell>{payment.payment_date || '-'}</TableCell>
                      <TableCell>
                        {payment.amount != null ? new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(payment.amount) : '-'}
                      </TableCell>
                      <TableCell>{payment.operator || '-'}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" asChild>
                          <Link to={`/payments/${payment.id}`}>查看详情</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
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
                <select
                  id="contractType"
                  value={editForm.contractType}
                  onChange={(e) => setEditForm({...editForm, contractType: e.target.value})}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="">请选择合同类型</option>
                  {contractTypes.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                  {editForm.contractType && !contractTypes.includes(editForm.contractType) && (
                    <option value={editForm.contractType}>{editForm.contractType}</option>
                  )}
                </select>
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

      {/* 付款流程表单PDF导入弹窗 */}
      {showPaymentPdfImport && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">导入付款流程表单PDF</h2>
              <button onClick={() => { setShowPaymentPdfImport(false); setPaymentPdfFile(null); setPaymentPdfResult(null) }} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground">
              将OA系统中的付款申请表单导出为PDF，上传后系统将自动解析并创建付款记录，并自动关联到当前合同。
            </p>
            {!paymentPdfResult ? (
              <>
                <div
                  className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
                  onClick={() => paymentPdfInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    const f = e.dataTransfer.files[0]
                    if (f?.name.toLowerCase().endsWith('.pdf')) setPaymentPdfFile(f)
                  }}
                >
                  <FileText className="h-10 w-10 mx-auto text-gray-400 mb-2" />
                  {paymentPdfFile ? (
                    <p className="text-sm font-medium text-blue-600">{paymentPdfFile.name}</p>
                  ) : (
                    <p className="text-sm text-gray-500">点击或拖拽PDF文件到此处</p>
                  )}
                  <input ref={paymentPdfInputRef} type="file" accept=".pdf" className="hidden"
                    onChange={(e) => setPaymentPdfFile(e.target.files?.[0] || null)} />
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => { setShowPaymentPdfImport(false); setPaymentPdfFile(null) }}>取消</Button>
                  <Button onClick={async () => {
                    if (!paymentPdfFile) return
                    setImportingPaymentPdf(true)
                    try {
                      const result = await paymentManagementApi.importPdf(paymentPdfFile)
                      if (result.error) {
                        setPaymentPdfResult({ success: false, message: result.error })
                      } else {
                        // 如果解析出的合同编号与当前合同不匹配，手动关联
                        const paymentId = result.data?.payment_id
                        if (paymentId && !result.data?.auto_linked && id) {
                          await paymentManagementApi.linkContract(paymentId, Number(id))
                        }
                        setPaymentPdfResult({ success: true, message: '导入成功', detail: '付款记录已创建并关联到当前合同' })
                        fetchContractPayments()
                      }
                    } catch (e: any) {
                      setPaymentPdfResult({ success: false, message: e.message || '导入失败' })
                    } finally {
                      setImportingPaymentPdf(false)
                    }
                  }} disabled={!paymentPdfFile || importingPaymentPdf}>
                    {importingPaymentPdf ? '解析中...' : '开始导入'}
                  </Button>
                </div>
              </>
            ) : (
              <div className="space-y-4">
                <div className={`flex items-start gap-3 p-4 rounded-lg ${paymentPdfResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
                  <div>
                    <p className={`font-medium ${paymentPdfResult.success ? 'text-green-800' : 'text-red-800'}`}>{paymentPdfResult.message}</p>
                    {paymentPdfResult.detail && <p className="text-sm mt-1 text-gray-600">{paymentPdfResult.detail}</p>}
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => { setShowPaymentPdfImport(false); setPaymentPdfFile(null); setPaymentPdfResult(null) }}>关闭</Button>
                  {paymentPdfResult.success && (
                    <Button onClick={() => { setPaymentPdfFile(null); setPaymentPdfResult(null) }}>继续导入</Button>
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
