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
  /** 课程名称可选；填了才能识别跨专业的「同名同学分」课程 */
  name?: string
  credits: number
  grade: number
}

export function makeCompleted(input: TranscriptInput): CompletedCourse {
  return {
    course_code: input.course_code.trim().toUpperCase(),
    name: (input.name ?? '').trim(),
    credits: input.credits,
    grade: input.grade,
    term: '',
    passed: isPassingGrade(input.grade),
  }
}

const t = (course_code: string, name: string, credits: number, grade: number) =>
  makeCompleted({ course_code, name, credits, grade })

/**
 * 演示用成绩单：一位从「软件工程」转到「计算机科学与技术」的学生。
 *
 * 刻意做成 33 门、覆盖五种结果，而不是随手 4 门：
 *  - **课号直接对得上** → 已认定（17 门）
 *  - **修过但没过** → 需重修（1 门）
 *  - **原专业同名同学分、课号不同** → 可能可折抵（10 门），需教务处认定
 *  - **原专业独有课程** → 待认定（5 门）
 *  - 其余由后端按培养方案反推 → 需补修（13 门）
 *
 * 四类（不含待认定）学分严格守恒 = 培养方案 123 学分。
 * 这组数字比"4 门成绩单 → 38 门需补修"可信得多，也是演示时最该讲的差别。
 */
export const SAMPLE_TRANSCRIPT: CompletedCourse[] = [
  // ---- 课号相同且通过：已认定 ----
  t('CS101', '高等数学A(一)', 5, 92),
  t('CS103', '线性代数', 3, 88),
  t('CS105', '程序设计基础', 4, 85),
  t('CS106', '离散数学', 3, 79),
  t('CS201', '数据结构', 4, 81),
  t('CS202', '计算机组成原理', 4, 76),
  t('CS205', '数据库系统原理', 3, 83),
  t('CS207', '软件工程', 3, 90),
  t('CS210', '人工智能导论', 2, 87),
  t('CS211', '计算机专业英语', 2, 84),
  t('CS212', '数字逻辑', 3, 78),
  t('EL101', '数据可视化', 2, 88),
  t('GE101', '思想道德与法治', 3, 86),
  t('GE102', '大学英语(一)', 3, 89),
  t('GE106', '军事理论', 2, 91),
  t('GE107', '中国近现代史纲要', 3, 82),
  t('GE108', '马克思主义基本原理', 3, 80),

  // ---- 课号相同但未通过：需重修 ----
  t('CS203', '操作系统', 4, 52),

  // ---- 原专业同名同学分、课号不同：可能可折抵（需教务处认定）----
  t('SE102', '高等数学A(二)', 5, 84),
  t('SE104', '大学物理(一)', 4, 77),
  t('SE209', '概率论与数理统计', 3, 81),
  t('SE103', '大学英语(二)', 3, 90),
  t('SE104P', '体育(一)', 1, 93),
  t('SE105P', '体育(二)', 1, 89),
  t('SE204', '计算机网络', 3, 79),
  t('SE206', '算法设计与分析', 3, 75),
  t('SE108', '计算机图形学', 2, 82),
  t('SE105', '信息安全', 3, 86),

  // ---- 原专业独有课程：待认定 ----
  t('SE001', '软件工程导论', 3, 85),
  t('SE002', '软件测试技术', 3, 78),
  t('SE003', 'UML建模', 2, 88),
  t('SE004', '软件项目管理', 2, 91),
  t('SE005', '人机交互', 2, 84),
]
