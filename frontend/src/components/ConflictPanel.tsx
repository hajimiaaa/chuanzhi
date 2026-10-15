/**
 * 冲突面板。
 *
 * 三条设计决定：
 *  1. **分层**：error 默认展开置顶，warning 次级，info 折叠。顶部三枚计数 chip 可点击筛选。
 *  2. **数据边界说明移出主列表**：`time_data_missing` 在样例数据下**必然出现**，
 *     混在列表里当红字会把一个干净的开局读成"满屏问题"。它移到面板底部，措辞是说明而非警告。
 *  3. **失败不清空**：请求失败时保留上一次结果并打「已过期」徽章。
 *     清空等于告诉用户"没有冲突" —— 那是比报错更危险的假阴性。
 */

import { useMemo, useState } from 'react'

import type { Conflict, Program, Severity } from '@/api/types'
import { SEVERITY_COLOR, SEVERITY_ICON, SEVERITY_LABEL } from '@/lib/colors'
import { conflictMeta, countsTowardSummary, GROUP_LABEL, GROUP_ORDER, type ConflictGroup } from '@/lib/conflictMeta'
import { ConflictCard } from './ConflictCard'

export interface FocusState {
  term: number | null
  courseCodes: string[]
  nonce: number
}

interface Props {
  program: Program
  conflicts: Conflict[]
  loading: boolean
  stale: boolean
  error: string
  isEmptyPlan: boolean
  focus: FocusState | null
  courseFilter: string | null
  onFocusConflict: (conflict: Conflict) => void
  onClearCourseFilter: () => void
  onRun: () => void
  onExplain: () => void
}

const SEVERITIES: Severity[] = ['error', 'warning', 'info']

export function ConflictPanel({
  program,
  conflicts,
  loading,
  stale,
  error,
  isEmptyPlan,
  focus,
  courseFilter,
  onFocusConflict,
  onClearCourseFilter,
  onRun,
  onExplain,
}: Props) {
  const [severityFilter, setSeverityFilter] = useState<Severity | null>(null)
  const [showInfo, setShowInfo] = useState(false)

  const { main, boundary, counts } = useMemo(() => {
    const mainList: Conflict[] = []
    const boundaryList: Conflict[] = []
    const tally: Record<Severity, number> = { error: 0, warning: 0, info: 0 }

    for (const conflict of conflicts) {
      if (!countsTowardSummary(conflict.kind)) {
        boundaryList.push(conflict)
        continue
      }
      tally[conflict.severity] += 1
      if (courseFilter && !conflict.course_codes.includes(courseFilter)) continue
      mainList.push(conflict)
    }
    return { main: mainList, boundary: boundaryList, counts: tally }
  }, [conflicts, courseFilter])

  const visible = useMemo(() => {
    return main.filter((conflict) => {
      if (severityFilter && conflict.severity !== severityFilter) return false
      if (conflict.severity === 'info' && !showInfo && !severityFilter) return false
      return true
    })
  }, [main, severityFilter, showInfo])

  const grouped = useMemo(() => {
    const map = new Map<ConflictGroup, Conflict[]>()
    for (const conflict of visible) {
      const group = conflictMeta(conflict.kind).group
      map.set(group, [...(map.get(group) ?? []), conflict])
    }
    return GROUP_ORDER.filter((g) => map.has(g)).map((g) => [g, map.get(g)!] as const)
  }, [visible])

  const totalIssues = counts.error + counts.warning

  return (
    <section className={`panel conflicts ${loading ? 'conflicts--loading' : ''}`}>
      <header className="panel__head">
        <h2 className="panel__title">冲突检测</h2>
        {loading && <span className="muted tiny">校验中…</span>}
        {stale && (
          <span className="badge badge--stale" title={error}>
            已过期
          </span>
        )}
        <span className="shell__spacer" />
        {totalIssues > 0 && (
          <button className="btn btn--quiet tiny" onClick={onExplain} title="用 AI 解释这份规划">
            AI 解读
          </button>
        )}
      </header>

      <div className="conflicts__filters">
        {SEVERITIES.map((severity) => {
          const count = counts[severity]
          const active = severityFilter === severity
          return (
            <button
              key={severity}
              className={`chip chip--sev ${active ? 'chip--active' : ''}`}
              style={{ ['--sev' as string]: SEVERITY_COLOR[severity] }}
              onClick={() => setSeverityFilter(active ? null : severity)}
              disabled={count === 0 && !active}
            >
              <span aria-hidden="true">{SEVERITY_ICON[severity]}</span>
              {SEVERITY_LABEL[severity]} {count}
            </button>
          )
        })}
        {courseFilter && (
          <button className="chip chip--active" onClick={onClearCourseFilter}>
            仅看 {courseFilter} ×
          </button>
        )}
      </div>

      {stale && error && (
        <div className="conflicts__stale small">
          本次校验失败，下方为**上一次**的结果：{error}
        </div>
      )}

      {isEmptyPlan ? (
        <EmptyPlanState onRun={onRun} />
      ) : main.length === 0 && boundary.length > 0 ? (
        <CleanState onExplain={onExplain} />
      ) : main.length === 0 ? (
        <CleanState onExplain={onExplain} />
      ) : (
        <>
          {visible.length === 0 && (
            <div className="muted small" style={{ padding: '8px 0' }}>
              当前筛选下没有条目。
              {!showInfo && counts.info > 0 && (
                <button className="btn btn--quiet tiny" style={{ marginLeft: 6 }} onClick={() => setShowInfo(true)}>
                  展开 {counts.info} 条提示
                </button>
              )}
            </div>
          )}

          {grouped.map(([group, items]) => (
            <div key={group} className="conflicts__group">
              <div className="conflicts__group-head">
                <span>{GROUP_LABEL[group]}</span>
                <span className="muted tiny">{items.length}</span>
              </div>
              {items.map((conflict, index) => (
                <ConflictCard
                  key={`${conflict.kind}-${conflict.term}-${conflict.course_codes.join('-')}-${index}`}
                  conflict={conflict}
                  program={program}
                  isFocused={
                    !!focus &&
                    focus.nonce > 0 &&
                    conflict.course_codes.length > 0 &&
                    focus.courseCodes.includes(conflict.course_codes[0]!)
                  }
                  onFocus={() => onFocusConflict(conflict)}
                />
              ))}
            </div>
          ))}
        </>
      )}

      {boundary.length > 0 && <BoundaryNotes conflicts={boundary} />}
    </section>
  )
}

