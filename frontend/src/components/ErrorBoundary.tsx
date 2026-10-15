/** 兜住渲染期异常。退出方式是「恢复样例规划」—— 演示时最要紧的是能立刻回到可用状态。 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  onReset?: () => void
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] 渲染期异常:', error, info.componentStack)
  }

  private handleReset = () => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="panel" style={{ margin: 24 }}>
        <h2 className="panel__title">页面渲染出错</h2>
        <p className="secondary small" style={{ marginTop: 0 }}>
          {error.message}
        </p>
        <button className="btn btn--primary" onClick={this.handleReset}>
          恢复样例规划
        </button>
      </div>
    )
  }
}
