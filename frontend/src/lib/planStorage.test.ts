import { describe, expect, it } from 'vitest'

import { normalizePlan } from './planStorage'

const RAW = {
  programId: 'p1',
  items: [
    { course_code: 'CS101', term: 1 },
    { course_code: 'CS102', term: 2 },
  ],
  completed: [
    { course_code: 'SE102', name: '高等数学A(二)', credits: 5, grade: 84, term: '', passed: true },
  ],
}

describe('normalizePlan', () => {
  it('合法的存档原样还原', () => {
    const plan = normalizePlan(RAW, 'p1')

    expect(plan?.items).toEqual(RAW.items)
    expect(plan?.completed[0]?.name).toBe('高等数学A(二)')
  })

  it('专业对不上就丢弃 —— 不能把 A 专业的排课套到 B 专业上', () => {
    expect(normalizePlan(RAW, 'p2')).toBeNull()
  })

  it('不是对象 / 缺字段时返回 null，不抛异常', () => {
    expect(normalizePlan(null, 'p1')).toBeNull()
    expect(normalizePlan([], 'p1')).toBeNull()
    expect(normalizePlan('x', 'p1')).toBeNull()
    expect(normalizePlan({ programId: 'p1' }, 'p1')).toBeNull()
  })

  it('丢掉学期非法的条目，保留其余', () => {
    const plan = normalizePlan(
      {
        ...RAW,
        items: [
          { course_code: 'CS101', term: 1 },
          { course_code: 'CS102', term: 0 },
          { course_code: 'CS103', term: 2.5 },
          { course_code: '', term: 3 },
        ],
      },
      'p1',
    )

    expect(plan?.items).toEqual([{ course_code: 'CS101', term: 1 }])
  })

  it('成绩单缺字段时补安全默认值，不编造成绩', () => {
    const plan = normalizePlan(
      { ...RAW, completed: [{ course_code: 'X1' }] },
      'p1',
    )

    expect(plan?.completed[0]).toEqual({
      course_code: 'X1',
      name: '',
      credits: 0,
      grade: null,
      term: '',
      passed: null,
    })
  })
})
