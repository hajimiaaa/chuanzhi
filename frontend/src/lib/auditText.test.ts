import { describe, expect, it } from 'vitest'

import type { AuditSheetResponse, CreditCase } from '@/api/types'
import { CONFIDENCE_LABEL, formatAuditSheet } from './auditText'

function item(code: string, name: string, credits: number, grade: number | null = null): CreditCase {
  return {
    course_code: code,
    name,
    credits,
    category: '必修',
    grade,
    terms: [],
    prerequisites: [],
  }
}

const SHEET: AuditSheetResponse = {
  program: {
    id: 'p1',
    name: '计算机科学与技术',
    college: '信息科学与工程学院',
    data_status: 'sample',
    catalog_ref: 'data/majors.json',
    note: '',
  },
  generated_at: '2026-11-10T12:00:00+08:00',
  engine_version: '0.1.0',
  summary: {
    recognized: 1,
    retake: 0,
    possible_overlap: 1,
    remedial: 0,
    pending: 1,
    recognized_credits: 5,
    retake_credits: 0,
    possible_overlap_credits: 5,
    remedial_credits: 0,
    pending_credits: 3,
    program_credits: 123,
    total_min_credits: 119,
  },
  sections: [
    {
      key: 'recognized',
      title: '已认定',
      confidence: 'high',
      action: '无需操作',
      cases: [item('CS101', '高等数学A(一)', 5, 92)],
    },
    {
      key: 'possible_overlap',
      title: '可能可折抵',
      confidence: 'medium',
      action: '带成绩单到教务处确认',
      cases: [item('CS102', '高等数学A(二)', 5, 84)],
    },
    {
      key: 'pending',
      title: '待认定',
      confidence: 'low',
      action: '由学院判断',
      cases: [item('SE001', '软件工程导论', 3, 85)],
    },
  ],
  self_check: [
    { name: '课程无遗漏', passed: true, detail: '41/41 门已归类' },
    { name: '学分守恒', passed: true, detail: '123.0 = 52.0 + 4.0 + 28.0 + 39.0' },
  ],
  disclaimer: '本清单仅供参考，最终以教务系统为准。当前为样例数据，不可用于真实毕业审核。',
  next_actions: [
    { step: 1, text: '登录教务系统核对', where: '教务系统' },
    { step: 2, text: '带成绩单到教务处确认', where: '明理楼 226' },
  ],
  printable: false,
}

describe('formatAuditSheet', () => {
  it('包含单据头、自检与免责声明', () => {
    const text = formatAuditSheet(SHEET)

    expect(text).toContain('转专业学分核对单')
    expect(text).toContain('计算机科学与技术')
    expect(text).toContain('[✓] 学分守恒')
    expect(text).toContain('样例数据，不可用于真实毕业审核')
    expect(text).toContain('教务系统')
  })

  it('每一类都带门数、置信度和该做什么', () => {
    const text = formatAuditSheet(SHEET)

    expect(text).toContain(`== 已认定（1 门 · ${CONFIDENCE_LABEL.high}）==`)
    expect(text).toContain(`== 可能可折抵（1 门 · ${CONFIDENCE_LABEL.medium}）==`)
    expect(text).toContain('该做什么：带成绩单到教务处确认')
  })

  it('列出门数与成绩', () => {
    const text = formatAuditSheet(SHEET)

    expect(text).toContain('- CS101 高等数学A(一) 5 学分 · 成绩 92')
    expect(text).toContain('- SE001 软件工程导论 3 学分 · 成绩 85')
  })

  it('成绩缺失时不编造数字', () => {
    const text = formatAuditSheet({
      ...SHEET,
      sections: [
        { ...SHEET.sections[0]!, cases: [item('CS101', '高等数学A(一)', 5, null)] },
      ],
    })

    expect(text).toContain('- CS101 高等数学A(一) 5 学分')
    expect(text).not.toContain('成绩 null')
  })

  it('原专业课程没有名称时用占位符，不编名字', () => {
    const text = formatAuditSheet({
      ...SHEET,
      sections: [
        { ...SHEET.sections[2]!, cases: [item('X1', '', 3, 80)] },
      ],
    })

    expect(text).toContain('- X1 （原专业课程） 3 学分')
  })
})
