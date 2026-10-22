/**
 * 顶栏：身份、主导航、数据状态徽章、运行模式、操作区。
 *
 * 导航是两个入口的产品化表达（认知入口 / 核算入口），所以放在标题正后方，
 * 而不是藏进某个按钮里。切到规则视图时，排课专属的按钮与专业信息整组隐藏 ——
 * 留着它们是"看起来能点、点了没意义"的假可用。
 */

import type { HealthResponse, Program } from '@/api/types'

export type AppView = 'plan' | 'rules'

const VIEWS: Array<{ id: AppView; label: string }> = [
  { id: 'plan', label: '培养方案' },
  { id: 'rules', label: '转专业规则' },
]

interface Props {
  view: AppView
  onViewChange: (view: AppView) => void
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
  view,
  onViewChange,
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
  const onPlan = view === 'plan'

  return (
    <header className="shell__bar">
      <h1 className="shell__title">课径 CoursePath</h1>

      <nav className="navtabs" aria-label="主导航">
        {VIEWS.map((item) => (
          <button
            key={item.id}
            className={`navtab ${view === item.id ? 'navtab--active' : ''}`}
            onClick={() => onViewChange(item.id)}
            aria-current={view === item.id ? 'page' : undefined}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {onPlan && program && (
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

      {onPlan && (
        <>
          <button className="btn btn--quiet tiny" onClick={onUndo} disabled={!canUndo} title="撤销">
            撤销
          </button>
          <button className="btn btn--quiet tiny" onClick={onRedo} disabled={!canRedo} title="重做">
            重做
          </button>
          <button
            className="btn tiny"
            onClick={onReset}
            disabled={!isDirty}
            title="回到后端算出来的可行解"
          >
            恢复样例规划
          </button>
          <button
            className="btn btn--quiet tiny"
            onClick={onClear}
            disabled={!program}
            title="清空全部课程"
          >
            清空
          </button>
          <button className="btn btn--primary tiny" onClick={onExplain} disabled={!program}>
            AI 解读
          </button>
        </>
      )}

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
