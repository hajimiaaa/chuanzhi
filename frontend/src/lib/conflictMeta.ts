/**
 * 冲突类型的登记表 —— 后端的 16 种 `kind` 在这里必须有中文名与分组。
 *
 * ⚠️ 未知 kind **不静默变空白**：原样显示 kind 字符串 + 控制台提醒一次。
 * 后端 constraints.py 的 KIND_ORDER 是会增长的，而"新类型悄悄不显示"正是
 * 本项目一直在防的那种静默假阴性。
 */

import type { Conflict } from '@/api/types'

export type ConflictGroup = 'prerequisite' | 'schedule' | 'credit' | 'data' | 'boundary'

export interface ConflictMeta {
  kind: string
  label: string
  group: ConflictGroup
  /** true = 这张表里没登记，按原样显示 */
  fallback?: boolean
}

export const GROUP_LABEL: Record<ConflictGroup, string> = {
  prerequisite: '先修关系',
  schedule: '开课与负荷',
  credit: '学分达标',
  data: '录入与数据',
  boundary: '数据边界说明',
}

export const GROUP_ORDER: readonly ConflictGroup[] = [
  'prerequisite',
  'schedule',
  'credit',
  'data',
  'boundary',
]

const TABLE: Record<string, { label: string; group: ConflictGroup }> = {
  program_mismatch: { label: '培养方案不匹配', group: 'data' },
  unknown_course: { label: '课程代码不存在', group: 'data' },
  duplicate_course: { label: '课程重复安排', group: 'data' },
  unknown_term: { label: '学期超出学制', group: 'data' },
  unknown_completed_course: { label: '已修课程不在本方案', group: 'data' },
  grade_unlabeled: { label: '已修课程未标成绩', group: 'data' },
  unknown_category: { label: '课程类别未定义', group: 'credit' },

  prerequisite_cycle: { label: '循环先修', group: 'prerequisite' },
  prerequisite_missing: { label: '先修课缺位', group: 'prerequisite' },
  prerequisite_order: { label: '先修顺序颠倒', group: 'prerequisite' },
  prerequisite_failed: { label: '先修课未通过', group: 'prerequisite' },

  course_not_offered: { label: '开课学期不匹配', group: 'schedule' },
  term_overload: { label: '学期学分超载', group: 'schedule' },
  time_overlap: { label: '上课时段重叠', group: 'schedule' },

  time_data_missing: { label: '时间检测未接入', group: 'boundary' },
  credit_below_minimum: { label: '学分未达标', group: 'credit' },
}

const warned = new Set<string>()

export function conflictMeta(kind: string): ConflictMeta {
  const known = TABLE[kind]
  if (known) return { kind, ...known }

  if (!warned.has(kind)) {
    warned.add(kind)
    console.warn(
      `[conflictMeta] 未登记的冲突类型 "${kind}"，已按原样显示。请同步 lib/conflictMeta.ts`,
    )
  }
  return { kind, label: kind, group: 'data', fallback: true }
}

/** 数据边界说明不参与计数 —— 否则"未接入"会被读成"有问题" */
export function countsTowardSummary(kind: string): boolean {
  return conflictMeta(kind).group !== 'boundary'
}

/** expected / actual 都有值时才有"数值对比"语义（画 meter），否则画课程链 */
export function hasRatio(conflict: Conflict): boolean {
  return typeof conflict.expected === 'number' && typeof conflict.actual === 'number'
}

export type MeterVariant = 'over' | 'gap'

/**
 * 超出型 vs 缺口型 —— 两者必须分开。
 * 语义相反（一个越界、一个还差），长得一样会让人读错。
 */
export function meterVariant(conflict: Conflict): MeterVariant {
  return (conflict.actual ?? 0) > (conflict.expected ?? 0) ? 'over' : 'gap'
}
