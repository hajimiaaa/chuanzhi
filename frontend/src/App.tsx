/**
 * 主线闭环：选专业 → 拖拽排课 → 实时校验 → 学分进度 → AI 解读。
 *
 * 初始态是「后端算出的可行解」而不是空规划 —— 见 useValidation 的注释。
 * 演示叙事因此是：打开就是干净的 → 拖错一门 → 立刻冒红 → 拖回去 → 红消失。
 */

import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { describeError } from '@/api/client'
import { getMajors, getPrograms } from '@/api/endpoints'
import type { Conflict, MajorsDoc, PlanIn, ProgramSummary } from '@/api/types'
import { AppShell } from '@/components/AppShell'
import { BackendBanner } from '@/components/BackendBanner'
import { ConflictPanel, type FocusState } from '@/components/ConflictPanel'
import { CreditMeters } from '@/components/CreditMeters'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ExplainPanel } from '@/components/ExplainPanel'
import { MajorPicker } from '@/components/MajorPicker'
import { StatTiles } from '@/components/StatTiles'
import { TermBoard } from '@/components/TermBoard'
import { useHealth } from '@/hooks/useHealth'
import { useProgram } from '@/hooks/useProgram'
import { useValidation } from '@/hooks/useValidation'
import { computeCredits, courseIndex, unplacedCourses } from '@/lib/derive'
import { PlanProvider, usePlan } from '@/state/PlanContext'
import { sortItems } from '@/state/planReducer'

/*
 * ECharts 单独懒加载：按需引入后仍是 179 kB(gzip)，而图表在侧栏偏下位置，
 * 没必要让它阻塞首屏。它本来就被 manualChunks 切成了独立 chunk，
 * 这里只是让它从"首屏就下载"变成"进入视口附近才下载"。
 */
const TermChart = lazy(() =>
  import('@/components/TermChart').then((module) => ({ default: module.TermChart })),
)

export default function App() {
  const health = useHealth()
  const [programs, setPrograms] = useState<ProgramSummary[]>([])
  const [majors, setMajors] = useState<MajorsDoc | null>(null)
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    if (health.status !== 'ok') return
    const controller = new AbortController()

    Promise.all([
      getPrograms({ signal: controller.signal }),
      getMajors({ signal: controller.signal }),
    ])
      .then(([list, doc]) => {
        if (controller.signal.aborted) return
        setPrograms(list.items)
        setMajors(doc)
        setLoadError('')
        setCurrentId((current) => current ?? list.items[0]?.id ?? null)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setLoadError(describeError(cause))
      })

    return () => controller.abort()
  }, [health.status])

  return (
    <div className="shell">
      <ErrorBoundary>
        {health.status === 'down' && <BackendBanner error={health.error} onRetry={health.retry} />}
        {health.status === 'checking' && (
          <div className="shell__bar">
            <h1 className="shell__title">课径 CoursePath</h1>
            <span className="muted small">正在连接后端…</span>
          </div>
        )}
        {health.status === 'ok' && (!currentId || !majors) && (
          <>
            <div className="shell__bar">
              <h1 className="shell__title">课径 CoursePath</h1>
              <span className="muted small">{loadError ? '加载失败' : '正在加载培养方案…'}</span>
            </div>
            {loadError && (
              <div className="panel" style={{ margin: 24 }}>
                <p className="secondary small">{loadError}</p>
              </div>
            )}
          </>
        )}
        {health.status === 'ok' && currentId && majors && (
          <PlanProvider key={currentId} programId={currentId}>
            <Workbench
              currentId={currentId}
              programs={programs}
              majors={majors}
              onPick={setCurrentId}
              health={health.data}
            />
          </PlanProvider>
        )}
      </ErrorBoundary>
    </div>
  )
}

interface WorkbenchProps {
  currentId: string
  programs: ProgramSummary[]
  majors: MajorsDoc
  onPick: (programId: string) => void
  health: ReturnType<typeof useHealth>['data']
}

