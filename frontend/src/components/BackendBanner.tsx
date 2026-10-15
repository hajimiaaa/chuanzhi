/**
 * 后端未启动时的贯通提示条。
 *
 * 这是「不白屏」的核心：给出**可直接复制执行的命令**，而不是一句"加载失败"。
 * 刻意不做离线假数据 —— 那会把"后端挂了"悄悄变成"数据过期了"。
 */

import { API_BASE } from '@/api/client'

interface Props {
  error: string
  onRetry: () => void
}

export function BackendBanner({ error, onRetry }: Props) {
  return (
    <div className="banner" role="alert">
      <span aria-hidden="true" style={{ fontSize: 16, lineHeight: '20px' }}>
        ⚠
      </span>
      <div style={{ flex: 1 }}>
        <strong>连不上后端</strong>
        <div className="small" style={{ marginTop: 2 }}>
          目标地址 <code>{API_BASE}</code>。请在另一个终端执行：
          <div style={{ marginTop: 6 }}>
            <code>cd backend</code>
            <br />
            <code>py -3.11 -m uvicorn app.main:app --port 8000</code>
          </div>
        </div>
        <details className="small" style={{ marginTop: 6 }}>
          <summary style={{ cursor: 'pointer' }}>错误详情</summary>
          <div className="muted">{error}</div>
        </details>
      </div>
      <button className="btn" onClick={onRetry}>
        重试
      </button>
    </div>
  )
}
