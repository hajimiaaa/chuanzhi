import { describe, expect, it } from 'vitest'

import { PASS_MARK, SAMPLE_TRANSCRIPT, isPassingGrade, makeCompleted } from './transcript'

describe('isPassingGrade', () => {
  it('以 60 为界，且包含边界值', () => {
    expect(isPassingGrade(PASS_MARK - 1)).toBe(false)
    expect(isPassingGrade(PASS_MARK)).toBe(true)
    expect(isPassingGrade(PASS_MARK + 1)).toBe(true)
  })

  it('0 分不算通过（不能因为 0 是假值就误判）', () => {
    expect(isPassingGrade(0)).toBe(false)
  })
})

describe('makeCompleted', () => {
  it('课号去空白并转大写', () => {
    expect(makeCompleted({ course_code: '  cs101 ', credits: 5, grade: 90 }).course_code).toBe(
      'CS101',
    )
  })

  it('按分数算出 passed', () => {
    expect(makeCompleted({ course_code: 'CS102', credits: 5, grade: 59 }).passed).toBe(false)
    expect(makeCompleted({ course_code: 'CS102', credits: 5, grade: 60 }).passed).toBe(true)
  })

  it('保留学分与原始分数，供后端复核', () => {
    const item = makeCompleted({ course_code: 'CS105', credits: 4, grade: 76 })
    expect(item.credits).toBe(4)
    expect(item.grade).toBe(76)
  })
})

describe('SAMPLE_TRANSCRIPT', () => {
  it('覆盖已认定 / 重修 / 待认定三种情形', () => {
    const byCode = new Map(SAMPLE_TRANSCRIPT.map((c) => [c.course_code, c]))

    expect(byCode.get('CS101')?.passed).toBe(true)
    expect(byCode.get('CS201')?.passed).toBe(false)
    // 原专业课程：不在样例培养方案的课程库里
    expect(byCode.get('CE101')?.passed).toBe(true)
  })

  it('没有重复课号', () => {
    const codes = SAMPLE_TRANSCRIPT.map((c) => c.course_code)
    expect(new Set(codes).size).toBe(codes.length)
  })
})
