/**
 * 与后端契约逐一对应的类型。
 *
 * ⚠️ 字段名必须**逐字符**对上后端：所有请求模型都是 `extra="forbid"`，
 * 把 `course_code` 写成 `courseCode` 会被响亮地 422（这是后端刻意的设计，
 * 本项目最大的失败模式是"静默的假阴性"，宁可报错也不要静默落进默认值）。
 *
 * 来源：backend/app/models.py 的各 to_dict()、backend/app/schemas.py、backend/app/main.py
 */

export type Severity = 'error' | 'warning' | 'info'

export interface Summary {
  error: number
  warning: number
  info: number
  total: number
}

export const CATEGORIES = ['必修', '专业选修', '通识', '实践'] as const
export type Category = (typeof CATEGORIES)[number]

export interface TimeSlot {
  day: number // 1=周一 … 7=周日
  start_period: number
  end_period: number
  weeks: number[]
}

export interface Course {
  code: string
  name: string
  credits: number
  category: string
  prerequisites: string[]
  /** 空数组 = 未标注，视为每学期均可开课 */
  terms: number[]
  /** 样例培养方案里为空 —— 上课时段来自排课表，不是培养方案的字段 */
  slots: TimeSlot[]
}

export interface CreditRule {
  category: string
  min_credits: number
}

export type DataStatus = 'sample' | 'official'
export type ScheduleStatus = 'available' | 'not_available'

export interface Program {
  id: string
  name: string
  college: string
  campus: string
  data_status: DataStatus
  note: string
  catalog_ref: string
  schedule_status: ScheduleStatus
  total_terms: number
  total_min_credits: number
  /** 0 = 未设上限 */
  max_credits_per_term: number
  credit_rules: CreditRule[]
  courses: Course[]
}

export interface ProgramSummary {
  id: string
  name: string
  college: string
  campus: string
  data_status: DataStatus
  schedule_status: ScheduleStatus
  total_terms: number
  total_min_credits: number
  course_count: number
}

/**
 * 后端已按 `(KIND_ORDER 序, severity, term, course_codes, message)` 排好序，
 * 前端可直接顺序渲染，不需要再排。
 */
export interface Conflict {
  kind: string
  severity: Severity
  message: string
  course_codes: string[]
  /** 非学期类冲突为 0 */
  term: number
  /** 与 actual 搭配，用于画「12 / 40 学分」进度条；无该语义时为 null */
  expected: number | null
  actual: number | null
}

export interface PlanItem {
  course_code: string
  term: number
}

export interface CompletedCourse {
  course_code: string
  /** 课程名称（可选）：跨专业「同名同学分、课号不同」的课要靠它识别成「可能可折抵」 */
  name: string
  credits: number
  grade: number | string | null
  term: string
  passed: boolean | null
}

export interface PlanIn {
  program_id: string
  items: PlanItem[]
  completed: CompletedCourse[]
}

export interface SuggestIn {
  program_id: string
  max_credits_per_term: number | null
}

export interface PlanSuggestion {
  items: PlanItem[]
  /** 排不下的课程 —— 后端刻意显式返回，不静默丢弃 */
  unscheduled: string[]
  notes: string[]
}

export interface ValidateResponse {
  program_id: string
  data_status: DataStatus
  schedule_status: ScheduleStatus
  summary: Summary
  conflicts: Conflict[]
}

export interface SamplePlanResponse {
  program_id: string
  data_status: DataStatus
  schedule_status: ScheduleStatus
  plan: PlanSuggestion
}

export interface SuggestResponse {
  program_id: string
  plan: PlanSuggestion
}

export interface HealthResponse {
  status: string
  version: string
  llm: { provider: string; mode: 'mock' | 'live' }
  data: { programs: number | null; majors: number | null }
}

export interface Major {
  name: string
  level: string
  tags?: string[]
}

export interface College {
  name: string
  campus: string
  majors: Major[]
}

export interface MajorsDoc {
  source: {
    school: string
    title: string
    origin: string
    raw_file: string
    generator: string
  }
  campuses: string[]
  stats: { colleges: number; majors: number }
  colleges: College[]
}

export interface ProgramListResponse {
  items: ProgramSummary[]
}

export interface ExplainResponse {
  program_id: string
  summary: Summary
  provider: string
  text: string
  error: string
}

/** SSE 事件（POST /api/llm/explain/stream）。类型在 JSON 的 type 字段里，帧只有 data: 前缀。 */
export type StreamEvent =
  | { type: 'meta'; provider: string; program_id: string; conflicts: number; summary: Summary }
  | { type: 'thinking'; text: string }
  | { type: 'delta'; text: string }
  | { type: 'error'; message: string }
  | { type: 'done'; provider: string; chars: number; chunks: number; error: string }

// ---------- 转专业规则（GET /api/rules、GET /api/rules/{id}）----------
//
// 顺序与 backend/app/models.py 的 RULE_CATEGORIES 一致。前端按这个顺序分组，
// 不依赖后端返回的条款顺序 —— 顺序本身是语义（学生按这条路径查下来）。

