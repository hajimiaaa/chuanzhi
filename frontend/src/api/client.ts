/**
 * HTTP 客户端：超时、取消、错误分类。
 *
 * 关键设计：把"后端没起"与"后端报错"分成两类错误，前端才能给出精确的提示 ——
 * 这正是「不白屏」的前提。走 vite proxy 的话这个区分会变得含糊
 * （请求打到 dev server 拿到 500/504，分不清是代理挂了还是后端挂了），
 * 所以我们直连后端、依赖后端的 CORS 白名单。
 */

/** 用 127.0.0.1 而不是 localhost：Windows 上 localhost 可能先解析到 ::1，而 uvicorn 默认只监听 IPv4 */
const RAW = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

/** 空串 = 用相对路径（仅在你另配了 vite proxy 时有意义） */
export const API_BASE = RAW.replace(/\/+$/, '')

export const DEFAULT_TIMEOUT_MS = 8000

/** 后端返回了非 2xx。422 的 body.detail 是 Pydantic 的逐字段说明，必须原样展示。 */
export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }

  /** 把后端 detail（字符串或 Pydantic 的结构化数组）压成一行可读文本 */
  detailText(): string {
    const body = this.body
    if (body == null) return this.message
    if (typeof body === 'string') return body
    if (typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) {
        return detail
          .map((d) => {
            if (d && typeof d === 'object' && 'loc' in d && 'msg' in d) {
              const loc = (d as { loc: unknown[] }).loc.join('.')
              return `${loc}: ${(d as { msg: string }).msg}`
            }
            return JSON.stringify(d)
          })
          .join('；')
      }
    }
    return JSON.stringify(body)
  }
}

/** 请求根本没到后端（后端没起、DNS、连接被拒、超时） */
export class NetworkError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options)
    this.name = 'NetworkError'
  }
}

export interface RequestOptions {
  signal?: AbortSignal
  timeoutMs?: number
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  { signal, timeoutMs = DEFAULT_TIMEOUT_MS }: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController()
  let timedOut = false

  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const forwardAbort = () => controller.abort()
  signal?.addEventListener('abort', forwardAbort, { once: true })

  try {
    let response: Response
    try {
      response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal })
    } catch (cause) {
      // 上游主动取消：原样抛出，交给调用方按"取消"处理，不要包装成网络错误
      if (signal?.aborted) throw cause
      if (timedOut) {
        throw new NetworkError(`请求超时（${timeoutMs}ms）：${API_BASE}${path}`, { cause })
      }
      throw new NetworkError(
        `连不上后端 ${API_BASE}。请确认已在 backend/ 目录执行 uvicorn app.main:app --port 8000`,
        { cause },
      )
    }

    const text = await response.text()
    let parsed: unknown = null
    if (text) {
      try {
        parsed = JSON.parse(text)
      } catch {
        parsed = text
      }
    }

    if (!response.ok) {
      throw new ApiError(response.status, parsed)
    }

    return parsed as T
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forwardAbort)
  }
}

/** 把任意异常压成一句给用户看的中文。422 的 detail 必须原样转发（后端刻意的"响亮失败"）。 */
export function describeError(cause: unknown): string {
  if (cause instanceof ApiError) return `后端返回 ${cause.status}：${cause.detailText()}`
  if (cause instanceof NetworkError) return cause.message
  return cause instanceof Error ? cause.message : String(cause)
}

export function getJson<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>(path, { method: 'GET' }, options)
}

export function postJson<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  return request<T>(
    path,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    options,
  )
}
