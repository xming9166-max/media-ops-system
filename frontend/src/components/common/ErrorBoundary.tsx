/* 全局错误边界：页面崩溃时兜底展示，避免白屏。
 *
 * React 19 仍无内置 ErrorBoundary，使用经典 class 组件实现。
 */

import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

import { logger } from '@/services/log/logger'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 统一错误上报钩子（后续可接 Sentry / 自建错误上报）
    logger.error('[ErrorBoundary] 未捕获错误:', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100vh',
              gap: 12,
            }}
          >
            <h2>页面出现异常</h2>
            <p>请刷新页面重试，若问题持续请联系管理员。</p>
            <button
              type="button"
              onClick={() => {
                this.setState({ hasError: false })
              }}
            >
              重试
            </button>
          </div>
        )
      )
    }
    return this.props.children
  }
}
