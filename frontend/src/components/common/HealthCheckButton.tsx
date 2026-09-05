import { Button, Space } from 'antd'
import { useState } from 'react'
import { fetchHealth } from '@/services/api/health'

type HealthCheckStatus = 'idle' | 'loading' | 'success' | 'error'

export default function HealthCheckButton() {
  const [status, setStatus] = useState<HealthCheckStatus>('idle')

  const handleCheck = async () => {
    if (status === 'loading') return
    setStatus('loading')
    try {
      const data = await fetchHealth()
      setStatus(data.status === 'ok' ? 'success' : 'error')
    } catch {
      setStatus('error')
    }
  }

  return (
    <Space>
      <Button onClick={handleCheck} loading={status === 'loading'}>
        测试后端连接
      </Button>
      <span role="status" aria-label="连接状态">
        {status === 'success' ? '✅' : '❌'}
      </span>
    </Space>
  )
}
