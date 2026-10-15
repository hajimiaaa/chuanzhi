/**
 * 打字机 —— 用"追赶缓冲"，**不在真实流上再叠一层逐字定时器**。
 *
 * 维护两个量：
 *   target —— 已经收到的全部文本（只由 delta 追加，永不超前）
 *   shown  —— 正在显示的文本
 * rAF 每帧看 gap，按 1~3 字推进。
 *
 * 关键性质：**显示的字符数永远 ≤ 已收到的字符数。**
 * 所以它既是打字机效果，又不可能造假 —— 后端慢它就慢，后端快它就追赶。
 * 真实的 LLM 中文分块是几个字一跳，直接渲染读起来是"抽搐"，追赶缓冲把它变成匀速。
 */

import { useEffect, useRef, useState } from 'react'

interface Props {
  /** 已收到的全部文本 */
  text: string
  /** 流是否已结束 —— 结束后直接补齐，不再有节奏延迟 */
  done?: boolean
}

const CATCH_UP_THRESHOLD = 12

export function Typewriter({ text, done = false }: Props) {
  const [shown, setShown] = useState('')
  const targetRef = useRef(text)
  const frameRef = useRef(0)

  targetRef.current = text

  useEffect(() => {
    if (done) {
      setShown(targetRef.current)
      return
    }

    const tick = () => {
      setShown((current) => {
        const target = targetRef.current
        const gap = target.length - current.length
        if (gap <= 0) return current
        const step = gap > CATCH_UP_THRESHOLD ? 3 : 1
        return target.slice(0, current.length + step)
      })
      frameRef.current = requestAnimationFrame(tick)
    }

    frameRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameRef.current)
  }, [done])

  const streaming = !done && shown.length < text.length

  return (
    <div className="typewriter">
      <p className="typewriter__text">
        {shown}
        {streaming && <span className="typewriter__caret" aria-hidden="true" />}
      </p>
    </div>
  )
}
