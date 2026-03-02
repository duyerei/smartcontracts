import { useState, useEffect } from 'react'
import { Upload, FileText, Trash2, Edit, Image } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface Payment {
  id: number
  contract_id: number
  description: string
  payment_date: string | null
  amount: number | null
  file_path: string
  file_size: number
  created_at: string
}

interface PaymentListProps {
  contractId: number
}

export function PaymentList({ contractId }: PaymentListProps) {
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(false)
  const [showUploadDialog, setShowUploadDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [editingPayment, setEditingPayment] = useState<Payment | null>(null)
  const [editForm, setEditForm] = useState({
    description: '',
    paymentDate: '',
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
    loadPayments()
    
    // 设置定时刷新，每5秒检查一次是否有更新
    const interval = setInterval(() => {
      loadPayments()
    }, 5000)
    
    return () => clearInterval(interval)
  }, [contractId])

  const loadPayments = async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/payments/${contractId}/list`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setPayments(data.payments || [])
      }
    } catch (error) {
      console.error('加载付款记录失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // 验证文件类型
      if (!file.name.match(/\.(pdf|jpg|jpeg|png|doc|docx)$/i)) {
        alert('仅支持 PDF、图片、DOC、DOCX 格式的文件')
        return
      }
      
      // 验证文件大小（50MB）
      if (file.size > 50 * 1024 * 1024) {
        alert('文件大小不能超过 50MB')
        return
      }
      
      handleUpload(file)
    }
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    setShowUploadDialog(false)
    
    try {
      const token = localStorage.getItem('token')
      const formData = new FormData()
      formData.append('file', file)
      formData.append('description', file.name)

      const response = await fetch(`/api/v1/payments/${contractId}/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (response.ok) {
        loadPayments()
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

  const handlePreview = async (payment: Payment) => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/payments/${payment.id}/download`, {
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

  const handleDelete = async (paymentId: number) => {
    if (!confirm('确定要删除这条付款记录吗？')) return

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/payments/${paymentId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        loadPayments()
      } else {
        alert('删除失败')
      }
    } catch (error) {
      console.error('删除失败:', error)
      alert('删除失败')
    }
  }

  const handleEdit = (payment: Payment) => {
    setEditingPayment(payment)
    setEditForm({
      description: payment.description,
      paymentDate: payment.payment_date ? payment.payment_date.split('T')[0] : '',
      amount: payment.amount ? String(payment.amount) : ''
    })
    setShowEditDialog(true)
  }

  const handleSaveEdit = async () => {
    if (!editingPayment) return

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/payments/${editingPayment.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          description: editForm.description,
          payment_date: editForm.paymentDate || null,
          amount: editForm.amount ? parseFloat(editForm.amount) : null
        })
      })

      if (response.ok) {
        setShowEditDialog(false)
        setEditingPayment(null)
        loadPayments()
      } else {
        alert('保存失败')
      }
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败')
    }
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

  const getFileIcon = (filePath: string) => {
    const ext = filePath.split('.').pop()?.toLowerCase()
    if (['jpg', 'jpeg', 'png'].includes(ext || '')) {
      return <Image className="h-4 w-4 text-muted-foreground flex-shrink-0" />
    }
    return <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
  }

  const getFileExtension = (filePath: string) => {
    const match = filePath.match(/\.[^.]+$/)
    return match ? match[0] : ''
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>付款管理</CardTitle>
        <Button variant="outline" size="sm" onClick={() => setShowUploadDialog(true)}>
          <Upload className="h-4 w-4 mr-2" />
          上传付款凭证
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-muted-foreground text-center py-4">加载中...</p>
        ) : payments.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">暂无付款记录</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">付款资料</th>
                  <th className="text-left px-4 py-3 font-medium">付款时间</th>
                  <th className="text-left px-4 py-3 font-medium">付款金额</th>
                  <th className="text-right px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((payment, index) => (
                  <tr 
                    key={payment.id}
                    className={`border-t hover:bg-muted/50 transition-colors ${
                      index % 2 === 0 ? 'bg-background' : 'bg-muted/20'
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {getFileIcon(payment.file_path)}
                        <button
                          onClick={() => handlePreview(payment)}
                          className="font-medium text-primary hover:underline text-left"
                        >
                          {payment.description}{getFileExtension(payment.file_path)}
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {payment.payment_date ? (
                        formatDate(payment.payment_date)
                      ) : isRecognitionTimeout(payment.created_at) ? (
                        <span className="text-xs text-muted-foreground">未识别</span>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">识别中...</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {payment.amount ? (
                        formatAmount(payment.amount)
                      ) : isRecognitionTimeout(payment.created_at) ? (
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
                          onClick={() => handleEdit(payment)}
                          title="编辑"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(payment.id)}
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
            <DialogTitle>上传付款凭证</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="file">选择文件</Label>
              <Input
                id="file"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                onChange={handleFileSelect}
              />
              <p className="text-xs text-muted-foreground">
                支持 PDF、图片、DOC、DOCX 格式，最大 50MB
              </p>
              <p className="text-xs text-blue-600">
                上传后系统将自动识别付款时间和金额
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

      {/* 上传中对话框 */}
      <Dialog open={uploading} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>正在上传...</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-center py-6">
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">AI正在识别付款信息</p>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* 编辑对话框 */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑付款记录</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-description">付款说明</Label>
              <Input
                id="edit-description"
                value={editForm.description}
                onChange={(e) => setEditForm({...editForm, description: e.target.value})}
                placeholder="请输入付款说明"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-paymentDate">付款时间</Label>
              <Input
                id="edit-paymentDate"
                type="date"
                value={editForm.paymentDate}
                onChange={(e) => setEditForm({...editForm, paymentDate: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-amount">付款金额</Label>
              <Input
                id="edit-amount"
                type="number"
                value={editForm.amount}
                onChange={(e) => setEditForm({...editForm, amount: e.target.value})}
                placeholder="请输入付款金额"
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
