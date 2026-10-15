/**
 * 从「培养方案 + 规划」派生的学分统计。纯函数，可单测。
 *
 * 口径与后端 constraints.py 一致：只统计能对上课程库的课程，按 code 去重。
 */

import type { Course, PlanItem, Program } from '@/api/types'
import { round1 } from './format'

export interface CreditTotals {
  /** 类别 -> 学分 */
  byCategory: Record<string, number>
  /** 学期 -> 学分 */
  byTerm: Record<number, number>
  /** 学期 -> 类别 -> 学分（ECharts 堆叠柱用） */
  byTermCategory: Record<number, Record<string, number>>
  total: number
}

export function courseIndex(program: Program): Map<string, Course> {
  return new Map(program.courses.map((course) => [course.code, course]))
}

export function computeCredits(program: Program, items: PlanItem[]): CreditTotals {
  const index = courseIndex(program)
  const byCategory: Record<string, number> = {}
  const byTerm: Record<number, number> = {}
  const byTermCategory: Record<number, Record<string, number>> = {}
  const seen = new Set<string>()
  let total = 0

  for (const item of items) {
    if (seen.has(item.course_code)) continue // 同课重复排只计一次
    const course = index.get(item.course_code)
    if (!course) continue
    seen.add(item.course_code)

    total += course.credits
    byCategory[course.category] = (byCategory[course.category] ?? 0) + course.credits
    byTerm[item.term] = (byTerm[item.term] ?? 0) + course.credits
    const perTerm = (byTermCategory[item.term] ??= {})
    perTerm[course.category] = (perTerm[course.category] ?? 0) + course.credits
  }

  for (const key of Object.keys(byCategory)) byCategory[key] = round1(byCategory[key])
  for (const key of Object.keys(byTerm)) byTerm[Number(key)] = round1(byTerm[Number(key)])
  for (const term of Object.keys(byTermCategory)) {
    for (const cat of Object.keys(byTermCategory[Number(term)])) {
      byTermCategory[Number(term)][cat] = round1(byTermCategory[Number(term)][cat])
    }
  }

  return { byCategory, byTerm, byTermCategory, total: round1(total) }
}

/** 尚未排入任何学期的课程 */
export function unplacedCourses(program: Program, items: PlanItem[]): Course[] {
  const placed = new Set(items.map((i) => i.course_code))
  return program.courses.filter((course) => !placed.has(course.code))
}

/** 触发某条冲突的课程代码集合，用于面板筛选 */
export function conflictCourseSet(conflicts: { course_codes: string[] }[]): Set<string> {
  const set = new Set<string>()
  for (const conflict of conflicts) {
    for (const code of conflict.course_codes) set.add(code)
  }
  return set
}
