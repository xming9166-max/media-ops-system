import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '@/app/App'

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByText('自媒体运营系统')).toBeInTheDocument()
  })

  it('shows placeholder content on home page', () => {
    render(<App />)
    expect(screen.getByText(/前端工程骨架已就绪/)).toBeInTheDocument()
  })

  it('shows health check button with error marker initially', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: '测试后端连接' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('❌')
  })
})
