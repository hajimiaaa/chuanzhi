import { describe, expect, it } from 'vitest'

import type { Course, Program } from '@/api/types'
import { previewDrop, worstLevel } from './localRules'

function course(code: string, credits = 3, terms: number[] = [], prereqs: string[] = []): Course {
  return { code, name: code, credits, category: '必修', prerequisites: prereqs, terms, slots: [] }
}

function program(courses: Course[], cap = 20, totalTerms = 8): Program {
  return {
    id: 'p1',
    name: '测试专业',
    college: '',
    campus: '',
    data_status: 'sample',
    note: '',
    catalog_ref: '',
    schedule_status: 'not_available',
    total_terms: totalTerms,
    total_min_credits: 100,
    max_credits_per_term: cap,
    credit_rules: [],
    courses,
  }
}

describe('previewDrop', () => {
  it('未标注开课学期（terms 为空）= 每学期都可以', () => {
    const p = program([course('A')])
    expect(previewDrop(p, [], p.courses[0], 5).level).toBe('ok')
  })

  it('排到不开课的学期 → blocked，并说明实际开课学期', () => {
    const p = program([course('A', 3, [1])])
    const result = previewDrop(p, [], p.courses[0], 3)
    expect(result.level).toBe('blocked')
    expect(result.reason).toContain('第 1 学期')
  })

  it('多学期开课时把每个学期都列出来', () => {
    const p = program([course('A', 3, [3, 5])])
    const result = previewDrop(p, [], p.courses[0], 4)
    expect(result.level).toBe('blocked')
    expect(result.reason).toContain('第 3 学期')
    expect(result.reason).toContain('第 5 学期')
  })

  it('学期越界 → blocked', () => {
    const p = program([course('A')], 20, 8)
    expect(previewDrop(p, [], p.courses[0], 9).level).toBe('blocked')
  })

  it('超过学期学分上限 → warn（不是 blocked）', () => {
    const p = program([course('A', 12), course('B', 10)], 20)
    const items = [{ course_code: 'B', term: 1 }]
    const result = previewDrop(p, items, p.courses[0], 1)
    expect(result.level).toBe('warn')
    expect(result.reason).toContain('22')
  })

  it('未设上限（cap = 0）时不判超载', () => {
    const p = program([course('A', 40)], 0)
    expect(previewDrop(p, [], p.courses[0], 1).level).toBe('ok')
  })

  it('先修课排在同一个或更后的学期 → warn', () => {
    const p = program([course('A'), course('B', 3, [], ['A'])])
    const items = [{ course_code: 'A', term: 4 }]
    const result = previewDrop(p, items, p.courses[1], 4)
    expect(result.level).toBe('warn')
    expect(result.reason).toContain('A')
  })

  it('先修课排得更早则不提示', () => {
    const p = program([course('A'), course('B', 3, [], ['A'])])
    const items = [{ course_code: 'A', term: 1 }]
    expect(previewDrop(p, items, p.courses[1], 4).level).toBe('ok')
  })

  it('拖回原学期 = 无变化，不显示提示', () => {
    const p = program([course('A', 3, [1])])
    const items = [{ course_code: 'A', term: 1 }]
    const result = previewDrop(p, items, p.courses[0], 1)
    expect(result.level).toBe('ok')
    expect(result.reason).toBe('')
  })

  it('未知课程 → blocked', () => {
    const p = program([course('A')])
    expect(previewDrop(p, [], undefined, 1).level).toBe('blocked')
  })
})

describe('worstLevel', () => {
  it('blocked 压过 warn 压过 ok', () => {
    expect(worstLevel([{ level: 'ok', reason: '' }, { level: 'warn', reason: '' }])).toBe('warn')
    expect(
      worstLevel([
        { level: 'warn', reason: '' },
        { level: 'blocked', reason: '' },
        { level: 'ok', reason: '' },
      ]),
    ).toBe('blocked')
    expect(worstLevel([])).toBe('ok')
  })
})
