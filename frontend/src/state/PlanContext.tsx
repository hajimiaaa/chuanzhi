/**
 * 把规划状态下发给泳道板与冲突面板。
 *
 * 校验结果**不放这里** —— 它是独立的派生 hook（useValidation），
 * 挂进来会让每次冲突变化都重渲染整棵树。
 */

import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'

import {
  canRedo as canRedoFn,
  canUndo as canUndoFn,
  createHistory,
  isDirty as isDirtyFn,
  planReducer,
  type PlanAction,
  type PlanHistory,
} from './planReducer'

export interface PlanContextValue {
  history: PlanHistory
  dispatch: Dispatch<PlanAction>
  canUndo: boolean
  canRedo: boolean
  /** 与样例基线不同 —— 决定「恢复样例规划」按钮是否可用 */
  isDirty: boolean
}

const PlanContext = createContext<PlanContextValue | null>(null)

export function PlanProvider({ programId, children }: { programId: string; children: ReactNode }) {
  const [history, dispatch] = useReducer(planReducer, programId, createHistory)

  const value = useMemo<PlanContextValue>(
    () => ({
      history,
      dispatch,
      canUndo: canUndoFn(history),
      canRedo: canRedoFn(history),
      isDirty: isDirtyFn(history),
    }),
    [history],
  )

  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>
}

export function usePlan(): PlanContextValue {
  const value = useContext(PlanContext)
  if (!value) throw new Error('usePlan 必须在 <PlanProvider> 内使用')
  return value
}
