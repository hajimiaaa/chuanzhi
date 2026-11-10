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

  it('保留课程名称 —— 跨专业同名课靠它识别', () => {
    const item = makeCompleted({
      course_code: 'SE102',
      name: ' 高等数学A(二) ',
      credits: 5,
      grade: 84,
    })
    expect(item.name).toBe('高等数学A(二)')
  })

  it('不填名称时是空串，不编造', () => {
    expect(makeCompleted({ course_code: 'X1', credits: 2, grade: 80 }).name).toBe('')
  })
})

describe('SAMPLE_TRANSCRIPT', () => {
  const byCode = new Map(SAMPLE_TRANSCRIPT.map((c) => [c.course_code, c]))

  it('是一份像真的转专业成绩单，而不是四门课', () => {
    expect(SAMPLE_TRANSCRIPT.length).toBeGreaterThanOrEqual(30)
  })

  it('覆盖已认定 / 重修 / 可能可折抵 / 待认定四种情形', () => {
    // 课号相同且通过
    expect(byCode.get('CS101')?.passed).toBe(true)
    // 课号相同但未通过
    expect(byCode.get('CS203')?.passed).toBe(false)
    // 原专业同名课：课号不同，但名称要和培养方案对得上
    expect(byCode.get('SE102')?.name).toBe('高等数学A(二)')
    expect(byCode.get('SE102')?.credits).toBe(5)
    // 原专业独有课程
    expect(byCode.get('SE001')?.name).toBe('软件工程导论')
  })

  it('没有重复课号', () => {
    const codes = SAMPLE_TRANSCRIPT.map((c) => c.course_code)
    expect(new Set(codes).size).toBe(codes.length)
  })
})
