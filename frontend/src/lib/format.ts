/** 格式化小工具。纯函数，可单测。 */

/**
 * 学分保留一位小数。
 * 培养方案里有 2.5 / 1.5 / 0.5 这类值，直接求和会出现 39.999999999999996 ——
 * 后端 constraints.py 里用同一个策略（round(x, 1)）收敛。
 */
export function round1(value: number): number {
  return Math.round(value * 10) / 10
}

export function formatCredits(value: number): string {
  const rounded = round1(value)
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
}

export function termLabel(term: number): string {
  return `第 ${term} 学期`
}

export function dayLabel(day: number): string {
  const names = '一二三四五六日'
  return `周${names[day - 1] ?? '?'}`
}

export function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/** 把 null / undefined 统一显示成破折号，避免界面上出现 "null" */
export function dash(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}
