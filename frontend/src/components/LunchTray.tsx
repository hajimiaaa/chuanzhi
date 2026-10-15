/**
 * 未排入的课程（以及后端 `unscheduled` 里排不下的课）。
 *
 * 这里就是"课程库"：从板子上移除的课会落回这里，再从这儿拖回任意学期。
 * 所以不需要再单独做一个课程库组件。
 */

import { useDraggable } from '@dnd-kit/core'

import type { Course } from '@/api/types'
import { formatCredits } from '@/lib/format'

function TrayChip({ course }: { course: Course }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: course.code,
    data: { fromTerm: null },
  })

  return (
    <div
      ref={setNodeRef}
      className={`chip chip--draggable ${isDragging ? 'chip--dragging' : ''}`}
      title={`${course.name} · ${formatCredits(course.credits)} 学分`}
      {...attributes}
      {...listeners}
    >
      <span className="tabular">{course.code}</span>
      <span className="chip__name">{course.name}</span>
      <span className="muted tabular">{formatCredits(course.credits)}</span>
    </div>
  )
}

interface Props {
  /** 培养方案里所有尚未排入的课程 */
  unplaced: Course[]
  /** 后端明确说排不下的课程代码（planner 的 unscheduled） */
  unscheduled: string[]
}

export function LunchTray({ unplaced, unscheduled }: Props) {
  if (unplaced.length === 0 && unscheduled.length === 0) return null

  return (
    <section className="tray">
      <header className="tray__head">
        <span className="panel__title">未排入 · {unplaced.length}</span>
        <span className="muted tiny">拖到任意学期即可加入</span>
      </header>

      {unscheduled.length > 0 && (
        <div className="tray__note">
          <span className="badge">排不下</span>
          <span className="small secondary">
            {unscheduled.join('、')} —— 后端规划器无法在学制内为这些课找到位置
          </span>
        </div>
      )}

      <div className="tray__body">
        {unplaced.map((course) => (
          <TrayChip key={course.code} course={course} />
        ))}
        {unplaced.length === 0 && <span className="muted small">全部课程都已排入</span>}
      </div>
    </section>
  )
}
