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