function Workbench({ currentId, programs, majors, onPick, health }: WorkbenchProps) {
  const { history, dispatch, canUndo, canRedo, isDirty } = usePlan()
  const { program, samplePlan, status, error } = useProgram(currentId)
  const validation = useValidation(program, history.current)

  const [focus, setFocus] = useState<FocusState | null>(null)
  const [courseFilter, setCourseFilter] = useState<string | null>(null)
  const [explainOpen, setExplainOpen] = useState(false)
  const seededRef = useRef<string | null>(null)

  // 用后端算出的可行解做初始态与基线 —— 空规划会让开局一次冒出 5 条学分缺口
  useEffect(() => {
    if (!program || !samplePlan || seededRef.current === program.id) return
    seededRef.current = program.id
    dispatch({
      type: 'REPLACE_PLAN',
      plan: { programId: program.id, items: samplePlan.items, completed: [] },
      origin: 'sample',
      asBaseline: true,
    })
  }, [program, samplePlan, dispatch])

  const conflicts = validation.result?.conflicts ?? []
  const summary = validation.result?.summary ?? null

  const credits = useMemo(
    () => (program ? computeCredits(program, history.current.items) : null),
    [program, history.current.items],
  )

  const unplaced = useMemo(
    () => (program ? unplacedCourses(program, history.current.items) : []),
    [program, history.current.items],
  )

  const focusCodes = useMemo(() => new Set(focus?.courseCodes ?? []), [focus])

  const explainBody = useMemo<PlanIn>(
    () => ({
      program_id: currentId,
      items: sortItems(history.current.items),
      completed: history.current.completed,
    }),
    [currentId, history.current.items, history.current.completed],
  )

  const handleMove = useCallback(
    (courseCode: string, toTerm: number) => dispatch({ type: 'MOVE_COURSE', courseCode, toTerm }),
    [dispatch],
  )
  const handleRemove = useCallback(
    (courseCode: string) => dispatch({ type: 'REMOVE_COURSE', courseCode }),
    [dispatch],
  )
  const scrollToTerm = useCallback((term: number) => {
    document
      .querySelector(`[data-term="${term}"]`)
      ?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
  }, [])

  const handleFocusConflict = useCallback(
    (conflict: Conflict) => {
      setFocus({ term: conflict.term, courseCodes: conflict.course_codes, nonce: Date.now() })
      document
        .querySelector(`[data-course="${conflict.course_codes[0] ?? ''}"]`)
        ?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
      if (conflict.term > 0) scrollToTerm(conflict.term)
    },
    [scrollToTerm],
  )

  const handleFocusCourse = useCallback(
    (courseCode: string) => {
      const related = conflicts.filter((c) => c.course_codes.includes(courseCode))
      setCourseFilter(related.length > 0 ? courseCode : null)
      const first = related[0]
      if (first) setFocus({ term: first.term, courseCodes: [courseCode], nonce: Date.now() })
    },
    [conflicts],
  )

  if (status === 'error') {
    return (
      <>
        <div className="shell__bar">
          <h1 className="shell__title">课径 CoursePath</h1>
          <span className="muted small">培养方案加载失败</span>
        </div>
        <div className="panel" style={{ margin: 24 }}>
          <p className="secondary small">{error}</p>
          <button className="btn" onClick={() => onPick(currentId)}>
            重试
          </button>
        </div>
      </>
    )
  }

  if (!program || !credits) {
    return (
      <>
        <div className="shell__bar">
          <h1 className="shell__title">课径 CoursePath</h1>
          <span className="muted small">正在加载培养方案…</span>
        </div>
      </>
    )
  }

  const placed = credits.byCategory
  const index = courseIndex(program)

  return (
    <>
      <AppShell
        program={program}
        health={health}
        canUndo={canUndo}
        canRedo={canRedo}
        isDirty={isDirty}
        onUndo={() => dispatch({ type: 'UNDO' })}
        onRedo={() => dispatch({ type: 'REDO' })}
        onReset={() => dispatch({ type: 'RESET_TO_SAMPLE' })}
        onClear={() => dispatch({ type: 'CLEAR' })}
        onExplain={() => setExplainOpen(true)}
      />

      <div className="shell__body">
        <main className="shell__main">
          <StatTiles
            totalEarned={credits.total}
            totalMin={program.total_min_credits}
            errorCount={summary?.error ?? 0}
            warningCount={summary?.warning ?? 0}
            placedCourses={history.current.items.length}
            totalCourses={program.courses.length}
          />

          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">四年排课板</h2>
              <span className="muted tiny">
                拖动课程卡片改学期· 每学期上限 {program.max_credits_per_term} 学分
              </span>
            </div>
            <TermBoard
              program={program}
              items={history.current.items}
              conflicts={conflicts}
              focusCodes={focusCodes}
              unplaced={unplaced}
              unscheduled={samplePlan?.unscheduled ?? []}
              onMove={handleMove}
              onRemove={handleRemove}
              onFocusCourse={handleFocusCourse}
            />
          </div>
        </main>

        <aside className="shell__aside">
          <ConflictPanel
            program={program}
            conflicts={conflicts}

            loading={validation.loading}
            stale={validation.stale}
            error={validation.error}
            isEmptyPlan={history.current.items.length === 0}
            focus={focus}
            courseFilter={courseFilter}
            onFocusConflict={handleFocusConflict}
            onClearCourseFilter={() => setCourseFilter(null)}
            onRun={validation.run}
            onExplain={() => setExplainOpen(true)}
          />

          {explainOpen && (
            <ExplainPanel
              body={explainBody}
              providerHint={health?.llm.provider ?? 'mock'}
              onClose={() => setExplainOpen(false)}
            />
          )}

          <section className="panel">
            <div className="panel__head">
              <h2 className="panel__title">学分进度</h2>
            </div>
            <CreditMeters rules={program.credit_rules} earnedByCategory={placed} />
          </section>

          <section className="panel">
            <div className="panel__head">
              <h2 className="panel__title">每学期负荷</h2>
              <span className="muted tiny">点击柱子可定位到该学期</span>
            </div>
            <Suspense fallback={<div className="chart__canvas muted small">图表加载中…</div>}>
              <TermChart
                program={program}
                byTermCategory={credits.byTermCategory}
                byTerm={credits.byTerm}
                rules={program.credit_rules}
                onSelectTerm={scrollToTerm}
              />
            </Suspense>
          </section>

          <MajorPicker
            doc={majors}
            programs={programs}
            currentId={currentId}
            onPick={onPick}
          />

          <details className="panel">
            <summary className="panel__title" style={{ cursor: 'pointer' }}>
              关于这份数据
            </summary>
            <p className="small secondary" style={{ marginBottom: 0 }}>
              {program.note}
            </p>
            <p className="muted tiny" style={{ marginBottom: 0, marginTop: 6 }}>
              共 {index.size} 门课 · 学分门槛 {program.total_min_credits} ·{' '}
              {program.total_terms} 个学期
            </p>
          </details>
        </aside>
      </div>
    </>
  )
}
