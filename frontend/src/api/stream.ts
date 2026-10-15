/**
 * SSE 流式读取。
 *
 * 为什么不用 EventSource：
 *   - 它只支持 GET，而我们的请求体是复杂的 plan JSON
 *   - 它不能设请求头、不能发 body
 *   - 它的自动重连在这里是负资产（POST 流的重连语义不清）
 * → 用 fetch + ReadableStream，自己解帧。
 *
 * ⚠️ 这是全前端最容易写错、且错起来最隐蔽的地方，所以解帧逻辑抽成纯函数 `drainFrames`
 *    并用 vitest 覆盖半帧 / 多帧 / CRLF / 跨块汉字四种边界。
 */

import { API_BASE, ApiError, NetworkError } from './client'
import type { PlanIn, StreamEvent } from './types'

/**
 * 从缓冲区里尽量多地切出完整帧。
 *
 * **绝不能假设"一次 read = 一帧"** —— 一帧可能被拆到两个 chunk 里，
 * 一个 chunk 里也可能有 3 帧。缓冲区 + indexOf('\n\n') 循环是唯一正确的写法。
 *
 * @returns events 本次切出的事件；rest 尚未成帧的残余（调用方需保存并在下次拼接）
 */
export function drainFrames(buffer: string): { events: StreamEvent[]; rest: string } {
  // 归一化 CRLF：本机后端发 \n\n，但代理/中间件可能改写
  let rest = buffer.replace(/\r\n/g, '\n')
  const events: StreamEvent[] = []

  let idx: number
  while ((idx = rest.indexOf('\n\n')) >= 0) {
    const frame = rest.slice(0, idx)
    rest = rest.slice(idx + 2)

    for (const line of frame.split('\n')) {
      // 忽略 ": 心跳" 之类的注释行与 event:/id: 字段
      if (!line.startsWith('data:')) continue
      const payload = line.slice(5).trim()
      if (!payload) continue
      try {
        events.push(JSON.parse(payload) as StreamEvent)
      } catch {
        // 单帧解析失败不炸整条流
        console.warn('[stream] 无法解析的 SSE 帧已跳过:', payload.slice(0, 200))
      }
    }
  }

  return { events, rest }
}

export interface StreamHandlers {
  onEvent: (event: StreamEvent) => void
  signal?: AbortSignal
}

export async function explainStream(body: PlanIn, { onEvent, signal }: StreamHandlers): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/llm/explain/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new NetworkError(
      `连不上后端 ${API_BASE}。请确认已在 backend/ 目录执行 uvicorn app.main:app --port 8000`,
      { cause },
    )
  }

  if (!response.ok) {
    const text = await response.text()
    let parsed: unknown = text
    try {
      parsed = JSON.parse(text)
    } catch {
      /* 保留原文 */
    }
    throw new ApiError(response.status, parsed)
  }
  if (!response.body) {
    throw new NetworkError('响应没有 body，无法读取流')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8') // 必须显式指定，不能靠默认值
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      // stream: true 处理跨块的多字节汉字：中文 3 字节，块边界可能落在字中间，
      // 不加这个参数会偶发出现 U+FFFD 替换字符
      buffer += decoder.decode(value, { stream: true })
      const { events, rest } = drainFrames(buffer)
      buffer = rest
      for (const event of events) onEvent(event)
    }

    buffer += decoder.decode()
    // 收尾：容忍最后一帧缺少末尾空行
    for (const event of drainFrames(`${buffer}\n\n`).events) onEvent(event)
  } finally {
    reader.cancel().catch(() => {
      /* 已结束或已取消，忽略 */
    })
  }
}
