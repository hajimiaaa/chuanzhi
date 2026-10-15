/**
 * 实时校验：把当前规划发给后端，拿回权威的冲突列表。
 *
 * 三件必须做对的事：
 *  1. **防抖**（300ms trailing）—— 连续拖几门课、或按住 Ctrl+Z 连撤，只发一次
 *  2. **竞态守卫** —— `AbortController` + `seq` 序号双保险。`abort()` 只是发出信号，
 *     被取消的请求仍可能已经收到响应并进入回调；`seq` 才是"后发先至"的可靠解法
 *  3. **失败不清空** —— 网络抖动时保留上一次结果并打"已过期"徽章。
 *     把面板清空等于告诉用户"没有冲突"，那是比报错更危险的假阴性
 *
 * 另：空规划**不自动请求**（见迭代 3 计划结论 A）。样例数据下空规划会一次冒出
 * 5 条「学分不足」，开局满屏红。空态由 UI 单独设计，但保留 `run()` 让用户能手动触发。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/api/client'
import { validatePlan } from '@/api/endpoints'
import type {
  Conflict,
  DataStatus,
  PlanIn,
  Program,
  ScheduleStatus,
  Summary,
  ValidateResponse,
} from '@/api/types'
import { planSignature, sortItems, type PlanState } from '@/state/planReducer'

export const DEBOUNCE_MS = 300
const CACHE_LIMIT = 50

export type ValidationStatus = 'idle' | 'loading' | 'ok' | 'error'

export interface ValidationResult {
  conflicts: Conflict[]
  summary: Summary | null
  dataStatus: DataStatus | null
  scheduleStatus: ScheduleStatus | null
}

export interface ValidationState {
  result: ValidationResult | null
  status: ValidationStatus
  error: string
  /** 曾经成功、现在失败 —— 面板要打"已过期"而不是清空 */
  stale: boolean
  /** 请求在途 —— 面板降透明度，而不是换骨架屏（避免闪烁） */
  loading: boolean
  run: () => void
}

function toPlanIn(plan: PlanState): PlanIn {
  return {
    program_id: plan.programId,
    items: sortItems(plan.items),
    completed: plan.completed,
  }
}

export function useValidation(program: Program | null, plan: PlanState | null): ValidationState {
  const [result, setResult] = useState<ValidationResult | null>(null)
  const [status, setStatus] = useState<ValidationStatus>('idle')
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)

  const forceRef = useRef(false)
  const seqRef = useRef(0)
  const cacheRef = useRef(new Map<string, ValidateResponse>())

  const signature = program && plan ? planSignature(plan) : ''

  const apply = useCallback((response: ValidateResponse) => {
    setResult({
      conflicts: response.conflicts,
      summary: response.summary,
      dataStatus: response.data_status,
      scheduleStatus: response.schedule_status,
    })
    setStatus('ok')
    setError('')
  }, [])

  useEffect(() => {
    if (!program || !plan || !signature) return

    const isEmpty = plan.items.length === 0
    if (isEmpty && !forceRef.current) {
      seqRef.current += 1 // 作废在途请求
      setResult(null)
      setStatus('idle')
      setError('')
      return
    }
    forceRef.current = false

    const cached = cacheRef.current.get(signature)
    if (cached) {
      apply(cached)
      return
    }

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      const mine = ++seqRef.current
      setStatus('loading')

      validatePlan(toPlanIn(plan), { signal: controller.signal })
        .then((response) => {
          if (mine !== seqRef.current) return // 后发先至守卫
          if (cacheRef.current.size > CACHE_LIMIT) cacheRef.current.clear()
          cacheRef.current.set(signature, response)
          apply(response)
        })
        .catch((cause: unknown) => {
          if (mine !== seqRef.current) return
          if (controller.signal.aborted) return
          setStatus('error')
          setError(describeError(cause))
          // 刻意不动 result —— 保住上一次的冲突列表
        })
    }, DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [signature, program, nonce, apply])

  const run = useCallback(() => {
    forceRef.current = true
    setNonce((n) => n + 1)
  }, [])

  return {
    result,
    status,
    error,
    stale: status === 'error' && result !== null,
    loading: status === 'loading',
    run,
  }
}
