import { useQuery } from '@tanstack/react-query'
import { httpClient } from '@/services/http/client'

export interface HealthStatus {
  status: string
}

export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await httpClient.get<HealthStatus>('/api/v1/health')
  return data
}

export function useHealthStatus() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  })
}