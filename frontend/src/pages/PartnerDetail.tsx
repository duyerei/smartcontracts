import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, Building2, Phone, User, MapPin, Landmark, CreditCard,
  FileText, Upload, Trash2, Download, Edit, Save, X, StickyNote
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { partnerApi, PartnerRecord } from '@/lib/api'

const formatAmount = (v?: number | null) =>
  v == null ? '-' : new Intl.NumberFormat('zh-CN', { style: 'decimal', minimumFractionDigits: 2 }).format(v)

export function PartnerDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [partner, setPartner] = useState<PartnerRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<Partial<PartnerRecord>>({})

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const res = await partnerApi.get(Number(id))
      if (res.data) {
        setPartner(res.data)
        setForm(res.data)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const handleSave = async () => {
    if (!id) return
    setSaving(true)
    try {
      await partnerApi.update(Number(id), form)
      await load()
      setIsEditing(false)
    } catch (e: any) {
      alert(e.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!id || !confirm('确定删除该合作伙伴？')) return
    await partnerApi.delete(Number(id))
    navigate('/partners')
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !id) return
    setUploading(true)
    try {
      await partnerApi.uploadAttachment(Number(id), file)
      await load()
    } catch (err: any) {
      alert(err.message || '上传失败')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDeleteAttachment = async (attId: number) => {
    if (!id || !confirm('确定删除该附件？')) return
    await partnerApi.deleteAttachment(Number(id), attId)
    await load()
  }

  if (loading) return <div className="py-8 text-center text-muted-foreground">加载中...</div>
  if (!partner) return <div className="py-8 text-center text-muted-foreground">合作伙伴不存在</div>

  return (
    <div className="space-y-6">
      {/* 顶部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/partners')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Building2 className="h-6 w-6 text-primary" />
              {partner.name}
            </h1>
            <p className="text-sm text-muted-foreground">合作伙伴详情</p>
          </div>
        </div>
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={() => { setIsEditing(false); setForm(partner) }}>
                <X className="h-4 w-4 mr-2" />取消
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                <Save className="h-4 w-4 mr-2" />{saving ? '保存中...' : '保存'}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                <Edit className="h-4 w-4 mr-2" />编辑
              </Button>
              <Button variant="destructive" onClick={handleDelete}>
                <Trash2 className="h-4 w-4 mr-2" />删除
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：基本信息 */}
        <div className="lg:col-span-1 space-y-6">
          <Card>
            <CardHeader><CardTitle>基本信息</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {isEditing ? (
                <>
                  {[
                    { key: 'name', label: '名称', icon: Building2 },
                    { key: 'contact_name', label: '联系人', icon: User },
                    { key: 'contact_phone', label: '联系电话', icon: Phone },
                    { key: 'address', label: '地址', icon: MapPin },
                    { key: 'bank_name', label: '开户行', icon: Landmark },
                    { key: 'bank_account', label: '银行账号', icon: CreditCard },
                  ].map(({ key, label }) => (
                    <div key={key} className="space-y-1">
                      <Label>{label}</Label>
                      <Input
                        value={(form as any)[key] || ''}
                        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                        placeholder={label}
                      />
                    </div>
                  ))}
                  <div className="space-y-1">
                    <Label>备注</Label>
                    <textarea
                      className="w-full border rounded-md px-3 py-2 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                      value={form.notes || ''}
                      onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                      placeholder="备注信息"
                    />
                  </div>
                </>
              ) : (
                <div className="space-y-3">
                  {[
                    { icon: User, label: '联系人', value: partner.contact_name },
                    { icon: Phone, label: '联系电话', value: partner.contact_phone },
                    { icon: MapPin, label: '地址', value: partner.address },
                    { icon: Landmark, label: '开户行', value: partner.bank_name },
                    { icon: CreditCard, label: '银行账号', value: partner.bank_account },
                  ].map(({ icon: Icon, label, value }) => (
                    <div key={label} className="flex items-start gap-3">
                      <Icon className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="text-sm font-medium">{value || '-'}</p>
                      </div>
                    </div>
                  ))}
                  {partner.notes && (
                    <div className="flex items-start gap-3">
                      <StickyNote className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-xs text-muted-foreground">备注</p>
                        <p className="text-sm whitespace-pre-wrap">{partner.notes}</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 附件资料 */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>附件资料</CardTitle>
                <div>
                  <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} />
                  <Button variant="outline" size="sm" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
                    <Upload className="h-4 w-4 mr-1" />
                    {uploading ? '上传中...' : '上传'}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {!partner.attachments?.length ? (
                <p className="text-sm text-muted-foreground text-center py-4">暂无附件</p>
              ) : (
                <div className="space-y-2">
                  {partner.attachments.map(att => (
                    <div key={att.id} className="flex items-center justify-between p-2 border rounded">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        <span className="text-sm truncate">{att.file_name}</span>
                      </div>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon">
                          <a href={`/api/v1/partners/${id}/attachments/${att.id}/download`} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center w-full h-full">
                            <Download className="h-4 w-4" />
                          </a>
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDeleteAttachment(att.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 右侧：关联合同 */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>关联合同 ({partner.contracts?.length ?? 0})</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {!partner.contracts?.length ? (
                <p className="text-sm text-muted-foreground text-center py-8">暂无关联合同</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>合同名称</TableHead>
                      <TableHead className="w-[130px]">合同编号</TableHead>
                      <TableHead className="w-[100px]">类型</TableHead>
                      <TableHead className="w-[120px]">金额</TableHead>
                      <TableHead className="w-[80px]">状态</TableHead>
                      <TableHead className="w-[110px]">到期日</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {partner.contracts.map(c => (
                      <TableRow key={c.id} className="cursor-pointer hover:bg-muted/50">
                        <TableCell>
                          <Link to={`/contracts/${c.id}`} className="text-primary hover:underline font-medium">
                            {c.title || '-'}
                          </Link>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{c.contract_number || '-'}</TableCell>
                        <TableCell>
                          {c.contract_type ? <Badge variant="outline">{c.contract_type}</Badge> : '-'}
                        </TableCell>
                        <TableCell className="text-sm">{formatAmount(c.amount)}</TableCell>
                        <TableCell>
                          {c.status ? (
                            <Badge variant={
                              c.status === '合同履行中' ? 'default' :
                              c.status === '即将到期' ? 'destructive' :
                              'secondary'
                            }>{c.status}</Badge>
                          ) : '-'}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{c.end_date || '-'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
