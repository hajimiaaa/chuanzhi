import { describe, expect, it } from 'vitest'

import {
  canRedo,
  canUndo,
  createHistory,
  isDirty,
  planReducer,
  planSignature,
  type PlanAction,
  type PlanHistory,
} from './planReducer'

const run = (state: PlanHistory, ...actions: PlanAction[]) =>
  actions.reduce(planReducer, state)

const termsOf = (state: PlanHistory, code: string) =>
  state.current.items.filter((i) => i.course_code === code).map((i) => i.term)

describe('planReducer', () => {
  it('新建时是空规划，基线也是空的', () => {
    const state = createHistory('p1')
    expect(state.current.items).toEqual([])
    expect(state.origin).toBe('empty')
    expect(canUndo(state)).toBe(false)
    expect(isDirty(state)).toBe(false)
  })

  it('MOVE_COURSE 是原子的：不会留下重复条目', () => {
    const state = run(createHistory('p1'), { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 1 })
    expect(termsOf(state, 'CS101')).toEqual([1])

    const moved = planReducer(state, { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 4 })
    // 这正是用 reducer 而不是两次 setState 的原因：中间态不可观测
    expect(termsOf(moved, 'CS101')).toEqual([4])
    expect(moved.current.items).toHaveLength(1)
  })

  it('移到同一个学期是无操作，不污染撤销栈', () => {
    const state = run(createHistory('p1'), { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 2 })
    const same = planReducer(state, { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 2 })
    expect(same).toBe(state)
    expect(same.past).toHaveLength(1)
  })

  it('非法学期被拒绝', () => {
    const state = createHistory('p1')
    expect(planReducer(state, { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 0 })).toBe(state)
    expect(planReducer(state, { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 1.5 })).toBe(state)
  })

  it('items 始终按 (学期, 课程代码) 排序', () => {
    const state = run(
      createHistory('p1'),
      { type: 'MOVE_COURSE', courseCode: 'ZZZ', toTerm: 1 },
      { type: 'MOVE_COURSE', courseCode: 'AAA', toTerm: 3 },
      { type: 'MOVE_COURSE', courseCode: 'BBB', toTerm: 1 },
    )
    expect(state.current.items.map((i) => i.course_code)).toEqual(['BBB', 'ZZZ', 'AAA'])
  })

  it('撤销与重做', () => {
    const state = run(
      createHistory('p1'),
      { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 1 },
      { type: 'MOVE_COURSE', courseCode: 'CS102', toTerm: 2 },
    )
    expect(state.current.items).toHaveLength(2)

    const undone = planReducer(state, { type: 'UNDO' })
    expect(undone.current.items.map((i) => i.course_code)).toEqual(['CS101'])
    expect(canRedo(undone)).toBe(true)

    const redone = planReducer(undone, { type: 'REDO' })
    expect(redone.current.items).toHaveLength(2)

    expect(planReducer(createHistory('p1'), { type: 'UNDO' }).current.items).toEqual([])
  })

  it('新变更会清空重做栈', () => {
    const state = run(
      createHistory('p1'),
      { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 1 },
      { type: 'UNDO' },
      { type: 'MOVE_COURSE', courseCode: 'CS102', toTerm: 2 },
    )
    expect(canRedo(state)).toBe(false)
  })

  it('REPLACE_PLAN 同时设定基线，随后 RESET 可回到它', () => {
    const baselineItems = [
      { course_code: 'CS101', term: 1 },
      { course_code: 'CS102', term: 2 },
    ]
    const state = run(
      createHistory('p1'),
      {
        type: 'REPLACE_PLAN',
        plan: { programId: 'p1', items: baselineItems, completed: [] },
        origin: 'sample',
        asBaseline: true,
      },
      { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 5 },
    )
    expect(isDirty(state)).toBe(true)

    const reset = planReducer(state, { type: 'RESET_TO_SAMPLE' })
    expect(reset.current.items).toEqual([
      { course_code: 'CS101', term: 1 },
      { course_code: 'CS102', term: 2 },
    ])
    expect(isDirty(reset)).toBe(false)
  })

  it('已经在基线上时 RESET 是无操作', () => {
    const state = run(createHistory('p1'), {
      type: 'REPLACE_PLAN',
      plan: { programId: 'p1', items: [{ course_code: 'CS101', term: 1 }], completed: [] },
      origin: 'sample',
      asBaseline: true,
    })
    expect(planReducer(state, { type: 'RESET_TO_SAMPLE' })).toBe(state)
  })

  it('REMOVE_COURSE 与 CLEAR', () => {
    const state = run(
      createHistory('p1'),
      { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 1 },
      { type: 'MOVE_COURSE', courseCode: 'CS102', toTerm: 2 },
    )
    expect(planReducer(state, { type: 'REMOVE_COURSE', courseCode: 'CS101' }).current.items).toHaveLength(1)
    expect(planReducer(state, { type: 'CLEAR' }).current.items).toEqual([])
    // 移除不存在的课 = 无操作
    expect(planReducer(state, { type: 'REMOVE_COURSE', courseCode: 'NOPE' })).toBe(state)
    // 已经空了再清空 = 无操作
    expect(planReducer(planReducer(state, { type: 'CLEAR' }), { type: 'CLEAR' }).current.items).toEqual([])
  })

  it('SET_PROGRAM 切换专业时重置历史与基线', () => {
    const state = run(createHistory('p1'), { type: 'MOVE_COURSE', courseCode: 'CS101', toTerm: 1 })
    const switched = planReducer(state, { type: 'SET_PROGRAM', programId: 'p2' })
    expect(switched.current.programId).toBe('p2')
    expect(switched.current.items).toEqual([])
    expect(switched.past).toEqual([])
    expect(switched.origin).toBe('empty')
  })

  it('签名对输入顺序不敏感 —— 校验去重依赖这一点', () => {
    const a = { programId: 'p1', items: [{ course_code: 'B', term: 2 }, { course_code: 'A', term: 1 }], completed: [] }
    const b = { programId: 'p1', items: [{ course_code: 'A', term: 1 }, { course_code: 'B', term: 2 }], completed: [] }
    expect(planSignature(a)).toBe(planSignature(b))
  })

  it('签名能区分不同学期', () => {
    const a = { programId: 'p1', items: [{ course_code: 'A', term: 1 }], completed: [] }
    const b = { programId: 'p1', items: [{ course_code: 'A', term: 2 }], completed: [] }
    expect(planSignature(a)).not.toBe(planSignature(b))
  })
})
