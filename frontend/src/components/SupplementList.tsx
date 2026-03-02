import { useState, useEffect } from 'react'
import { Upload, FileText, Trash2, Edit } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface Supplement {
  id: number
  contract_id: number
  title: string
  signed_date: string | null
  amount: number | null
  file_path: string
  file_size: number
  created_at: string
}

interface SupplementListProps {
  contractId: number
}

export function SupplementList({ contractId }: SupplementListProps) {
  const [supplements, setSupplements] = useState<Supplement[]>([])
  const [loading, setLoading] = useState(false)
  const [showUploadDialog, setShowUploadDialog] = useState(false)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [extractedTitle, setExtractedTitle] = useState('')
  const [editingSupplement, setEditingSupplement] = useState<Supplement | null>(null)
  const [editForm, setEditForm] = useState({
    title: '',
    signedDate: '',
    amount: ''
  })

  // 判断是否超时（创建时间超过2分钟）
  const isRecognitionTimeout = (createdAt: string) => {
    const created = new Date(createdAt).getTime()
    const now = Date.now()
    const twoMinutes = 2 * 60 * 1000
    return now - created > twoMinutes
  }

  useEffect(() => {
    loadSupplements()
    
    // 设置定时刷新，每5秒检查一次是否有更新
    const interval = setInterval(() => {
      loadSupplements()
    }, 5000)
    
    return () => clearInterval(interval)
  }, [contractId])

  const loadSupplements = async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/supplements/${contractId}/list`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setSupplements(data.supplements || [])
      }
    } catch (error) {
      console.error('加载补充协议失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // 验证文件类型
      if (!file.name.match(/\.(pdf|doc|docx)$/i)) {
        alert('仅支持 PDF、DOC、DOCX 格式的文件')
        return
      }
      
      // 验证文件大小（50MB）
      if (file.size > 50 * 1024 * 1024) {
        alert('文件大小不能超过 50MB')
        return
      }
      
      setSelectedFile(file)
      setShowUploadDialog(false)
      
      // 自动识别文件名和日期
      await analyzeFile(file)
    }
  }

  const analyzeFile = async (file: File) => {
    setAnalyzing(true)
    try {
      const token = localStorage.getItem('token')
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`/api/v1/supplements/${contractId}/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (response.ok) {
        const data = await response.json()
        setExtractedTitle(data.title || file.name.replace(/\.[^/.]+$/, ''))
        setShowConfirmDialog(true)
      } else {
        // 如果分析失败，使用文件名作为标题
        setExtractedTitle(file.name.replace(/\.[^/.]+$/, ''))
        setShowConfirmDialog(true)
      }
    } catch (error) {
      console.error('文件分析失败:', error)
      // 使用文件名作为标题
      setExtractedTitle(file.name.replace(/\.[^/.]+$/, ''))
      setShowConfirmDialog(true)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleConfirmUpload = async () => {
    if (!selectedFile) return

    setUploading(true)
    try {
      const token = localStorage.getItem('token')
      const formData = new FormData()
      formData.append('file', selectedFile)
      if (extractedTitle) formData.append('title', extractedTitle)

      const response = await fetch(`/api/v1/supplements/${contractId}/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (response.ok) {
        setShowConfirmDialog(false)
        setSelectedFile(null)
        setExtractedTitle('')
        loadSupplements()
      } else {
        const error = await response.json()
        alert(error.detail || '上传失败')
      }
    } catch (error) {
      console.error('上传失败:', error)
      alert('上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleCancelUpload = () => {
    setShowConfirmDialog(false)
    setSelectedFile(null)
    setExtractedTitle('')
    setShowUploadDialog(true)
  }

  const handlePreview = async (supplement: Supplement) => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/supplements/${supplement.id}/download`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        
        // 在新窗口打开
        const newWindow = window.open(url, '_blank')
        
        // 清理URL（延迟清理，确保文件已加载）
        if (newWindow) {
          setTimeout(() => {
            window.URL.revokeObjectURL(url)
          }, 1000)
        }
      } else {
        const error = await response.json()
        alert(error.detail || '预览失败')
      }
    } catch (error) {
      console.error('预览失败:', error)
      alert('预览失败，请检查网络连接')
    }
  }

  const handleDelete = async (supplementId: number) => {
    if (!confirm('确定要删除这份补充协议吗？')) return

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/supplements/${supplementId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        loadSupplements()
      } else {
        alert('删除失败')
      }
    } catch (error) {
      console.error('删除失败:', error)
      alert('删除失败')
    }
  }

  const handleEdit = (supplement: Supplement) => {
    setEditingSupplement(supplement)
    setEditForm({
      title: supplement.title,
      signedDate: supplement.signed_date ? supplement.signed_date.split('T')[0] : '',
      amount: supplement.amount ? String(supplement.amount) : ''
    })
    setShowEditDialog(true)
  }

  const handleSaveEdit = async () => {
    if (!editingSupplement) return

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/supplements/${editingSupplement.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: editForm.title,
          signed_date: editForm.signedDate || null,
          amount: editForm.amount ? parseFloat(editForm.amount) : null
        })
      })

      if (response.ok) {
        setShowEditDialog(false)
        setEditingSupplement(null)
        loadSupplements()
      } else {
        alert('保存失败')
      }
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败')
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const formatAmount = (amount: number | null) => {
    if (!amount) return '-'
    return new Intl.NumberFormat('zh-CN', { 
      style: 'currency', 
      currency: 'CNY' 
    }).format(amount)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    return dateStr.split('T')[0]
  }

  const getFileExtension = (filePath: string) => {
    const match = filePath.match(/\.[^.]+$/)
    return match ? match[0] : ''
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>补充协议</CardTitle>
        <Button variant="outline" size="sm" onClick={() => setShowUploadDialog(true)}>
          <Upload className="h-4 w-4 mr-2" />
          上传补充协议
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-muted-foreground text-center py-4">加载中...</p>
        ) : supplements.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">暂无补充协议</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">补充协议</th>
                  <th className="text-left px-4 py-3 font-medium">签约时间</th>
                  <th className="text-left px-4 py-3 font-medium">金额</th>
                  <th className="text-right px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {supplements.map((supplement, index) => (
                  <tr 
                    key={supplement.id}
                    className={`border-t hover:bg-muted/50 transition-colors ${
                      index % 2 === 0 ? 'bg-background' : 'bg-muted/20'
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        <button
                          onClick={() => handlePreview(supplement)}
                          className="font-medium text-primary hover:underline text-left"
                        >
                          {supplement.title}{getFileExtension(supplement.file_path)}
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {supplement.signed_date ? (
                        formatDate(supplement.signed_date)
                      ) : isRecognitionTimeout(supplement.created_at) ? (
                        <span className="text-xs text-muted-foreground">未识别</span>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">识别中...</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {supplement.amount ? (
                        formatAmount(supplement.amount)
                      ) : isRecognitionTimeout(supplement.created_at) ? (
                        <span className="text-xs text-muted-foreground">未识别</span>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">识别中...</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEdit(supplement)}
                          title="编辑"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(supplement.id)}
                          title="删除"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      {/* 文件选择对话框 */}
      <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>上传补充协议</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="file">选择文件</Label>
              <Input
                id="file"
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={handleFileSelect}
              />
              <p className="text-xs text-muted-foreground">
                支持 PDF、DOC、DOCX 格式，最大 50MB
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowUploadDialog(false)}>
              取消
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 分析中对话框 */}
      <Dialog open={analyzing} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>正在分析文件...</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-center py-6">
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">AI正在识别文件信息</p>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* 确认上传对话框 */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认上传补充协议</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="rounded-lg bg-muted p-4 space-y-3">
              <div className="flex items-start gap-3">
                <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">文件名</p>
                  <p className="font-medium">{selectedFile?.name}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {selectedFile && formatFileSize(selectedFile.size)}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">协议名称</p>
                  <Input
                    value={extractedTitle}
                    onChange={(e) => setExtractedTitle(e.target.value)}
                    placeholder="请输入协议名称"
                    className="mt-1"
                  />
                </div>
              </div>
            </div>
            <div className="rounded-lg bg-blue-50 dark:bg-blue-950 p-3 text-sm">
              <p className="text-blue-900 dark:text-blue-100">
                确认要在当前合同下创建此补充协议吗？
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCancelUpload} disabled={uploading}>
              取消
            </Button>
            <Button onClick={handleConfirmUpload} disabled={uploading || !extractedTitle}>
              {uploading ? '上传中...' : '确认上传'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* 编辑对话框 */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑补充协议</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-title">协议名称</Label>
              <Input
                id="edit-title"
                value={editForm.title}
                onChange={(e) => setEditForm({...editForm, title: e.target.value})}
                placeholder="请输入协议名称"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-signedDate">签订时间</Label>
              <Input
                id="edit-signedDate"
                type="date"
                value={editForm.signedDate}
                onChange={(e) => setEditForm({...editForm, signedDate: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-amount">金额</Label>
              <Input
                id="edit-amount"
                type="number"
                value={editForm.amount}
                onChange={(e) => setEditForm({...editForm, amount: e.target.value})}
                placeholder="请输入金额"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              取消
            </Button>
            <Button onClick={handleSaveEdit}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
