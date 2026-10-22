/**
 * 转专业规则的登记表与展示派生 —— 全是纯函数，可在 node 环境直接单测。
 *
 * 与 lib/conflictMeta.ts 同一条纪律：**未知枚举不静默变空白**。
 * 后端 models.py 的 RULE_CATEGORIES / RULE_VERDICTS 会增长，
 * "新类别悄悄不显示"正是本项目一直在防的那种静默假阴性 ——
 * 所以这里一律回退成原样字符串，并在控制台提醒一次。
 *
 * 分组顺序也在这里：`RULE_CATEGORY_ORDER` 与后端一致，**不依赖接口返回顺序**。
 * 顺序本身是语义 —— 学生就是按「能不能转 → 挂科 → 分数 → 考核 → 专业 → 校区」
 * 这条路径一路查下来的。
 */

import type { Provision, RuleCategory, RuleGap, RuleGapStatus, RuleStats, RuleVerdict } from '@/api/types'
import { RULE_CATEGORIES } from '@/api/types'
import { VERDICT_COLOR } from './colors'

export const RULE_CATEGORY_ORDER: readonly RuleCategory[] = RULE_CATEGORIES

/** 类别短名：芯片与分组标题用 */
export const CATEGORY_LABEL: Record<RuleCategory, string> = {
  eligibility: '准入情形',
  academic_record: '挂科要求',
  score_threshold: '分数门槛',
  assessment_method: '考核方式',
  major_restriction: '专业限制',
  campus_restriction: '校区限制',
  quota: '次数与志愿',
  credit_recognition: '学分认定',
}

/** 类别长问句：空态与分组说明用 —— 学生脑子里的问题，比"类别名"更好懂 */
export const CATEGORY_QUESTION: Record<RuleCategory, string> = {
  eligibility: '哪些情形下可以转专业？需要谁批准？',
  academic_record: '已修读的课程必须全部合格吗？',
  score_threshold: '绩点、单科成绩、通识课分数线有要求吗？',
  assessment_method: '要笔试还是面试？什么情况下才会启动考核？',
  major_restriction: '哪些专业不能转到普通类？',
  campus_restriction: '跨校区转专业有额外限制吗？',
  quota: '最多能转几次？能报几个志愿？',
  credit_recognition: '转过去之后，原专业的学分怎么算？',
}

export const VERDICT_LABEL: Record<RuleVerdict, string> = {
  deny: '禁止',
  require: '要求',
  allow: '允许',
  limit: '上限',
  conditional: '条件触发',
  info: '说明',
}

export const VERDICT_ICON: Record<RuleVerdict, string> = {
  deny: '✕',
  require: '!',
  allow: '✓',
  limit: '#',
  conditional: '?',
  info: 'i',
}

export const GAP_STATUS_LABEL: Record<RuleGapStatus, string> = {
  not_available: '通知未规定',
  partial: '部分缺失',
}

// ---------- 未知枚举的安全回退 ----------

const warned = new Set<string>()

function warnOnce(value: string, hint: string) {
  if (warned.has(value)) return
  warned.add(value)
  console.warn(`[ruleMeta] 未登记的${hint} "${value}"，已按原样显示。请同步 lib/ruleMeta.ts`)
}

export function categoryLabel(category: string): string {
  if (category in CATEGORY_LABEL) return CATEGORY_LABEL[category as RuleCategory]
  warnOnce(category, '规则类别')
  return category
}

export function categoryQuestion(category: string): string {
  if (category in CATEGORY_QUESTION) return CATEGORY_QUESTION[category as RuleCategory]
  warnOnce(category, '规则类别')
  return ''
}

export function verdictMeta(verdict: string): { label: string; icon: string; color: string } {
  if (verdict in VERDICT_LABEL) {
    const known = verdict as RuleVerdict
    return { label: VERDICT_LABEL[known], icon: VERDICT_ICON[known], color: VERDICT_COLOR[known] ?? '' }
  }
  warnOnce(verdict, '判定类型')
  return { label: verdict, icon: '·', color: '' }
}

export function gapStatusLabel(status: string): string {
  if (status in GAP_STATUS_LABEL) return GAP_STATUS_LABEL[status as RuleGapStatus]
  warnOnce(status, '缺口状态')
  return status
}

// ---------- 展示派生 ----------

/**
 * 按固定类别顺序分组，**跳过空组**；未知类别排在已知类别之后、保持出现顺序。
 *
 * 未知类别不丢：后端新增一类而前端没跟上的时候，条款仍然要显示出来。
 */
export function groupProvisions(
  provisions: Provision[],
): Array<readonly [string, Provision[]]> {
  const map = new Map<string, Provision[]>()
  for (const provision of provisions) {
    map.set(provision.category, [...(map.get(provision.category) ?? []), provision])
  }

  const known = RULE_CATEGORY_ORDER.filter((category) => map.has(category))
  const unknown = [...map.keys()].filter(
    (category) => !(RULE_CATEGORY_ORDER as readonly string[]).includes(category),
  )

  return [...known, ...unknown].map((category) => [category, map.get(category)!] as const)
}

/** 比例 -> 百分比文案。0.3 -> "30%"，0.125 -> "12.5%"（避开浮点尾巴） */
export function formatPercent(ratio: number): string {
  const pct = Math.round(ratio * 10000) / 100
  return `${pct}%`
}

/**
 * 把结构化载荷翻译成人话。刻意返回数组而不是拼好的一段：
 * 一条条款可能同时有「受限方向 + 裁量」两层意思，分行才读得清。
 */
export function describeProvision(provision: Provision): string[] {
  const lines: string[] = []

  if (provision.restricted_from.length > 0 && provision.restricted_to.length > 0) {
    lines.push(`${provision.restricted_from.join(' / ')} → ${provision.restricted_to.join(' / ')}`)
  } else if (provision.restricted_from.length > 0) {
    lines.push(`限：${provision.restricted_from.join(' / ')}`)
  } else if (provision.restricted_to.length > 0) {
    lines.push(`转入：${provision.restricted_to.join(' / ')}`)
  }

  if (provision.max_count !== null) {
    lines.push(`上限 ${provision.max_count}`)
  }

  if (provision.ratio !== null) {
    lines.push(
      provision.category === 'assessment_method'
        ? `转入人数超过招生数的 ${formatPercent(provision.ratio)} 时启动考核`
        : `比例阈值 ${formatPercent(provision.ratio)}`,
    )
  }

  if (provision.factors.length > 0) {
    lines.push(`考量：${provision.factors.join('、')}`)
  }

  if (provision.defers_to) {
    lines.push(`依据：${provision.defers_to}`)
  }

  if (provision.discretionary) {
    lines.push('兜底条款，由学校审核裁量')
  }

  return lines
}

export function gapByCategory(gaps: RuleGap[]): Map<string, RuleGap> {
  return new Map(gaps.map((gap) => [gap.category, gap]))
}

/** 计数为 0 的类别 —— 它们不是"没有规则"，而是"通知里没规定"，在界面上要单独说 */
export function categoriesWithoutProvisions(stats: RuleStats): RuleCategory[] {
  return RULE_CATEGORY_ORDER.filter((category) => (stats.by_category[category] ?? 0) === 0)
}
