/* 框架路由扩展类型（共享层，供 app/hooks/features 使用）。
 *
 * RouteMeta / AppRouteObject 属于框架级路由约定，不属于任何业务 feature，
 * 因此放在共享 types 目录；features 通过自身 types.ts 引用。
 */

import type { RouteObject } from 'react-router-dom'

/** 路由元信息：驱动守卫、文档标题、菜单联动 */
export interface RouteMeta {
  /** 页面标题（用于 document.title，可选） */
  title?: string
  /** 需要已登录才能访问（默认 false） */
  requiresAuth?: boolean
  /** 需要的权限标识；不设则不校验权限 */
  permission?: string
  /** 是否在菜单中隐藏 */
  hideInMenu?: boolean
}

/** 带元信息的路由对象 */
export interface AppRouteObject extends Omit<RouteObject, 'children'> {
  meta?: RouteMeta
  children?: AppRouteObject[]
}
