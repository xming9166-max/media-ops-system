/* Feature manifest 类型定义。
 *
 * 每个 feature 通过 manifest 向框架注册路由、菜单等扩展点，
 * 避免直接修改 app 装配层。路由框架类型（RouteMeta/AppRouteObject）在共享层 src/types/router.ts。
 */

import type { AppRouteObject } from '@/types/router'

export type { AppRouteObject, RouteMeta } from '@/types/router'

export interface FeatureManifest {
  /* feature 唯一标识，建议与目录名一致 */
  id: string
  /* 路由配置 */
  routes?: AppRouteObject[]
  /* 菜单项（后续可扩展） */
  menu?: MenuItem[]
}

export interface MenuItem {
  key: string
  label: string
  path?: string
  icon?: string
  children?: MenuItem[]
}
