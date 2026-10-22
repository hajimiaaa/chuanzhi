/**
 * 规则登记表与展示派生的单测。
 *
 * 这里测的不是组件，而是"后端给了什么 → 界面该说什么"的映射。
 * 组件测试需要 jsdom 与 testing-library，而本仓库的 vitest 是 node 环境、只收
 * `*.test.ts`；把这些逻辑抽成纯函数，既守住了现有工程约定，也更好断言。
 */

import { describe, expect, it, vi } from 'vitest'

import type { Provision, RuleCategory, RuleStats } from '@/api/types'
import {
  CATEGORY_LABEL,
  CATEGORY_QUESTION,
  GAP_STATUS_LABEL,
  RULE_CATEGORY_ORDER,
  categoriesWithoutProvisions,
  categoryLabel,
  describeProvision,
  formatPercent,
  gapByCategory,
  gapStatusLabel,
  groupProvisions,
  verdictMeta,
} from './ruleMeta'

function provision(overrides: Partial<Provision> = {}): Provision {
  return {
    id: 'p1',
    category: 'academic_record',
    verdict: 'require',
    clause: '一、（一）',
    quote: '原文引用',
    restricted_from: [],
    restricted_to: [],
    factors: [],
    ratio: null,
    max_count: null,
    defers_to: '',
    discretionary: false,
    ...overrides,
  }
}

function stats(overrides: Partial<Record<RuleCategory, number>> = {}): RuleStats {
  const byCategory = Object.fromEntries(
    RULE_CATEGORY_ORDER.map((category) => [category, 0]),
  ) as Record<RuleCategory, number>
  Object.assign(byCategory, overrides)
  const provisions = Object.values(byCategory).reduce((sum, n) => sum + n, 0)
  return { provisions, by_category: byCategory, gaps: 0 }
}

describe('groupProvisions', () => {
  it('按固定类别顺序分组，与输入顺序无关', () => {
    const groups = groupProvisions([
      provision({ id: 'a', category: 'quota' }),
      provision({ id: 'b', category: 'eligibility' }),
    ])

    expect(groups.map(([category]) => category)).toEqual(['eligibility', 'quota'])
  })

  it('跳过没有条款的类别', () => {
    const groups = groupProvisions([provision({ category: 'major_restriction' })])

    expect(groups).toHaveLength(1)
    expect(groups[0]![0]).toBe('major_restriction')
  })

  it('同一类别内保持原顺序', () => {
    const groups = groupProvisions([
      provision({ id: 'first' }),
      provision({ id: 'second' }),
    ])

    expect(groups[0]![1].map((item) => item.id)).toEqual(['first', 'second'])
  })

  it('未知类别不丢，排在已知类别之后', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    const groups = groupProvisions([
      provision({ category: 'brand_new' as RuleCategory }),
      provision({ category: 'quota' }),
    ])

    expect(groups.map(([category]) => category)).toEqual(['quota', 'brand_new'])
  })
})

describe('describeProvision', () => {
  it('受限方向：从哪些类别转到哪些类别', () => {
    const lines = describeProvision(
      provision({ restricted_from: ['艺术类专业', '体育类专业'], restricted_to: ['普通类专业'] }),
    )

    expect(lines).toEqual(['艺术类专业 / 体育类专业 → 普通类专业'])
  })

  it('只有转出限制时说明「限」', () => {
    expect(describeProvision(provision({ restricted_from: ['专升本类'] }))).toEqual([
      '限：专升本类',
    ])
  })

  it('次数/志愿上限', () => {
    expect(describeProvision(provision({ category: 'quota', max_count: 1 }))).toEqual([
      '上限 1',
    ])
  })

  it('考核触发比例', () => {
    const lines = describeProvision(
      provision({ category: 'assessment_method', ratio: 0.3 }),
    )

    expect(lines).toEqual(['转入人数超过招生数的 30% 时启动考核'])
  })

  it('非考核类别的比例用中性说法', () => {
    expect(describeProvision(provision({ category: 'quota', ratio: 0.25 }))).toEqual([
      '比例阈值 25%',
    ])
  })

  it('考量因素逐项列出', () => {
    const lines = describeProvision(
      provision({ factors: ['高考成绩', '单科成绩'] }),
    )

    expect(lines).toEqual(['考量：高考成绩、单科成绩'])
  })

  it('指向另一份文件时写明依据', () => {
    const lines = describeProvision(
      provision({ defers_to: '《学校学分认定管理办法》' }),
    )

    expect(lines).toEqual(['依据：《学校学分认定管理办法》'])
  })

  it('兜底条款标明裁量', () => {
    const lines = describeProvision(
      provision({ category: 'major_restriction', verdict: 'deny', discretionary: true }),
    )

    expect(lines).toEqual(['兜底条款，由学校审核裁量'])
  })

  it('没有结构化载荷时返回空数组（不编造解释）', () => {
    expect(describeProvision(provision())).toEqual([])
  })
})

describe('formatPercent', () => {
  it('避开浮点尾巴', () => {
    expect(formatPercent(0.3)).toBe('30%')
    expect(formatPercent(0.125)).toBe('12.5%')
    expect(formatPercent(1)).toBe('100%')
  })
})

describe('categoriesWithoutProvisions', () => {
  it('列出计数为 0 的类别（零本身就是信息）', () => {
    const missing = categoriesWithoutProvisions(
      stats({ major_restriction: 3, eligibility: 6 }),
    )

    expect(missing).toContain('score_threshold')
    expect(missing).toContain('campus_restriction')
    expect(missing).not.toContain('major_restriction')
  })

  it('按固定顺序返回', () => {
    expect(categoriesWithoutProvisions(stats())).toEqual([...RULE_CATEGORY_ORDER])
  })
})

describe('gapByCategory', () => {
  it('按类别索引缺口', () => {
    const map = gapByCategory([
      {
        category: 'score_threshold',
        status: 'not_available',
        detail: '通知未规定',
        evidence_clause: '',
        absent_keywords: ['分数线'],
        where_to_find: '学院方案',
      },
    ])

    expect(map.get('score_threshold')?.where_to_find).toBe('学院方案')
    expect(map.get('campus_restriction')).toBeUndefined()
  })
})

describe('登记表完备性', () => {
  it('后端的每个类别都有短名与长问句', () => {
    for (const category of RULE_CATEGORY_ORDER) {
      expect(CATEGORY_LABEL[category]).toBeTruthy()
      expect(CATEGORY_QUESTION[category]).toBeTruthy()
    }
  })

  it('每种判定都有文字、图标与颜色 —— 颜色永不单独承载语义', () => {
    for (const verdict of ['deny', 'require', 'allow', 'limit', 'conditional', 'info']) {
      const meta = verdictMeta(verdict)
      expect(meta.label).toBeTruthy()
      expect(meta.icon).toBeTruthy()
      expect(meta.color).toBeTruthy()
    }
  })

  it('两种缺口状态都有中文名', () => {
    for (const status of ['not_available', 'partial']) {
      expect(gapStatusLabel(status)).toBeTruthy()
      expect(GAP_STATUS_LABEL[status as keyof typeof GAP_STATUS_LABEL]).toBeTruthy()
    }
  })

  it('后端新增枚举时原样显示并提醒，不静默变空白', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(categoryLabel('brand_new')).toBe('brand_new')
    expect(verdictMeta('mystery').label).toBe('mystery')
    expect(gapStatusLabel('half_known')).toBe('half_known')
    expect(warn).toHaveBeenCalled()
  })
})
