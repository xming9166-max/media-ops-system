/* 通用 Client State store 模板。
 *
 * 约定：
 * - 只放全局 UI 状态（主题、侧边栏折叠、全局 loading 等），禁止缓存服务端数据（交给 TanStack Query）。
 * - 需要持久化的字段才用 persist（如主题偏好），且显式指定 storage。
 *
 * 复制本文件为 stores/<name>Store.ts 后按需修改，保持 create 的结构与中间件用法一致。
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface AppUiState {
  /* 侧边栏折叠状态（本地 UI 状态示例） */
  sidebarCollapsed: boolean
  /* 主题偏好（持久化示例） */
  themeMode: 'light' | 'dark'
  toggleSidebar: () => void
  setThemeMode: (mode: 'light' | 'dark') => void
}

export const useAppUiStore = create<AppUiState>()(
  devtools(
    persist(
      (set) => ({
        sidebarCollapsed: false,
        themeMode: 'light',
        toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
        setThemeMode: (themeMode) => set({ themeMode }),
      }),
      {
        // 只持久化需要跨会话保留的字段
        name: 'app-ui',
        partialize: (state) => ({ themeMode: state.themeMode }),
      },
    ),
  ),
)