export const RULE_CATEGORIES = [
  'eligibility',
  'academic_record',
  'score_threshold',
  'assessment_method',
  'major_restriction',
  'campus_restriction',
  'quota',
  'credit_recognition',
] as const

export type RuleCategory = (typeof RULE_CATEGORIES)[number]

export type RuleVerdict = 'deny' | 'require' | 'allow' | 'limit' | 'conditional' | 'info'
export type RuleGapStatus = 'not_available' | 'partial'
export type RuleDocType = 'school_notice' | 'college_plan' | 'credit_recognition_policy'

/** GET /api/rules 的列表项（后端 RuleDoc.summary()） */
export interface RuleSummary {
  id: string
  doc_type: RuleDocType
  data_status: DataStatus
  title: string
  issued_by: string
  issued_date: string
  raw_file: string
  provision_count: number
  gap_count: number
}

export interface RuleSource {
  school: string
  title: string
  origin: string
  raw_file: string
  generator: string
  issuer: string
  issued_date: string
  doc_no: string
}

export interface RuleScope {
  grade: string
  student_types: string[]
}

/** 一条可检索的规则条款。`quote` 是原文逐字引用，校验脚本会回原文复核。 */
export interface Provision {
  id: string
  category: RuleCategory
  verdict: RuleVerdict
  /** 原文条号，如「一、（二）1.（1）」 */
  clause: string
  quote: string
  restricted_from: string[]
  restricted_to: string[]
  factors: string[]
  /** 触发比例，如 0.3；无该语义时为 null */
  ratio: number | null
  /** 次数/志愿数上限；无该语义时为 null */
  max_count: number | null
  /** 指向另一份文件；空串表示没有 */
  defers_to: string
  /** true = 兜底条款，由学校/学院裁量 */
  discretionary: boolean
}

export interface RuleTimelineStep {
  id: string
  label: string
  /** ISO 日期，如 2025-02-21 */
  deadline: string
  clause: string
  quote: string
}

/** 一处缺口：这类规则通知里没有，以及为什么没有、该去哪里找。 */
export interface RuleGap {
  category: RuleCategory
  status: RuleGapStatus
  detail: string
  evidence_clause: string
  /** 反证：这些词在原文里必须不出现，校验脚本会真的去查 */
  absent_keywords: string[]
  where_to_find: string
}

export interface RuleStats {
  provisions: number
  /** 8 个键恒定存在，计数为 0 也是信息 */
  by_category: Record<RuleCategory, number>
  gaps: number
}

export interface RuleDoc {
  id: string
  doc_type: RuleDocType
  data_status: DataStatus
  title: string
  source: RuleSource
  applies_to: RuleScope
  /** 描述整份文件，**不随 category 过滤缩小** */
  stats: RuleStats
  provisions: Provision[]
  timeline: RuleTimelineStep[]
  gaps: RuleGap[]
  note: string
  /** 恒定存在的键：未过滤为 null；过滤时回显命中条数，避免与 stats 看起来矛盾 */
  filter: { category: RuleCategory; matched: number } | null
}

export interface RuleListResponse {
  items: RuleSummary[]
}

// ---------- 补修/重修清单（POST /api/plan/credit-gap）----------
//
// 这是「学分折抵」里**不需要认定办法**的那一半：课号对得上的算得出来，
// 对不上的（原专业课程）归入 pending，等学校的《学分认定管理办法》。

export interface CreditCase {
  course_code: string
  /** 空串表示这门课不在目标培养方案的课程库里 */
  name: string
  credits: number
  category: string
  grade: number | string | null
  terms: number[]
  prerequisites: string[]
}

export interface CreditGapSummary {
  recognized: number
  retake: number
  possible_overlap: number
  remedial: number
  pending: number
  recognized_credits: number
  retake_credits: number
  possible_overlap_credits: number
  remedial_credits: number
  pending_credits: number
  program_credits: number
  total_min_credits: number
}

export interface CreditGapIn {
  program_id: string
  completed: CompletedCourse[]
}

export interface CreditGapResponse {
  program_id: string
  data_status: DataStatus
  summary: CreditGapSummary
  recognized: CreditCase[]
  retake: CreditCase[]
  possible_overlap: CreditCase[]
  remedial: CreditCase[]
  pending: CreditCase[]
  suggested: PlanSuggestion
  notes: string[]
}

// ---------- 核对单（POST /api/plan/audit-sheet）----------

export type AuditConfidence = 'high' | 'medium' | 'low'

export interface AuditSection {
  key: string
  title: string
  confidence: AuditConfidence
  action: string
  cases: CreditCase[]
}

export interface AuditCheck {
  name: string
  passed: boolean
  detail: string
}

export interface AuditAction {
  step: number
  text: string
  where: string
}

export interface AuditSheetProgram {
  id: string
  name: string
  college: string
  data_status: DataStatus
  catalog_ref: string
  note: string
}

export interface AuditSheetResponse {
  program: AuditSheetProgram
  generated_at: string
  engine_version: string
  summary: CreditGapSummary
  sections: AuditSection[]
  self_check: AuditCheck[]
  disclaimer: string
  next_actions: AuditAction[]
  /** 样例数据下为 false：不生成一张"看起来能签字"的单子 */
  printable: boolean
}
