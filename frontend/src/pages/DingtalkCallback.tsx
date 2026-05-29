import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'

export function DingtalkCallback() {
  const [searchParams] = useSearchParams()
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { loginWithDingtalkCode } = useAuth()
  const handledRef = useRef(false)

  useEffect(() => {
    if (handledRef.current) return
    handledRef.current = true

    const authCode = searchParams.get('authCode') || searchParams.get('code') || ''
    const state = searchParams.get('state') || ''
    const dingtalkError = searchParams.get('error') || ''

    if (dingtalkError) {
      setError('钉钉授权已取消或失败，请重新扫码')
      return
    }
    if (!authCode || !state) {
      setError('钉钉登录参数不完整，请重新扫码')
      return
    }

    loginWithDingtalkCode(authCode, state).then((err) => {
      if (err) {
        setError(err.includes('未绑定') ? '钉钉账号未授权登录，请联系管理员授权' : err)
        return
      }
      navigate('/', { replace: true })
    })
  }, [loginWithDingtalkCode, navigate, searchParams])

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center pb-2">
          <CardTitle className="text-xl font-bold">钉钉扫码登录</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            {error ? '登录未完成' : '正在确认钉钉身份...'}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? (
            <>
              <div className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
              <Button className="w-full" onClick={() => navigate('/login', { replace: true })}>
                返回登录页
              </Button>
            </>
          ) : (
            <div className="py-6 text-center text-sm text-muted-foreground">请稍候</div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
