/**
 * 拖拽期的本地预判。纯函数，可单测。
 *
 * ⚠️ **只提示，绝不拦截。**
 * 演示脚本本身就是"故意把课拖到非法位置"（把只在第 1 学期开课的 CS101 拖到第 3 学期），
 * 若在这里禁用非法泳道，演示根本复现不出来。所以本地判断只负责：
 *   - 给泳道加高亮（ok / warn / blocked）
 *   - 给出原因气泡
 * 落下仍然照常提交，由服务端给出权威结论。
 *
 * 界面上统一标注为「预览」——与面板里的服务端结论区分开，避免两者不一致时用户困惑。
 */

import type { Course, PlanItem, Program } from '@/api/types'
import { formatCredits, termLabel } from './format'
import { round1 } from './format'

export type PreviewLevel = 'ok' | 'warn' | 'blocked'

export interface Preview {
  level: PreviewLevel
  reason: string
}

export const NEUTRAL_PREVIEW: Preview = { level: 'ok', reason: '' }

export function previewDrop(
  program: Program,
  items: PlanItem[],
  course: Course | undefined,
  toTerm: number,
): Preview {
  if (!course) return { level: 'blocked', reason: '课程不在本培养方案中' }

  if (!Number.isInteger(toTerm) || toTerm < 1 || toTerm > program.total_terms) {
    return { level: 'blocked', reason: `学期超出 1–${program.total_terms} 的范围` }
  }

  const current = items.find((i) => i.course_code === course.code)
  if (current && current.term === toTerm) {
    return NEUTRAL_PREVIEW
  }

  // 开课学期白名单：terms 为空 = 未标注，视为每学期均可
  if (course.terms.length > 0 && !course.terms.includes(toTerm)) {
    const offered = course.terms.map((t) => termLabel(t)).join('、')
    return { level: 'blocked', reason: `${course.code} 只在${offered}开课` }
  }

  // 学期学分上限
  const cap = round1(program.max_credits_per_term ?? 0)
  if (cap > 0) {
    const index = new Map(program.courses.map((c) => [c.code, c]))
    let load = 0
    for (const item of items) {
      if (item.course_code === course.code) continue
      if (item.term !== toTerm) continue
      load += index.get(item.course_code)?.credits ?? 0
    }
    const after = round1(load + course.credits)
    if (after > cap) {
      return { level: 'warn', reason: `第 ${toTerm} 学期将达 ${formatCredits(after)}/${formatCredits(cap)} 学分` }
    }
  }

  // 先修顺序
  for (const prereq of course.prerequisites) {
    const placed = items.find((i) => i.course_code === prereq)
    if (placed && placed.term >= toTerm) {
      return {
        level: 'warn',
        reason: `先修课 ${prereq} 排在第 ${placed.term} 学期，不早于本课`,
      }
    }
  }

  return NEUTRAL_PREVIEW
}

/** 泳道高亮的汇总：有任何一门课落下会被判 blocked，泳道就显示红环 */
export function worstLevel(previews: Preview[]): PreviewLevel {
  if (previews.some((p) => p.level === 'blocked')) return 'blocked'
  if (previews.some((p) => p.level === 'warn')) return 'warn'
  return 'ok'
}
