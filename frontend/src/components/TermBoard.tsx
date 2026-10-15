/**
 * 四年排课板：8 个学期泳道 + 拖拽上下文。
 *
 * 用 @dnd-kit 而不是原生 HTML5 DnD，主要为了三件事：
 *  1. `<DragOverlay>` 能渲染真实卡片，拖动中不掉样式
 *  2. `isOver` 直接给出目标泳道，不需要用 enter/leave 计数器 hack —— 原生写法在这里会闪烁
 *  3. 触屏与键盘可达性开箱即得
 *
 * ⚠️ `activationConstraint: { distance: 6 }` 必须设：不设的话点一下卡片就被判成拖拽，
 *    onClick 永不触发，症状是"点击课程没反应"，很难查。
 */

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  pointerWithin,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { useMemo, useState } from 'react'

import type { Conflict, Course, PlanItem, Program } from '@/api/types'
import { courseIndex } from '@/lib/derive'
import { previewDrop, type Preview } from '@/lib/localRules'
import { CourseCardBody } from './CourseCard'
import { LunchTray } from './LunchTray'
import { TermLane } from './TermLane'

interface Props {
  program: Program
  items: PlanItem[]
  conflicts: Conflict[]
  focusCodes: Set<string>
  /** 尚未排入的课程 —— 与板子共用同一个拖拽上下文，才能从这里拖回学期 */
  unplaced: Course[]
  unscheduled: string[]
  onMove: (courseCode: string, toTerm: number) => void
  onRemove: (courseCode: string) => void
  onFocusCourse: (courseCode: string) => void
}

export function TermBoard({
  program,
  items,
  conflicts,
  focusCodes,
  unplaced,
  unscheduled,
  onMove,
  onRemove,
  onFocusCourse,
}: Props) {
  const [activeCode, setActiveCode] = useState<string | null>(null)
  const [overTerm, setOverTerm] = useState<number | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )

  const index = useMemo(() => courseIndex(program), [program])

  const { byTerm, conflictCountByCode, worstSeverityByCode } = useMemo(() => {
    const terms = new Map<number, Course[]>()
    for (let t = 1; t <= program.total_terms; t += 1) terms.set(t, [])
    for (const item of items) {
      const course = index.get(item.course_code)
      if (course && terms.has(item.term)) terms.get(item.term)!.push(course)
    }

    const counts = new Map<string, number>()
    const severity = new Map<string, string | null>()
    const rank: Record<string, number> = { error: 0, warning: 1, info: 2 }
    for (const conflict of conflicts) {
      for (const code of conflict.course_codes) {
        counts.set(code, (counts.get(code) ?? 0) + 1)
        const current = severity.get(code) ?? null
        if (current === null || (rank[conflict.severity] ?? 9) < (rank[current] ?? 9)) {
          severity.set(code, conflict.severity)
        }
      }
    }
    return { byTerm: terms, conflictCountByCode: counts, worstSeverityByCode: severity }
  }, [program.total_terms, items, index, conflicts])

  const creditsByTerm = useMemo(() => {
    const map = new Map<number, number>()
    for (const item of items) {
      const course = index.get(item.course_code)
      if (course) map.set(item.term, (map.get(item.term) ?? 0) + course.credits)
    }
    return map
  }, [items, index])

  const activeCourse = activeCode ? index.get(activeCode) : undefined

  /** 拖拽中：对**目标学期**做本地预判，只用于高亮与原因气泡 */
  const previewByTerm = useMemo(() => {
    const map = new Map<number, Preview>()
    if (!activeCourse || overTerm === null) return map
    const current = items.find((i) => i.course_code === activeCourse.code)
    if (current && current.term === overTerm) return map
    map.set(overTerm, previewDrop(program, items, activeCourse, overTerm))
    return map
  }, [activeCourse, overTerm, items, program])

  function handleDragStart(event: DragStartEvent) {
    setActiveCode(String(event.active.id))
  }

  function handleDragOver(event: DragOverEvent) {
    const term = event.over?.data.current?.term
    setOverTerm(typeof term === 'number' ? term : null)
  }

  function handleDragEnd(event: DragEndEvent) {
    const term = event.over?.data.current?.term
    setActiveCode(null)
    setOverTerm(null)
    // ⚠️ 即使本地预判是 blocked 也照常提交 —— 服务端才是权威，
    //    而且演示脚本本身就是要制造冲突
    if (typeof term === 'number') {
      onMove(String(event.active.id), term)
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={() => {
        setActiveCode(null)
        setOverTerm(null)
      }}
    >
      <div className="board">
        {Array.from({ length: program.total_terms }, (_, i) => i + 1).map((term) => (
          <TermLane
            key={term}
            term={term}
            courses={byTerm.get(term) ?? []}
            credits={creditsByTerm.get(term) ?? 0}
            limit={program.max_credits_per_term}
            conflictCountByCode={conflictCountByCode}
            worstSeverityByCode={worstSeverityByCode}
            focusCodes={focusCodes}
            preview={previewByTerm.get(term) ?? null}
            onRemoveCourse={onRemove}
            onFocusCourse={onFocusCourse}
          />
        ))}
      </div>

      <LunchTray unplaced={unplaced} unscheduled={unscheduled} />

      <DragOverlay dropAnimation={null}>
        {activeCourse ? (
          <div style={{ width: 196 }}>
            <CourseCardBody
              course={activeCourse}
              conflictCount={conflictCountByCode.get(activeCourse.code) ?? 0}
              worstSeverity={worstSeverityByCode.get(activeCourse.code) ?? null}
              dragging
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
