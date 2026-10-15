/** 单个学期泳道：一个放置目标 + 一列课程卡 + 学期学分小计。 */

import { useDroppable } from '@dnd-kit/core'

import type { Course } from '@/api/types'
import { formatCredits, termLabel } from '@/lib/format'
import type { Preview } from '@/lib/localRules'
import { CourseCard } from './CourseCard'

interface Props {
  term: number
  courses: Course[]
  credits: number
  limit: number
  conflictCountByCode: Map<string, number>
  worstSeverityByCode: Map<string, string | null>
  focusCodes: Set<string>
  /** 拖拽中本泳道的预判结果 —— 只做提示，不影响是否允许落下 */
  preview: Preview | null
  onRemoveCourse: (code: string) => void
  onFocusCourse: (code: string) => void
}

export function TermLane({
  term,
  courses,
  credits,
  limit,
  conflictCountByCode,
  worstSeverityByCode,
  focusCodes,
  preview,
  onRemoveCourse,
  onFocusCourse,
}: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: `term-${term}`, data: { term } })

  const overLimit = limit > 0 && credits > limit
  const ratio = limit > 0 ? Math.min(credits / limit, 1) : 0

  return (
    <section
      ref={setNodeRef}
      data-term={term}
      className={[
        'lane',
        isOver ? 'lane--over' : '',
        preview ? `lane--preview-${preview.level}` : '',
      ]
        .filter(Boolean)
        .join(' ')}
      aria-label={termLabel(term)}
    >
      <header className="lane__head">
        <span className="lane__title">{termLabel(term)}</span>
        <span className={`lane__credits tabular ${overLimit ? 'lane__credits--over' : ''}`}>
          {formatCredits(credits)}
          {limit > 0 && <span className="muted"> / {formatCredits(limit)}</span>}
        </span>
      </header>

      {limit > 0 && (
        <div className="lane__meter" aria-hidden="true">
          <div
            className={`lane__meter-fill ${overLimit ? 'lane__meter-fill--over' : ''}`}
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      )}

      <div className="lane__body">
        {courses.length === 0 && <div className="lane__empty muted small">拖课程到这里</div>}
        {courses.map((course) => (
          <CourseCard
            key={course.code}
            course={course}
            term={term}
            conflictCount={conflictCountByCode.get(course.code) ?? 0}
            worstSeverity={worstSeverityByCode.get(course.code) ?? null}
            isFocus={focusCodes.has(course.code)}
            onRemove={() => onRemoveCourse(course.code)}
            onFocus={() => onFocusCourse(course.code)}
          />
        ))}
      </div>

      {preview && preview.level !== 'ok' && preview.reason && (
        <div className={`lane__preview lane__preview--${preview.level}`}>
          <span className="badge badge--mono">预览</span> {preview.reason}
        </div>
      )}
    </section>
  )
}
