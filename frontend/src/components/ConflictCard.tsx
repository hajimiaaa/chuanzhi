/**
 * 单条冲突。
 *
 * 呈现按"这条冲突在讲什么"分三种：
 *   - 有 expected/actual → 数值对比条（超载 / 学分缺口）
 *   - 课程链（先修、重复安排）→ chips + 箭头，把违反的那一步标出来
 *   - 单门课（开课学期）→ 课程 chip + 从课程库本地取的「实际开课学期」
 *
 * 始终 **icon + 文字 + 颜色三者并存**，不让颜色单独承载语义。
 */

import type { Conflict, Course, Program } from '@/api/types'
import { SEVERITY_COLOR, SEVERITY_ICON, SEVERITY_LABEL } from '@/lib/colors'
import { conflictMeta, hasRatio, meterVariant } from '@/lib/conflictMeta'
import { formatCredits, termLabel } from '@/lib/format'
import { ValueMeter } from './ValueMeter'

interface Props {
  conflict: Conflict
  program: Program
  isFocused: boolean
  onFocus: () => void
}

export function ConflictCard({ conflict, program, isFocused, onFocus }: Props) {
  const meta = conflictMeta(conflict.kind)
  const color = SEVERITY_COLOR[conflict.severity] ?? SEVERITY_COLOR.info
  const courses = new Map(program.courses.map((c) => [c.code, c]))

  return (
    <article
      className={`conflict ${isFocused ? 'conflict--focus' : ''}`}
      onClick={onFocus}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onFocus()
        }
      }}
      role="button"
      tabIndex={0}
      style={{ ['--sev' as string]: color }}
    >
      <header className="conflict__head">
        <span className="conflict__icon" aria-hidden="true">
          {SEVERITY_ICON[conflict.severity] ?? 'i'}
        </span>
        <span className="conflict__kind">{meta.label}</span>
        <span className="conflict__sev muted tiny">{SEVERITY_LABEL[conflict.severity]}</span>
        {conflict.term > 0 && <span className="badge badge--mono">{termLabel(conflict.term)}</span>}
      </header>

      <p className="conflict__message">{conflict.message}</p>

      {hasRatio(conflict) && (
        <ValueMeter
          variant={meterVariant(conflict)}
          actual={conflict.actual ?? 0}
          expected={conflict.expected ?? 0}
        />
      )}

      {!hasRatio(conflict) && conflict.course_codes.length > 0 && (
        <CourseChain codes={conflict.course_codes} courses={courses} />
      )}
    </article>
  )
}

function CourseChain({ codes, courses }: { codes: string[]; courses: Map<string, Course> }) {
  return (
    <div className="chain">
      {codes.map((code, index) => {
        const course = courses.get(code)
        return (
          <span key={`${code}-${index}`} className="chain__item">
            {index > 0 && (
              <span className="chain__arrow" aria-hidden="true">
                →
              </span>
            )}
            <span className="chain__chip">
              <span className="tabular">{code}</span>
              {course && <span className="chain__name">{course.name}</span>}
              {course && <span className="muted tabular tiny">{formatCredits(course.credits)}</span>}
            </span>
          </span>
        )
      })}
    </div>
  )
}
