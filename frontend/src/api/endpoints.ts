/** 后端 8 个接口的薄封装。路径与响应类型一一对应 backend/app/main.py。 */

import { getJson, postJson, type RequestOptions } from './client'
import type {
  ExplainResponse,
  HealthResponse,
  MajorsDoc,
  PlanIn,
  Program,
  ProgramListResponse,
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
