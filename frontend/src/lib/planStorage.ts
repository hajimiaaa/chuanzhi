/**
 * 规划与成绩单的本地持久化。
 *
 * 目的很具体：评委试玩时刷新一次页面，拖了半天的排课和录入的成绩单不该全丢。
 * 只存 `items` 与 `completed`，不存撤销栈——撤销历史没有跨会话的意义。
 *
 * `normalizePlan` 是纯函数，可单测；真正的 localStorage 读写在它外面，
 * 并且在 `window` 不存在时安静跳过（node 测试环境）。
 */

import type { CompletedCourse, PlanItem } from '@/api/types'
import type { PlanState } from '@/state/planReducer'

export const PLAN_STORAGE_KEY = 'kepath.plans.v1'

type PlanStore = Record<string, PlanState>

function isPositiveInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1
}

/** 把任意 JSON 归一化成合法的 PlanState；不合法就返回 null，绝不抛异常。 */
export function normalizePlan(value: unknown, programId: string): PlanState | null {
  if (!value || typeof value !== 'object') return null
  const data = value as Record<string, unknown>
  if (data.programId !== programId) return null
  if (!Array.isArray(data.items) || !Array.isArray(data.completed)) return null

  const items: PlanItem[] = []
  for (const entry of data.items) {
    if (!entry || typeof entry !== 'object') continue
    const item = entry as Record<string, unknown>
    if (typeof item.course_code !== 'string' || !item.course_code) continue
    if (!isPositiveInt(item.term)) continue
    items.push({ course_code: item.course_code, term: item.term })
  }

  const completed: CompletedCourse[] = []
  for (const entry of data.completed) {
    if (!entry || typeof entry !== 'object') continue
    const item = entry as Record<string, unknown>
    if (typeof item.course_code !== 'string' || !item.course_code) continue
    const credits =
      typeof item.credits === 'number' && Number.isFinite(item.credits) ? item.credits : 0
    const grade =
      typeof item.grade === 'number' || typeof item.grade === 'string' ? item.grade : null
    completed.push({
      course_code: item.course_code,
      name: typeof item.name === 'string' ? item.name : '',
      credits,
      grade,
      term: typeof item.term === 'string' ? item.term : '',
      passed: typeof item.passed === 'boolean' ? item.passed : null,
    })
  }

  return { programId, items, completed }
}

function readStore(): PlanStore {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(PLAN_STORAGE_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed as PlanStore
  } catch {
    return {}
  }
}

export function loadPlan(programId: string): PlanState | null {
  return normalizePlan(readStore()[programId], programId)
}

export function savePlan(plan: PlanState): void {
  if (typeof window === 'undefined') return
  try {
    const store = readStore()
    store[plan.programId] = plan
    window.localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(store))
  } catch {
    // 存不下（隐私模式 / 配额满）不影响使用
  }
}

export function clearStoredPlan(programId: string): void {
  if (typeof window === 'undefined') return
  try {
    const store = readStore()
    delete store[programId]
    window.localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(store))
  } catch {
    // ignore
  }
}
