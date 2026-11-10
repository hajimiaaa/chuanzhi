/**
 * 把规划状态下发给泳道板与冲突面板。
 *
 * 校验结果**不放这里** —— 它是独立的派生 hook（useValidation），
 * 挂进来会让每次冲突变化都重渲染整棵树。
 */

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react'

import { savePlan } from '@/lib/planStorage'
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

  // 每次变更都落盘：刷新页面不丢排课与成绩单。读写失败静默跳过，不影响使用。
  // ⚠️ 空规划不落盘：PlanProvider 挂载时样例方案还没加载，此时写盘会把"空"存成
  //    存档，随后恢复逻辑又拿它盖掉样例——表现为打开就是空板子。
  useEffect(() => {
    const { items, completed } = history.current
    if (items.length === 0 && completed.length === 0) return
    savePlan(history.current)
  }, [history.current])

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
