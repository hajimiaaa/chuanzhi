/**
 * 补修/重修清单的数据加载。
 *
 * 沿用 useValidation / useRules 的两条纪律：
 *  - 竞态守卫（AbortController + seq）
 *  - **失败不清空**：保留上一次的清单并打「已过期」。
 *    清单被清空会被读成"没有要补的课"——比报错危险得多。
 *
 * 成绩单为空时不发请求：空成绩单算出来的是"整份培养方案都要补修"，
 * 那不是用户想看的初始态，交给界面单独处理。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/api/client'
import { creditGap } from '@/api/endpoints'
import type { CompletedCourse, CreditGapResponse, Program } from '@/api/types'

export type CreditGapStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface CreditGapState {
  data: CreditGapResponse | null
  status: CreditGapStatus
  error: string
  /** 曾经成功、现在失败 —— 打「已过期」而不是清空 */
  stale: boolean
  loading: boolean
  reload: () => void
}

export function useCreditGap(
  program: Program | null,
  completed: CompletedCourse[],
): CreditGapState {
  const [data, setData] = useState<CreditGapResponse | null>(null)
  const [status, setStatus] = useState<CreditGapStatus>('idle')
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)
  const seqRef = useRef(0)

  const programId = program?.id ?? null
  const hasTranscript = completed.length > 0

  useEffect(() => {
    if (!programId || !hasTranscript) {
      seqRef.current += 1 // 作废在途请求
      setData(null)
      setStatus('idle')
      setError('')
      return
    }

    const controller = new AbortController()
    const mine = ++seqRef.current
    setStatus('loading')
    setError('')

    creditGap(
      {
        program_id: programId,
        completed,
      },
      { signal: controller.signal },
    )
      .then((response) => {
        if (mine !== seqRef.current) return // 后发先至守卫
        if (controller.signal.aborted) return
        setData(response)
        setStatus('ready')
        setError('')
      })
      .catch((cause: unknown) => {
        if (mine !== seqRef.current) return
        if (controller.signal.aborted) return
        setStatus('error')
        setError(describeError(cause))
        // 刻意不动 data —— 保住上一次的清单
      })

    return () => controller.abort()
  }, [programId, completed, hasTranscript, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  return {
    data,
    status,
    error,
    stale: status === 'error' && data !== null,
    loading: status === 'loading',
    reload,
  }
}
