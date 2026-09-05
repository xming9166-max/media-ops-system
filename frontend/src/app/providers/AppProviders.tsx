import { QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import type { ReactNode } from 'react'

import { createQueryClient } from '@/services/query/queryClient'

const queryClient = createQueryClient()

interface AppProvidersProps {
  children: ReactNode
}

export default function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN}>{children}</ConfigProvider>
    </QueryClientProvider>
  )
}
