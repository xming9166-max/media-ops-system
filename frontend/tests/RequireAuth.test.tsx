import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import RequireAuth from '@/app/auth/RequireAuth'
import { setAuthStateSource } from '@/services/auth/authState'
import { clearAccessToken, setAccessToken } from '@/services/http/tokenStore'

function renderAt(path: string, permission?: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/protected"
          element={
            <RequireAuth permission={permission}>
              <div>受保护内容</div>
            </RequireAuth>
          }
        />
        <Route path="/login" element={<div>登录页</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

// 默认鉴权源：与生产一致（有 token 即已登录、权限放行）
const defaultSource = {
  isAuthenticated: () => Boolean(localStorage.getItem('access_token')),
  hasPermission: () => true,
}

beforeEach(() => {
  clearAccessToken()
  setAuthStateSource(defaultSource)
})

describe('RequireAuth 守卫', () => {
  it('未登录时跳转到 /login', async () => {
    renderAt('/protected')
    expect(await screen.findByText('登录页')).toBeInTheDocument()
    expect(screen.queryByText('受保护内容')).not.toBeInTheDocument()
  })

  it('已登录（有 token）且无需权限时放行', async () => {
    setAccessToken('token-abc')
    renderAt('/protected')
    expect(await screen.findByText('受保护内容')).toBeInTheDocument()
  })

  it('已登录但缺权限时展示 403', async () => {
    setAccessToken('token-abc')
    setAuthStateSource({
      isAuthenticated: () => true,
      hasPermission: (p) => p === 'allowed',
    })
    renderAt('/protected', 'denied')
    expect(await screen.findByText('403')).toBeInTheDocument()
    expect(screen.queryByText('受保护内容')).not.toBeInTheDocument()
  })
})
