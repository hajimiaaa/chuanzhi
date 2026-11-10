/**
 * 核算入口的第二屏：补修 / 重修清单。
 *
 * **这一屏只做「不需要认定办法」的那一半。**
 * 课程号能对上的（公共课、同名课）算得出来：已认定 / 重修 / 补修。
 * 对不上的原专业课程归入「待认定」——不是我们漏了，是缺《学分认定管理办法》。
 *
 * 四类刻意分开显示而不是合成一个"还差 N 门"：四类对应四种不同的动作
 * （不用管 / 重修 / 补修 / 去问教务处），合并任何一类都会变成误导。
 */

import { useState, type FormEvent } from 'react'

import { describeError } from '@/api/client'
import { auditSheet } from '@/api/endpoints'
import type {
  AuditSheetResponse,
  CompletedCourse,
  CreditCase,
  CreditGapResponse,
  PlanSuggestion,
  Program,
} from '@/api/types'
import { CreditAuditSheet } from '@/components/CreditAuditSheet'
import { useCreditGap } from '@/hooks/useCreditGap'
import { SAMPLE_TRANSCRIPT, makeCompleted } from '@/lib/transcript'
import { usePlan } from '@/state/PlanContext'

interface Props {
  program: Program | null
}

export function CreditGapView({ program }: Props) {
  const { history, dispatch } = usePlan()
  const completed = history.current.completed
  const gap = useCreditGap(program, completed)

  const [sheet, setSheet] = useState<AuditSheetResponse | null>(null)
  const [sheetLoading, setSheetLoading] = useState(false)
  const [sheetError, setSheetError] = useState('')

  async function openSheet() {
    if (!program) return
    setSheetLoading(true)
    setSheetError('')
    try {
      setSheet(await auditSheet({ program_id: program.id, completed }))
    } catch (cause: unknown) {
      setSheetError(describeError(cause))
    } finally {
      setSheetLoading(false)
    }
  }

  return (
    <div className={`shell__body ${gap.loading ? 'rules--loading' : ''}`}>
      <main className="shell__main">
        <header className="panel">
          <div className="panel__head">
            <h2 className="panel__title">补修核算</h2>
            {program && (
              <span className="secondary small">
                {program.name} · {program.college}
              </span>
            )}
            {program?.data_status === 'sample' && (
              <span className="badge badge--sample">样例数据</span>
            )}
            {gap.stale && (
              <span className="badge badge--stale" title={gap.error}>
                已过期
              </span>
            )}
          </div>
          <p className="small secondary" style={{ margin: 0 }}>
            转专业后还需要修什么 —— 按<strong>课程号 + 课名</strong>比对；
            <strong>跨专业折抵不替你判断</strong>，只把需要确认的课单独列出来。
          </p>

          {program && completed.length > 0 && (
            <div className="gapview__actions">
              <button
                className="btn btn--primary tiny"
                onClick={openSheet}
                disabled={sheetLoading}
              >
                {sheetLoading ? '生成中…' : '生成核对单'}
              </button>
              <span className="muted tiny">五类清单 + 自检 + 签字栏，可打印 / 复制为文本</span>
              {sheetError && <span className="muted tiny">· {sheetError}</span>}
            </div>
          )}
        </header>

        {!program ? (
          <section className="panel">
            <p className="muted small">正在加载培养方案…</p>
          </section>
        ) : completed.length === 0 ? (
          <EmptyTranscript />
        ) : !gap.data ? (
          <section className="panel">
            <p className="secondary small">{gap.error || '正在计算补修清单…'}</p>
            {gap.error && (
              <button className="btn tiny" onClick={gap.reload}>
                重试
              </button>
            )}
          </section>
        ) : (
          <Results data={gap.data} stale={gap.stale} error={gap.error} />
        )}
      </main>

      <aside className="shell__aside">
        <TranscriptEditor
          completed={completed}
          onAdd={(item) => dispatch({ type: 'UPSERT_COMPLETED', completed: item })}
          onRemove={(courseCode) => dispatch({ type: 'REMOVE_COMPLETED', courseCode })}
          onSample={() => dispatch({ type: 'REPLACE_COMPLETED', completed: SAMPLE_TRANSCRIPT })}
          onClear={() => dispatch({ type: 'REPLACE_COMPLETED', completed: [] })}
        />
        <PolicyNote />
      </aside>

      {sheet && <CreditAuditSheet data={sheet} onClose={() => setSheet(null)} />}
    </div>
  )
}

function EmptyTranscript() {
  return (
    <section className="panel">
      <div className="rules__empty">
        <div className="rules__empty-title">先录入已修课程</div>
        <p className="muted small">
          在右侧逐门添加你在原专业修过的课程（课程代码 / 学分 / 成绩），
          或者点「加载示例成绩单」直接看效果。
        </p>
        <p className="muted tiny">
          只有课程号能在目标培养方案里对上的，才算得出来；原专业课程会被标成「待认定」。
        </p>
      </div>
    </section>
  )
}

