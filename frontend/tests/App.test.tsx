import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '@/app/App'

describe('App', () => {
  it('renders without crashing', async () => {
    render(<App />)
    // 页面为 React.lazy 懒加载，使用 findBy 等待异步渲染完成
    expect(await screen.findByText('前后端分离基础开发框架')).toBeInTheDocument()
  })

  it('shows placeholder content on home page', async () => {
    render(<App />)
    expect(await screen.findByText(/前端工程骨架已就绪/)).toBeInTheDocument()
  })

  it('shows health check button with error marker initially', async () => {
    render(<App />)
    expect(await screen.findByRole('button', { name: '测试后端连接' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('❌')
  })
})
