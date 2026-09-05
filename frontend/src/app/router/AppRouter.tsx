import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import type { RouteObject } from 'react-router-dom'
import { cloneElement, isValidElement } from 'react'

import AppLayout from '@/app/layout/AppLayout'
import RequireAuth from '@/app/auth/RequireAuth'
import { getFeatureRoutes } from '@/features/registry'
import type { AppRouteObject } from '@/features/types'

/** 递归为声明了 requiresAuth/permission 的路由包裹 RequireAuth 守卫，并把 meta 挂到 handle */
function withGuards(routes: AppRouteObject[]): RouteObject[] {
  return routes.map((route): RouteObject => {
    const meta = route.meta
    const hasGuard = Boolean(meta?.requiresAuth || meta?.permission)

    // 剥离框架扩展字段 meta；react-router 本身是 index/non-index union，
    // 结构上除 meta 外完全兼容 RouteObject，此处用断言规避 union 推导限制。
    const { meta: _meta, children, ...rest } = route

    const guarded: RouteObject = {
      ...rest,
      // meta 通过 handle 透传给 useMatches（react-router 原生扩展位）
      handle: meta ? { meta } : undefined,
      children: children ? withGuards(children) : undefined,
    } as RouteObject

    if (hasGuard && isValidElement(guarded.element)) {
      guarded.element = (
        <RequireAuth permission={_meta?.permission}>{cloneElement(guarded.element)}</RequireAuth>
      )
    }
    return guarded
  })
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: withGuards(getFeatureRoutes()),
  },
])

export default function AppRouter() {
  return <RouterProvider router={router} />
}
