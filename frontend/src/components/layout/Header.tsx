import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, User, LogOut, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/contexts/AuthContext'

export function Header() {
  const { user, logout, changePassword } = useAuth()
  const navigate = useNavigate()
  const roleSummary = user?.roles?.map((item) => item.name).join(' / ')
  const [showPasswordDialog, setShowPasswordDialog] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const resetPasswordDialog = () => {
    setOldPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setPasswordError('')
    setPasswordSaving(false)
  }

  const handleOpenPasswordDialog = () => {
    resetPasswordDialog()
    setShowPasswordDialog(true)
  }

  const handleChangePassword = async () => {
    if (!oldPassword.trim()) {
      setPasswordError('请输入当前密码')
      return
    }
    if (!newPassword.trim()) {
      setPasswordError('请输入新密码')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('两次输入的新密码不一致')
      return
    }

    setPasswordSaving(true)
    setPasswordError('')
    const error = await changePassword(oldPassword, newPassword)
    setPasswordSaving(false)

    if (error) {
      setPasswordError(error)
      return
    }

    resetPasswordDialog()
    setShowPasswordDialog(false)
    window.alert('密码修改成功，请使用新密码登录。')
  }

  return (
    <>
      <header className="h-16 border-b bg-card px-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold">AI智能合同管理系统</h2>
        </div>
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon">
            <Bell className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-2 border-l pl-4">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                <User className="h-4 w-4 text-primary-foreground" />
              </div>
              <div className="text-sm">
                <p className="font-medium">{user?.real_name || user?.username || '用户'}</p>
                <p className="text-xs text-muted-foreground">
                  {roleSummary || (user?.role === 'admin' ? '管理员' : '普通用户')}
                  {(user?.primary_org_name || user?.department) ? ` · ${user?.primary_org_name || user?.department}` : ''}
                </p>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={handleOpenPasswordDialog} title="修改密码">
              <KeyRound className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={handleLogout} title="退出登录">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <Dialog open={showPasswordDialog} onOpenChange={(open) => {
        setShowPasswordDialog(open)
        if (!open) {
          resetPasswordDialog()
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>修改密码</DialogTitle>
            <DialogDescription>请输入当前密码，并设置新的登录密码。</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="old-password">当前密码</Label>
              <Input
                id="old-password"
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                placeholder="请输入当前密码"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">新密码</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="至少8位，含大小写字母、数字和特殊字符"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">确认新密码</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="请再次输入新密码"
              />
            </div>
            {passwordError && <div className="text-sm text-destructive">{passwordError}</div>}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPasswordDialog(false)}>
              取消
            </Button>
            <Button onClick={handleChangePassword} disabled={passwordSaving}>
              {passwordSaving ? '保存中...' : '确认修改'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
