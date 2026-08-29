import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import type { ReactNode } from 'react'

const queryClient = new QueryClient()

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