interface ResultsProps {
  data: CreditGapResponse
  stale: boolean
  error: string
}

function Results({ data, stale, error }: ResultsProps) {
  const { summary } = data

  return (
    <>
      {stale && error && (
        <div className="rules__stale small">
          本次请求失败，下方为<strong>上一次</strong>的结果：{error}
        </div>
      )}

      <section className="panel">
        <div className="stats__tiles gapview__tiles">
          <Tile value={summary.remedial} label="需补修" hint={`${summary.remedial_credits} 学分`} />
          <Tile
            value={summary.retake}
            label="需重修"
            hint={`${summary.retake_credits} 学分`}
            tone="warn"
          />
          <Tile
            value={summary.possible_overlap}
            label="可能可折抵"
            hint={`${summary.possible_overlap_credits} 学分 · 需确认`}
          />
          <Tile value={summary.pending} label="待认定" hint={`${summary.pending_credits} 学分`} />
          <Tile
            value={summary.recognized}
            label="已认定"
            hint={`${summary.recognized_credits} 学分`}
            tone="ok"
          />
        </div>
        <p className="muted tiny gapview__note">
          培养方案共 {summary.program_credits} 学分。前四类（不含「待认定」）合计严格等于培养方案总学分，
          不存在重复计算。
        </p>
      </section>

      <CaseSection
        title="需补修"
        hint="培养方案要求，成绩单里没有"
        cases={data.remedial}
        empty="没有需要补修的课程。"
      />
      <CaseSection
        title="需重修"
        hint="修过但没有通过"
        cases={data.retake}
        empty="没有需要重修的课程。"
      />
      <CaseSection
        title="可能可折抵"
        hint="同名、同学分，但课号不同"
        cases={data.possible_overlap}
        empty="没有需要确认的同名课程。"
        note="这类课大概率就是你修过的那门公共课，但「能不能顶」由学校认定。带成绩单到教务处按《学分认定管理办法》确认，确认前不要当成已修。"
      />
      <CaseSection
        title="待认定"
        hint="原专业独有课程，本方案没有对应"
        cases={data.pending}
        empty="没有待认定的课程。"
        note="它们既不在本培养方案课程库里，也没有同名同学分的对应课，只能由学院/教务处判断能否计入。"
      />
      <CaseSection
        title="已认定"
        hint="课程号对上且已通过"
        cases={data.recognized}
        empty="还没有课程号能直接对上的已修课程。"
      />

      <Suggested data={data.suggested} />

      {data.notes.length > 0 && (
        <section className="panel">
          <div className="panel__head">
            <h2 className="panel__title">计算说明</h2>
          </div>
          <ul className="gapview__notes">
            {data.notes.map((note) => (
              <li key={note} className="small secondary">
                {note}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

function Tile({
  value,
  label,
  hint,
  tone,
}: {
  value: number
  label: string
  hint: string
  tone?: 'warn' | 'ok'
}) {
  const modifier = value > 0 && tone === 'warn' ? 'tile__value--warn' : tone === 'ok' ? 'stats__ok' : ''
  return (
    <div className="tile">
      <div className={`tile__value tabular ${modifier}`}>{value}</div>
      <div className="tile__label">{label}</div>
      <div className="muted tiny">{hint}</div>
    </div>
  )
}

interface CaseSectionProps {
  title: string
  hint: string
  cases: CreditCase[]
  empty: string
  note?: string
}

function CaseSection({ title, hint, cases, empty, note }: CaseSectionProps) {
  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">{title}</h2>
        <span className="muted tiny">{hint}</span>
        <span className="shell__spacer" />
        <span className="muted tiny">{cases.length} 门</span>
      </div>

      {note && <p className="small secondary gapview__note">{note}</p>}

      {cases.length === 0 ? (
        <p className="muted small" style={{ margin: 0 }}>
          {empty}
        </p>
      ) : (
        <ul className="cases">
          {cases.map((item) => (
            <li key={item.course_code} className="case">
              <span className="case__code tabular">{item.course_code}</span>
              <span className="case__name">{item.name || '（原专业课程）'}</span>
              <span className="shell__spacer" />
              <span className="muted tiny case__meta">
                {item.credits} 学分
                {item.category ? ` · ${item.category}` : ''}
                {item.grade !== null && item.grade !== '' ? ` · 成绩 ${item.grade}` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Suggested({ data }: { data: PlanSuggestion }) {
  const byTerm = new Map<number, string[]>()
  for (const item of data.items) {
    byTerm.set(item.term, [...(byTerm.get(item.term) ?? []), item.course_code])
  }
  const terms = [...byTerm.entries()].sort((a, b) => a[0] - b[0])

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">建议修读顺序</h2>
        <span className="muted tiny">按先修关系与学期负荷排出的可行解</span>
      </div>

      {terms.length === 0 ? (
        <p className="muted small" style={{ margin: 0 }}>
          没有需要安排的课程。
        </p>
      ) : (
        <div className="gapview__terms">
          {terms.map(([term, codes]) => (
            <div className="gapview__term" key={term}>
              <span className="muted tiny">第 {term} 学期</span>
              <span className="small">{codes.join(' · ')}</span>
            </div>
          ))}
        </div>
      )}

      {data.unscheduled.length > 0 && (
        <p className="muted small gapview__note">
          排不下：{data.unscheduled.join(' · ')} —— 先修链或学期容量限制，原因见后端返回的 notes。
        </p>
      )}
    </section>
  )
}

interface EditorProps {
  completed: CompletedCourse[]
  onAdd: (item: CompletedCourse) => void
  onRemove: (courseCode: string) => void
  onSample: () => void
  onClear: () => void
}

function TranscriptEditor({ completed, onAdd, onRemove, onSample, onClear }: EditorProps) {
  const [code, setCode] = useState('')
  const [courseName, setCourseName] = useState('')
  const [credits, setCredits] = useState('3')
  const [grade, setGrade] = useState('')
  const [formError, setFormError] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    const courseCode = code.trim().toUpperCase()
    const creditValue = Number(credits)
    const gradeValue = Number(grade)

    if (!courseCode) return setFormError('请填写课程代码')
    if (!Number.isFinite(creditValue) || creditValue <= 0) return setFormError('学分必须是正数')
    if (!Number.isFinite(gradeValue) || gradeValue < 0 || gradeValue > 100) {
      return setFormError('成绩必须是 0–100 的数字')
    }

    onAdd(
      makeCompleted({
        course_code: courseCode,
        name: courseName,
        credits: creditValue,
        grade: gradeValue,
      }),
    )
    setCode('')
    setCourseName('')
    setGrade('')
    setFormError('')
  }

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">已修课程（原专业）</h2>
        <span className="muted tiny">{completed.length} 门</span>
      </div>

      <form className="transcript__form" onSubmit={submit}>
        <input
          className="picker__search transcript__input transcript__input--wide"
          placeholder="课程代码"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label="课程代码"
        />
        <input
          className="picker__search transcript__input transcript__input--wide"
          placeholder="课程名称（可选，跨专业同名课要靠它识别）"
          value={courseName}
          onChange={(e) => setCourseName(e.target.value)}
          aria-label="课程名称"
        />
        <input
          className="picker__search transcript__input"
          placeholder="学分"
          value={credits}
          onChange={(e) => setCredits(e.target.value)}
          inputMode="decimal"
          aria-label="学分"
        />
        <input
          className="picker__search transcript__input"
          placeholder="成绩"
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          inputMode="numeric"
          aria-label="成绩"
        />
        <button className="btn btn--primary tiny" type="submit">
          添加
        </button>
      </form>

      {formError && <p className="muted tiny transcript__error">{formError}</p>}

      <div className="transcript__actions">
        <button className="btn btn--quiet tiny" onClick={onSample}>
          加载示例成绩单
        </button>
        <button className="btn btn--quiet tiny" onClick={onClear} disabled={completed.length === 0}>
          清空成绩单
        </button>
      </div>

      {completed.length === 0 ? (
        <p className="muted small" style={{ margin: 0 }}>
          还没有录入。先添加一门课，或点「加载示例成绩单」看效果。
        </p>
      ) : (
        <ul className="transcript__list">
          {completed.map((item) => (
            <li key={item.course_code} className="transcript__item">
              <span className="case__code tabular">{item.course_code}</span>
              <span className="muted tiny transcript__item-text">
                {item.name ? `${item.name} · ` : ''}
                {item.credits} 学分 · {item.grade ?? '—'} 分
              </span>
              <span className="shell__spacer" />
              <span className={`badge ${item.passed ? 'badge--pass' : 'badge--fail'}`}>
                {item.passed ? '通过' : '未通过'}
              </span>
              <button
                className="btn btn--quiet tiny"
                onClick={() => onRemove(item.course_code)}
                aria-label={`移除 ${item.course_code}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function PolicyNote() {
  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">怎么读这五类</h2>
      </div>
      <p className="small secondary" style={{ margin: 0 }}>
        <strong>已认定 / 需重修 / 需补修</strong>：课程号完全对得上，结论可以直接采信。
        <br />
        <strong>可能可折抵</strong>：课名和学分都对得上、但课号不同——大概率是你修过的公共课，
        能不能顶要由教务处认定，<strong>确认前不要当成已修</strong>。
        <br />
        <strong>待认定</strong>：原专业独有课程，本方案没有对应，只能由学院判断能否计入。
      </p>
      <p className="muted tiny gapview__note">
        跨专业折抵的判定标准各校完全不同——有的给换算式（周学时 × 周数 ÷ 16），
        有的要求「课程目标对毕业要求的支撑等效」。我们不做这个判断，只把需要确认的课挑出来。
      </p>
    </section>
  )
}
