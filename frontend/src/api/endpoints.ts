/**
 * 后端 JSON 接口的薄封装。路径与响应类型一一对应 backend/app/main.py。
 *
 * 流式接口（/api/llm/explain/stream）在 api/stream.ts 里单独处理，不走这里。
 */

import { getJson, postJson, type RequestOptions } from './client'
import type {
  CreditGapIn,
  CreditGapResponse,
  ExplainResponse,
  HealthResponse,
  MajorsDoc,
  PlanIn,
  Program,
  ProgramListResponse,
  RuleCategory,
  RuleDoc,
  RuleListResponse,
  SamplePlanResponse,
  SuggestIn,
  SuggestResponse,
  ValidateResponse,
} from './types'

export const getHealth = (options?: RequestOptions) =>
  getJson<HealthResponse>('/api/health', options)

/** 原样透传，含 source 溯源块（学校 / 原始文件 / 生成脚本） */
export const getMajors = (options?: RequestOptions) => getJson<MajorsDoc>('/api/majors', options)

export const getPrograms = (options?: RequestOptions) =>
  getJson<ProgramListResponse>('/api/programs', options)

export const getProgram = (programId: string, options?: RequestOptions) =>
  getJson<Program>(`/api/programs/${encodeURIComponent(programId)}`, options)

export const getSamplePlan = (programId: string, options?: RequestOptions) =>
  getJson<SamplePlanResponse>(
    `/api/programs/${encodeURIComponent(programId)}/sample-plan`,
    options,
  )

export const validatePlan = (body: PlanIn, options?: RequestOptions) =>
  postJson<ValidateResponse>('/api/plan/validate', body, options)

export const suggestOrder = (body: SuggestIn, options?: RequestOptions) =>
  postJson<SuggestResponse>('/api/plan/suggest-order', body, options)

export const explainPlan = (body: PlanIn, options?: RequestOptions) =>
  postJson<ExplainResponse>('/api/llm/explain', body, options)

/** 补修/重修清单。不做跨专业折抵——`pending` 里的课只能标「待认定」。 */
export const creditGap = (body: CreditGapIn, options?: RequestOptions) =>
  postJson<CreditGapResponse>('/api/plan/credit-gap', body, options)

export const getRules = (options?: RequestOptions) =>
  getJson<RuleListResponse>('/api/rules', options)

/**
 * 传 category 时由**后端**过滤，响应里的 `filter.matched` 回显命中条数。
 * 非法 category 后端返回 422（不是静默忽略），所以这里不做本地校验。
 */
export const getRule = (
  ruleId: string,
  category?: RuleCategory | null,
  options?: RequestOptions,
) => {
  const query = category ? `?category=${encodeURIComponent(category)}` : ''
  return getJson<RuleDoc>(`/api/rules/${encodeURIComponent(ruleId)}${query}`, options)
}
