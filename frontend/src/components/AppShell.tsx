/** 顶栏：身份、数据状态徽章、运行模式、操作区。 */

import type { HealthResponse, Program } from '@/api/types'

interface Props {
  program: Program | null
  health: HealthResponse | null
  canUndo: boolean
  canRedo: boolean
  isDirty: boolean
  onUndo: () => void
  onRedo: () => void
  onReset: () => void
  onClear: () => void
  onExplain: () => void
}

export function AppShell({
  program,
  health,
  canUndo,
  canRedo,
  isDirty,
  onUndo,
  onRedo,
  onReset,
  onClear,
  onExplain,
}: Props) {
  const mock = health?.llm.mode === 'mock'

  return (
    <header className="shell__bar">
      <h1 className="shell__title">课径 CoursePath</h1>

      {program && (
        <>
          <span className="secondary small">
            {program.name} · {program.college}
          </span>
          {program.data_status === 'sample' && (
            <span className="badge badge--sample" title={program.note}>
              样例数据
            </span>
          )}
          {program.schedule_status === 'not_available' && (
            <span className="badge" title="培养方案不含上课时段（那是排课表的字段）">
              排课数据未接入
            </span>
          )}
        </>
      )}

      <span className="shell__spacer" />

      <button className="btn btn--quiet tiny" onClick={onUndo} disabled={!canUndo} title="撤销">
        撤销
      </button>
      <button className="btn btn--quiet tiny" onClick={onRedo} disabled={!canRedo} title="重做">
        重做
      </button>
      <button className="btn tiny" onClick={onReset} disabled={!isDirty} title="回到后端算出来的可行解">
        恢复样例规划
      </button>
      <button className="btn btn--quiet tiny" onClick={onClear} disabled={!program} title="清空全部课程">
        清空
      </button>
      <button className="btn btn--primary tiny" onClick={onExplain} disabled={!program}>
        AI 解读
      </button>

      <span
        className="badge badge--mono"
        title={
          mock
            ? 'mock 模式：无需任何 API Key，全部功能可离线演示'
            : `已连接真实模型：${health?.llm.provider}`
        }
      >
        {mock ? 'LLM: mock' : `LLM: ${health?.llm.provider}`}
      </span>
    </header>
  )
}