function CleanState({ onExplain }: { onExplain: () => void }) {
  return (
    <div className="clean">
      <div className="clean__mark" aria-hidden="true">
        ✓
      </div>
      <div>
        <div className="clean__title">可行规划 —— 未发现错误与警告</div>
        <div className="muted small">学分结构、先修顺序、开课学期与学期负荷均满足。</div>
      </div>
      <button className="btn btn--quiet tiny" onClick={onExplain}>
        用 AI 解释这份规划
      </button>
    </div>
  )
}

function EmptyPlanState({ onRun }: { onRun: () => void }) {
  return (
    <div className="muted small" style={{ padding: '10px 0' }}>
      规划里还没有课程。空规划**不会自动校验** —— 因为在样例数据下它会一次报出
      四条类别与总学分的缺口，开局就是个满屏红。
      <div style={{ marginTop: 8 }}>
        <button className="btn btn--quiet tiny" onClick={onRun}>
          仍然校验空规划
        </button>
      </div>
    </div>
  )
}

function BoundaryNotes({ conflicts }: { conflicts: Conflict[] }) {
  return (
    <div className="boundary">
      <div className="boundary__head">
        <span className="badge">数据说明</span>
        <span className="muted tiny">{conflicts.length} 条 · 不计入冲突数</span>
      </div>
      {conflicts.map((conflict, index) => (
        <div key={`${conflict.kind}-${index}`} className="boundary__item small secondary">
          {conflict.message}
        </div>
      ))}
      <details className="small" style={{ marginTop: 6 }}>
        <summary className="muted" style={{ cursor: 'pointer' }}>
          为什么会这样
        </summary>
        <p className="muted tiny" style={{ marginBottom: 0 }}>
          上课时段属于排课表的数据，不在培养方案里。这项检测本身已实现并有单元测试覆盖，
          只是当前培养方案还没有接入排课时段，因此以说明的方式标注，而不是假装没有这项检测。
        </p>
      </details>
    </div>
  )
}
