/**
 * SSE 解帧的边界测试。
 *
 * 这是全前端最容易写错、且错起来最隐蔽的地方：**绝不能假设“一次 read = 一帧”**。
 * 下面四条覆盖了真实会遇到的四种切法。
 */

import { describe, expect, it } from 'vitest'

import { drainFrames } from './stream'
import type { StreamEvent } from './types'

const frame = (payload: unknown) => `data: ${JSON.stringify(payload)}\n\n`

const delta = (text: string): StreamEvent => ({ type: 'delta', text })

describe('drainFrames', () => {
  it('切出完整帧并保留残余', () => {
    const buffer = frame(delta('甲')) + frame(delta('乙')) + 'data: {"type":"del'
    const { events, rest } = drainFrames(buffer)

    expect(events).toEqual([delta('甲'), delta('乙')])
    expect(rest).toBe('data: {"type":"del')
  })

  it('半帧跨 chunk：分两次喂，第二次才成帧', () => {
    const whole = frame(delta('跨块中文测试'))
    const cut = Math.floor(whole.length / 2)

    const first = drainFrames(whole.slice(0, cut))
    expect(first.events).toEqual([])
    expect(first.rest).toBe(whole.slice(0, cut))

    const second = drainFrames(first.rest + whole.slice(cut))
    expect(second.events).toEqual([delta('跨块中文测试')])
    expect(second.rest).toBe('')
  })

  it('一个 chunk 里含多帧', () => {
    const buffer = frame(delta('一')) + frame(delta('二')) + frame(delta('三'))
    expect(drainFrames(buffer).events).toEqual([delta('一'), delta('二'), delta('三')])
  })

  it('CRLF 帧分隔也能解析', () => {
    const buffer = 'data: {"type":"delta","text":"甲"}\r\n\r\n'
    expect(drainFrames(buffer).events).toEqual([delta('甲')])
  })

  it('忽略注释行与非 data 字段', () => {
    const buffer = ': 这是一条心跳\nevent: message\nid: 7\ndata: {"type":"delta","text":"甲"}\n\n'
    expect(drainFrames(buffer).events).toEqual([delta('甲')])
  })

  it('坏帧不影响后续帧', () => {
    const buffer = 'data: {不是合法 JSON}\n\n' + frame(delta('好的'))
    expect(drainFrames(buffer).events).toEqual([delta('好的')])
  })

  it('正文里的换行不会破坏帧边界', () => {
    // JSON.stringify 会把真实换行转义，所以帧里只剩一个 \n\n
    const payload = delta('第一行\n第二行')
    const buffer = frame(payload)
    expect(buffer.split('\n\n').length).toBe(2)
    expect(drainFrames(buffer).events).toEqual([payload])
  })

  it('空缓冲区不产出事件', () => {
    expect(drainFrames('').events).toEqual([])
    expect(drainFrames('\n\n').events).toEqual([])
  })
})
