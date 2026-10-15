/** 课程卡片。既是被拖拽单元，也被 DragOverlay 复用为拖拽中的浮层。 */

import { useDraggable } from '@dnd-kit/core'

import type { Course } from '@/api/types'
import { SEVERITY_COLOR } from '@/lib/colors'
import { formatCredits } from '@/lib/format'

export interface CourseCardBodyProps {
  course: Course
  /** 与这门课相关的冲突数（0 = 无冲突） */
  conflictCount?: number
  /** 相关冲突里最严重的级别，决定左侧竖条与角标颜色 */
  worstSeverity?: string | null
  isFocus?: boolean
  dragging?: boolean
}

export function CourseCardBody({
  course,
  conflictCount = 0,
  worstSeverity = null,
  isFocus = false,
  dragging = false,
}: CourseCardBodyProps) {
  const stripe = worstSeverity ? SEVERITY_COLOR[worstSeverity] : categoryVar(course.category)

  return (
    <div
      className={[
        'course',
        conflictCount > 0 ? 'course--conflict' : '',
        isFocus ? 'course--focus' : '',
        dragging ? 'course--dragging' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{ ['--stripe' as string]: stripe }}
    >
      <span className="course__code tabular">{course.code}</span>
      <span className="course__name" title={course.name}>
        {course.name}
      </span>
      <span className="course__credits tabular">{formatCredits(course.credits)}</span>
      {conflictCount > 0 && (
        <span className="course__flag" title={`${conflictCount} 条冲突`} aria-label={`${conflictCount} 条冲突`}>
          {conflictCount}
        </span>
      )}
    </div>
  )
}

function categoryVar(category: string): string {
  switch (category) {
    case '必修':
      return 'var(--cat-required)'
    case '专业选修':
      return 'var(--cat-elective)'
    case '通识':
      return 'var(--cat-general)'
    case '实践':
      return 'var(--cat-practice)'
    default:
      return 'var(--cat-fallback)'
  }
}

interface CourseCardProps extends CourseCardBodyProps {
  course: Course
  term: number
  onRemove: () => void
  onFocus: () => void
}

export function CourseCard({
  course,
  term,
  conflictCount = 0,
  worstSeverity = null,
  isFocus = false,
  onRemove,
  onFocus,
}: CourseCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: course.code,
    data: { fromTerm: term },
  })

  return (
    <div
      ref={setNodeRef}
      data-course={course.code}
      // dnd-kit 的 attributes 已带 role="button" 与 tabIndex=0，无需重复声明
      {...attributes}
      {...listeners}
      className="course-slot"
      onClick={onFocus}
      onKeyDown={(event) => {
        if (event.key === 'Delete' || event.key === 'Backspace') {
          event.preventDefault()
          onRemove()
        }
      }}
      aria-label={`${course.code} ${course.name}，${formatCredits(course.credits)} 学分，第 ${term} 学期`}
    >
      <CourseCardBody
        course={course}
        conflictCount={conflictCount}
        worstSeverity={worstSeverity}
        isFocus={isFocus}
        dragging={isDragging}
      />
      <button
        className="course-slot__remove"
        title="移出规划（Delete）"
        aria-label={`把 ${course.code} 移出规划`}
        onClick={(event) => {
          event.stopPropagation()
          onRemove()
        }}
        // 别让移除按钮成为拖拽把手
        onPointerDown={(event) => event.stopPropagation()}
      >
        ×
      </button>
    </div>
  )
}
