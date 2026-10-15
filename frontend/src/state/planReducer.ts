/**
 * 规划状态的纯 reducer。
 *
 * 为什么用 reducer 而不是若干 useState：
 *  1. **原子性** —— 移动一门课在语义上是「从 A 移除 + 加到 B」。用两个 setState 会出现
 *     一个中间渲染帧，那门课在板子上消失一帧；若校验恰好在这一帧触发，就会闪出一条
 *     假的 `unknown_course`。reducer 的每个 action 都不可观测中间态。
 *  2. **不变式集中** —— 「每门课最多出现一次」（后端 `duplicate_course` 是 error 级）
 *     由这里保证，而不是散落在 8 个泳道的 onDrop 里。
 *  3. **撤销/重做天然属于 reducer**，用 useState 就得手写快照，等于自己写个更差的 reducer。
 *  4. 纯函数，可直接单测。
 */

import type { CompletedCourse, PlanItem } from '@/api/types'

export interface PlanState {
  programId: string
  items: PlanItem[]
  completed: CompletedCourse[]
}

export type PlanOrigin = 'empty' | 'sample' | 'suggest' | 'manual'

export interface PlanHistory {
  current: PlanState
  past: PlanState[]
  future: PlanState[]
  /** 「恢复样例规划」的目标状态 */
  baseline: PlanState
  origin: PlanOrigin
}

export const HISTORY_LIMIT = 50

export type PlanAction =
  | { type: 'SET_PROGRAM'; programId: string }
  | { type: 'MOVE_COURSE'; courseCode: string; toTerm: number }
  | { type: 'ADD_COURSE'; courseCode: string; term: number }
  | { type: 'REMOVE_COURSE'; courseCode: string }
  | { type: 'REPLACE_PLAN'; plan: PlanState; origin: PlanOrigin; asBaseline?: boolean }
  | { type: 'UNDO' }
  | { type: 'REDO' }
  | { type: 'RESET_TO_SAMPLE' }
  | { type: 'CLEAR' }

export function emptyPlan(programId: string): PlanState {
  return { programId, items: [], completed: [] }
}

/** 统一排序，保证「同一份规划」的签名稳定 —— 校验去重与撤销判定都依赖它 */
export function sortItems(items: PlanItem[]): PlanItem[] {
  return [...items].sort((a, b) => a.term - b.term || a.course_code.localeCompare(b.course_code))
}

export function planSignature(plan: PlanState): string {
  const items = sortItems(plan.items).map((i) => `${i.term}:${i.course_code}`)
  const done = [...plan.completed]
    .sort((a, b) => a.course_code.localeCompare(b.course_code))
    .map((c) => `${c.course_code}:${c.passed ? 1 : 0}`)
  return `${plan.programId}|${items.join(',')}|${done.join(',')}`
}

export function createHistory(programId: string): PlanHistory {
  const plan = emptyPlan(programId)
  return { current: plan, past: [], future: [], baseline: plan, origin: 'empty' }
}

/** 落定一次变更：入栈、清空重做栈、截断到上限 */
function commit(state: PlanHistory, next: PlanState, origin: PlanOrigin, asBaseline = false): PlanHistory {
  return {
    current: next,
    past: [...state.past, state.current].slice(-HISTORY_LIMIT),
    future: [],
    baseline: asBaseline ? next : state.baseline,
    origin,
  }
}

export function planReducer(state: PlanHistory, action: PlanAction): PlanHistory {
  switch (action.type) {
    case 'SET_PROGRAM': {
      if (state.current.programId === action.programId) return state
      const plan = emptyPlan(action.programId)
      return { current: plan, past: [], future: [], baseline: plan, origin: 'empty' }
    }

    case 'MOVE_COURSE':
    case 'ADD_COURSE': {
      const term = action.type === 'MOVE_COURSE' ? action.toTerm : action.term
      const code = action.courseCode
      if (!Number.isInteger(term) || term < 1) return state

      const existing = state.current.items.find((i) => i.course_code === code)
      // 已在目标学期 = 无操作（不污染撤销栈）
      if (existing && existing.term === term) return state

      // 先剔除再插入 —— 一条 action 内完成，中间态不可观测（见文件头注释）
      const items = state.current.items.filter((i) => i.course_code !== code)
      items.push({ course_code: code, term })

      return commit(state, { ...state.current, items: sortItems(items) }, 'manual')
    }

    case 'REMOVE_COURSE': {
      const items = state.current.items.filter((i) => i.course_code !== action.courseCode)
      if (items.length === state.current.items.length) return state
      return commit(state, { ...state.current, items }, 'manual')
    }

    case 'REPLACE_PLAN': {
      const next: PlanState = {
        programId: action.plan.programId,
        items: sortItems(action.plan.items),
        completed: action.plan.completed,
      }
      return commit(state, next, action.origin, action.asBaseline ?? false)
    }

    case 'UNDO': {
      const previous = state.past.at(-1)
      if (!previous) return state
      return {
        ...state,
        current: previous,
        past: state.past.slice(0, -1),
        future: [state.current, ...state.future].slice(0, HISTORY_LIMIT),
      }
    }

    case 'REDO': {
      const next = state.future[0]
      if (!next) return state
      return {
        ...state,
        current: next,
        past: [...state.past, state.current].slice(-HISTORY_LIMIT),
        future: state.future.slice(1),
      }
    }

    case 'RESET_TO_SAMPLE': {
      if (planSignature(state.current) === planSignature(state.baseline)) return state
      return commit(state, state.baseline, 'sample')
    }

    case 'CLEAR': {
      if (state.current.items.length === 0) return state
      return commit(state, emptyPlan(state.current.programId), 'empty')
    }

    default:
      return state
  }
}

export const canUndo = (state: PlanHistory) => state.past.length > 0
export const canRedo = (state: PlanHistory) => state.future.length > 0
export const isDirty = (state: PlanHistory) =>
  planSignature(state.current) !== planSignature(state.baseline)
