/**
 * 专业选择。数据来自官方《专业目录一览表》（108 个专业 / 21 个学院）。
 *
 * 只有已经接入培养方案的专业可选 —— 其余明确标注「培养方案未接入」，
 * 而不是隐藏。让"我们覆盖了什么、没覆盖什么"一眼可见。
 */

import { useMemo, useState } from 'react'

import type { MajorsDoc, ProgramSummary } from '@/api/types'

interface Props {
  doc: MajorsDoc
  programs: ProgramSummary[]
  currentId: string | null
  onPick: (programId: string) => void
}

export function MajorPicker({ doc, programs, currentId, onPick }: Props) {
  const [query, setQuery] = useState('')

  const byMajorName = useMemo(() => {
    const map = new Map<string, ProgramSummary>()
    for (const summary of programs) map.set(`${summary.college}|${summary.name}`, summary)
    return map
  }, [programs])

  /**
   * 兜底匹配：只认「去掉括号后同名，且**本身不是特殊学制**」的专业。
   *
   * 不能无条件按裸名匹配 —— 目录里 `计算机科学与技术` / `（春季）` / `(专升本)` 是
   * 三个不同的招生口径，把它们都标成"已接入培养方案"是错的（而且它们本来就
   * 不在"可转专业"的范围内，见《通知》的不得转专业条款）。
   */
  const matchProgram = (college: string, majorName: string, tags?: string[]) => {
    const exact = byMajorName.get(`${college}|${majorName}`)
    if (exact) return exact
    if (tags && tags.length > 0) return undefined
    const bare = majorName.replace(/[（(].*?[)）]/g, '')
    if (bare === majorName) return undefined
    return byMajorName.get(`${college}|${bare}`)
  }

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const out: { key: string; college: string; campus: string; major: string; level: string; program?: ProgramSummary }[] = []
    for (const college of doc.colleges) {
      for (const major of college.majors) {
        if (needle) {
          const haystack = `${college.name}${major.name}`.toLowerCase()
          if (!haystack.includes(needle)) continue
        }
        out.push({
          key: `${college.name}|${major.name}`,
          college: college.name,
          campus: college.campus,
          major: major.name,
          level: major.level,
          program: matchProgram(college.name, major.name, major.tags),
        })
      }
    }
    return out
    // matchProgram 依赖 programs，后者已进依赖数组
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc, query, byMajorName])

  const ready = rows.filter((r) => r.program)

  return (
    <div className="picker">
      <div className="picker__head">
        <span className="panel__title">专业（{doc.stats.majors}）</span>
        <span className="badge badge--mono">{doc.source.school}</span>
      </div>

      <input
        className="picker__search"
        type="search"
        placeholder="搜索专业或学院…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="搜索专业"
      />

      <div className="picker__list" role="listbox" aria-label="专业列表">
        {ready.length === 0 && rows.length > 0 && (
          <div className="muted small" style={{ padding: '8px 4px' }}>
            没有已接入培养方案的专业
          </div>
        )}
        {ready.map((row) => {
          const summary = row.program!
          const active = summary.id === currentId
          return (
            <button
              key={row.key}
              role="option"
              aria-selected={active}
              className={`picker__item ${active ? 'picker__item--active' : ''}`}
              onClick={() => onPick(summary.id)}
            >
              <span className="picker__item-name">{row.major}</span>
              <span className="picker__item-meta muted tiny">
                {row.college} · {row.campus}
              </span>
              <span className="picker__item-tail">
                {summary.data_status === 'sample' && <span className="badge badge--sample">样例</span>}
                <span className="tabular tiny muted">{summary.course_count} 门</span>
              </span>
            </button>
          )
        })}

        {query && rows.length > ready.length && (
          <div className="picker__more muted tiny">
            另有 {rows.length - ready.length} 个专业匹配，但培养方案尚未接入
          </div>
        )}
      </div>

      <p className="muted tiny" style={{ marginTop: 8 }}>
        专业目录来源：{doc.source.raw_file}（{doc.source.generator}）
      </p>
    </div>
  )
}
