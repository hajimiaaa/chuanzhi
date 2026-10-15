/**
 * 启动探活。
 *
 * 这是「后端没起时不白屏」的基础：探活失败时页面给出**精确**的修复指令，
 * 而不是渲染一堆空组件。
 *
 * 刻意不做离线假数据 —— 后端 models.py 明文写着"两套领域模型必然漂移"，
 * 前端塞一份静态的 program 副本是同一个错误，而且会把"后端挂了"
 * 悄悄变成"数据过期了"，更难排查。
 */

import { useCallback, useEffect, useState } from 'react'

import { getHealth } from '@/api/endpoints'
import type { HealthResponse } from '@/api/types'

export type HealthStatus = 'checking' | 'ok' | 'down'

export interface HealthState {
  status: HealthStatus
  data: HealthResponse | null
  error: string
  retry: () => void
}

export function useHealth(): HealthState {
  const [status, setStatus] = useState<HealthStatus>('checking')
  const [data, setData] = useState<HealthResponse | null>(null)
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('checking')

    getHealth({ signal: controller.signal, timeoutMs: 4000 })
      .then((response) => {
        setData(response)
        setStatus('ok')
        setError('')
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setStatus('down')
        setError(cause instanceof Error ? cause.message : String(cause))
      })

    return () => controller.abort()
  }, [nonce])

  const retry = useCallback(() => setNonce((n) => n + 1), [])

  return { status, data, error, retry }
}
