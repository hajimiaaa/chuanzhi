/**
 * 已修成绩单的录入与本地判定。纯函数，可在 node 环境单测。
 *
 * 前端只收数字分数，不处理「优 / 良 / 合格」这类等级成绩 —— 那需要各校自己的
 * 换算表，而我们没有。后端 `models._grade_passed` 支持文本等级，但界面不暴露，
 * 免得让用户以为等级成绩也能直接算。
 */

import type { CompletedCourse } from '@/api/types'

/** 与后端 `models.PASS_MARK` 保持一致 */
export const PASS_MARK = 60

export function isPassingGrade(grade: number): boolean {
  return grade >= PASS_MARK
}

export interface TranscriptInput {
  course_code: string
  credits: number
  grade: number
}

export function makeCompleted(input: TranscriptInput): CompletedCourse {
  return {
    course_code: input.course_code.trim().toUpperCase(),
    credits: input.credits,
    grade: input.grade,
    term: '',
    passed: isPassingGrade(input.grade),
  }
}

/**
 * 演示用成绩单。刻意覆盖四种结果，让「加载示例」一次就能看到完整机制：
 *   CS101 / CS105 → 在培养方案里且通过 → 已认定
 *   CS201         → 在培养方案里但没通过 → 需重修
 *   CE101         → 原专业课程，不在培养方案课程库 → 待认定
 * 其余课程由后端按培养方案反推为「需补修」。
 */
export const SAMPLE_TRANSCRIPT: CompletedCourse[] = [
  makeCompleted({ course_code: 'CS101', credits: 5, grade: 92 }),
  makeCompleted({ course_code: 'CS105', credits: 4, grade: 76 }),
  makeCompleted({ course_code: 'CS201', credits: 4, grade: 55 }),
  makeCompleted({ course_code: 'CE101', credits: 3, grade: 88 }),
]
