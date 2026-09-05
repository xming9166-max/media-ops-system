/* Home feature manifest.
 *
 * 作为框架示例 feature，演示如何向框架注册路由与菜单。
 * 页面组件使用 React.lazy 懒加载，配合装配层 Suspense 实现按路由代码分割。
 */

import { lazy } from 'react'

import type { FeatureManifest } from '../types'

const HomePage = lazy(() => import('@/pages/HomePage'))

const manifest: FeatureManifest = {
  id: 'home',
  routes: [
    {
      index: true,
      element: <HomePage />,
      meta: { title: '首页' },
    },
  ],
  menu: [
    {
      key: 'home',
      label: '首页',
      path: '/',
    },
  ],
}

export default manifest
