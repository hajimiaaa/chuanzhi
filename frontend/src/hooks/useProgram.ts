/** 加载培养方案详情 + 开箱即用的样例规划。两者并行取，避免串行等待。 */

import { useEffect, useState } from 'react'

import { describeError } from '@/api/client'
import { getProgram, getSamplePlan } from '@/api/endpoints'
import type { PlanSuggestion, Program } from '@/api/types'

export type ProgramStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface ProgramState {
  program: Program | null
  /** 后端算出来的可行解 —— 前端的初始态与「恢复样例规划」的基线 */
  samplePlan: PlanSuggestion | null
  status: ProgramStatus
  error: string
}

const IDLE: ProgramState = { program: null, samplePlan: null, status: 'idle', error: '' }

export function useProgram(programId: string | null): ProgramState {
  const [state, setState] = useState<ProgramState>(IDLE)

  useEffect(() => {
    if (!programId) {
      setState(IDLE)
      return
    }

    const controller = new AbortController()
    setState((previous) => ({ ...previous, status: 'loading', error: '' }))

    Promise.all([
      getProgram(programId, { signal: controller.signal }),
      getSamplePlan(programId, { signal: controller.signal }),
    ])
      .then(([program, sample]) => {
        if (controller.signal.aborted) return
        setState({ program, samplePlan: sample.plan, status: 'ready', error: '' })
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setState({ program: null, samplePlan: null, status: 'error', error: describeError(cause) })
      })

    return () => controller.abort()
  }, [programId])

  return state
}
