/**
 * 核对单的纯文本导出。用于「复制为文本」——学生可以直接贴到 QQ/微信问学长或辅导员。
 * 纯函数，可单测。
 */

import type { AuditConfidence, AuditSheetResponse } from '@/api/types'

export const CONFIDENCE_LABEL: Record<AuditConfidence, string> = {
  high: '高置信',
  medium: '中置信 · 需确认',
  low: '低置信',
}

export function formatAuditSheet(data: AuditSheetResponse): string {
  const lines: string[] = []

  lines.push(`转专业学分核对单 · ${data.program.name}`)
  lines.push(
    `${data.program.college} · 数据状态：${data.program.data_status === 'official' ? '官方' : '样例'}`,
  )
  lines.push(`生成时间：${data.generated_at} · 引擎 v${data.engine_version}`)
  lines.push('')

  for (const check of data.self_check) {
    lines.push(`[${check.passed ? '✓' : '✕'}] ${check.name}：${check.detail}`)
  }

  for (const section of data.sections) {
    lines.push('')
    lines.push(
      `== ${section.title}（${section.cases.length} 门 · ${CONFIDENCE_LABEL[section.confidence]}）==`,
    )
    lines.push(`该做什么：${section.action}`)
    for (const item of section.cases) {
      const grade =
        item.grade !== null && item.grade !== '' ? ` · 成绩 ${item.grade}` : ''
      lines.push(
        `- ${item.course_code} ${item.name || '（原专业课程）'} ${item.credits} 学分${grade}`,
      )
    }
  }

  lines.push('')
  lines.push('下一步：')
  for (const action of data.next_actions) {
    lines.push(`${action.step}. ${action.text}（${action.where}）`)
  }

  lines.push('')
  lines.push(data.disclaimer)
  return lines.join('\n')
}
