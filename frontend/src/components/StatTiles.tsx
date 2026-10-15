/**
 * 顶部关键数字。
 *
 * 「距离毕业还差多少」是一个**单一数字对阈值**的问题 —— 按 dataviz 的选型原则，
 * 这类问题的正确形式是 Hero 数字 + meter，**不是图表**。
 * 堆叠柱留给"每学期负荷"那个真正需要比较的问题。
 */

import { formatCredits, round1 } from '@/lib/format'

interface Props {
  totalEarned: number
  totalMin: number
  errorCount: number
  warningCount: number
  placedCourses: number
  totalCourses: number
}

export function StatTiles({
  totalEarned,
  totalMin,
  errorCount,
  warningCount,
  placedCourses,
  totalCourses,
}: Props) {
  const earned = round1(totalEarned)
  const gap = round1(Math.max(totalMin - earned, 0))
  const met = earned >= totalMin
  const ratio = totalMin > 0 ? Math.min(earned / totalMin, 1) : 1

  return (
    <section className="panel stats">
      <div className="stats__hero">
        <div className="stats__figure tabular">
          {formatCredits(earned)}
          <span className="stats__figure-den muted"> / {formatCredits(totalMin)}</span>
        </div>
        <div className="stats__figure-label">
          总学分
          {met ? (
            <span className="stats__ok"> 已达毕业要求</span>
          ) : (
            <span className="muted"> · 还差 {formatCredits(gap)} 学分</span>
          )}
        </div>
        <div className="stats__rail" aria-hidden="true">
          <div className="stats__fill" style={{ width: `${ratio * 100}%` }} />
        </div>
      </div>

      <div className="stats__tiles">
        <div className="tile">
          <div className="tile__value tabular">
            {placedCourses}
            <span className="muted"> / {totalCourses}</span>
          </div>
          <div className="tile__label">已排课程</div>
        </div>
        <div className="tile">
          <div className={`tile__value tabular ${errorCount > 0 ? 'tile__value--bad' : ''}`}>
            {errorCount}
          </div>
          <div className="tile__label">错误</div>
        </div>
        <div className="tile">
          <div className={`tile__value tabular ${warningCount > 0 ? 'tile__value--warn' : ''}`}>
            {warningCount}
          </div>
          <div className="tile__label">警告</div>
        </div>
      </div>
    </section>
  )
}
