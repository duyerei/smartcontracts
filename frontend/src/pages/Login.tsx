import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { FileText, Lock, QrCode, User } from 'lucide-react'

export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [dingtalkLoading, setDingtalkLoading] = useState(false)
  const { login, getDingtalkLoginUrl } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) {
      setError('请输入用户名和密码')
      return
    }
    setLoading(true)
    setError('')
    const err = await login(username.trim(), password)
    setLoading(false)
    if (err) {
      setError(err)
    } else {
      navigate('/', { replace: true })
    }
  }

  const handleDingtalkLogin = async () => {
    setDingtalkLoading(true)
    setError('')
    const result = await getDingtalkLoginUrl()
    setDingtalkLoading(false)
    if (result.error || !result.loginUrl) {
      setError(result.error || '钉钉扫码登录暂不可用')
      return
    }
    window.location.href = result.loginUrl
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
            <FileText className="h-7 w-7 text-primary" />
          </div>
          <CardTitle className="text-xl font-bold">AI智能合同管理系统</CardTitle>
          <p className="text-sm text-muted-foreground mt-1">请登录以继续使用</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="username">用户名</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  className="pl-9"
                  autoFocus
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="password">密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  className="pl-9"
                />
              </div>
            </div>
            {error && (
              <div className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? '登录中...' : '登 录'}
            </Button>
            <div className="relative py-1 text-center text-xs text-muted-foreground">
              <span className="bg-card px-2">或</span>
            </div>
            <Button type="button" variant="outline" className="w-full" disabled={dingtalkLoading} onClick={handleDingtalkLogin}>
              <QrCode className="mr-2 h-4 w-4" />
              {dingtalkLoading ? '正在打开钉钉...' : '钉钉扫码登录'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
