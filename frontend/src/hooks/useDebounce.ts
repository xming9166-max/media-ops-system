/* useDebounce：防抖值 Hook。
 *
 * 典型场景：搜索框输入 → 延迟触发请求，避免每次敲键都发请求。
 */

import { useEffect, useState } from 'react'

export function useDebounce<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
