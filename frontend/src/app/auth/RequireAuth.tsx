/* 路由守卫：登录校验 + 权限校验。
 *
 * 用法：在 feature manifest 的路由 element 外包一层，或由装配层按 meta 自动包裹。
 *   <Route element={<RequireAuth permission="order:read"><OrderPage/></RequireAuth>} />
 *
 * - 未登录（requiresAuth 且 isAuthenticated()=false）→ 重定向到 /login（可注入）
 * - 无权限 → 展示 403 提示
 */

import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

import { isAuthenticated, hasPermission } from '@/services/auth/authState'

interface RequireAuthProps {
  children: ReactNode
  permission?: string
  /** 未登录跳转地址（默认 /login） */
  redirectTo?: string
}

/** 403 兜底：无权限提示（可用 children fallback 替换） */
function Forbidden() {
  return (
    <div style={{ textAlign: 'center', padding: '80px 0' }}>
      <h2>403</h2>
      <p>无权访问该页面</p>
    </div>
  )
}

export default function RequireAuth({
  children,
  permission,
  redirectTo = '/login',
}: RequireAuthProps) {
  const location = useLocation()

  if (!isAuthenticated()) {
    // 保留来源，登录后可回跳
    return <Navigate to={redirectTo} state={{ from: location.pathname }} replace />
  }

  if (permission && !hasPermission(permission)) {
    return <Forbidden />
  }

  return <>{children}</>
}
