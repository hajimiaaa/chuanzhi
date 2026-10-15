/**
 * 「思考可视化」。
 *
 * 显示的每一个量都是**真流式才可能产生的**：
 *   - 阶段步骤的内容来自服务端的 meta / thinking 事件（是 check_all 的真实结果，不是前端编的进度条）
 *   - 首字延迟、已收块数、已生成字数是逐帧跳动的实测值
 * 假的打字机动画做不出「首字 142ms · 19 块 · 186 字」这样的读数。
 */

import { formatMs } from '@/lib/format'

export type StreamStatus = 'idle' | 'streaming' | 'done' | 'error'

interface Props {
  status: StreamStatus
  thinking: string
  conflicts: number | null
  summary: { error: number; warning: number; info: number } | null
  firstByteMs: number
  chunks: number
  chars: number
  provider: string
}

export function ThinkingTrace({
  status,
  thinking,
  conflicts,
  summary,
  firstByteMs,
  chunks,
  chars,
  provider,
}: Props) {
  const started = status !== 'idle'
  const conflictDone = conflicts !== null
  const generating = status === 'streaming'
  const done = status === 'done'

  return (
    <div className="trace">
      <ol className="trace__steps">
        <Step label="解析规划" state={started ? 'done' : 'pending'} />
        <Step
          label={conflictDone ? `检测冲突 · ${conflicts} 条` : '检测冲突'}
          state={conflictDone ? 'done' : started ? 'active' : 'pending'}
          hint={
            summary
              ? `错误 ${summary.error} / 警告 ${summary.warning} / 提示 ${summary.info}`
              : undefined
          }
        />
        <Step
          label="组织解释"
          state={done ? 'done' : generating ? 'active' : conflictDone ? 'active' : 'pending'}
        />
        <Step label="生成文本" state={done ? 'done' : generating ? 'active' : 'pending'} />
      </ol>

      {thinking && <p className="trace__note small secondary">{thinking}</p>}

      {started && (
        <div className="trace__meters tiny muted tabular">
          <span>首字 {formatMs(firstByteMs)}</span>
          <span>·</span>
          <span>{chunks} 块</span>
          <span>·</span>
          <span>{chars} 字</span>
          <span>·</span>
          <span title="mock 模式下由内置规则生成，不产生任何网络请求">
            {provider === 'mock' ? '内置规则引擎（无网络请求）' : provider}
          </span>
        </div>
      )}
    </div>
  )
}

function Step({
  label,
  state,
  hint,
}: {
  label: string
  state: 'pending' | 'active' | 'done'
  hint?: string
}) {
  const mark = state === 'done' ? '✓' : state === 'active' ? '⟳' : '·'
  return (
    <li className={`trace__step trace__step--${state}`}>
      <span className="trace__mark" aria-hidden="true">
        {mark}
      </span>
      <span>{label}</span>
      {hint && <span className="muted tiny">{hint}</span>}
    </li>
  )
}
