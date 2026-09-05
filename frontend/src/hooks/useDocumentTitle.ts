/* useDocumentTitle：按当前路由 meta.title 设置 document.title。
 *
 * 需在 RouterProvider 内部使用（依赖 useMatches），由 AppLayout 调用。
 * meta 由装配层（AppRouter.withGuards）挂到路由 handle 上，这里读取。
 * 未匹配到 title 时回退到应用名。
 */

import { useEffect } from 'react'
import { useMatches } from 'react-router-dom'

import { APP } from '@/constants'
import type { RouteMeta } from '@/types/router'

interface HandleWithMeta {
  meta?: RouteMeta
}

export function useDocumentTitle(): void {
  const matches = useMatches()

  useEffect(() => {
    // 取最深一层匹配路由的 meta.title
    const deepest = matches[matches.length - 1]
    const meta = (deepest?.handle as HandleWithMeta | undefined)?.meta
    const title = meta?.title
    document.title = title ? `${title} - ${APP.NAME}` : APP.NAME
  }, [matches])
}
