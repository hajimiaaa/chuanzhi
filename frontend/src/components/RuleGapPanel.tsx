/**
 * 「查不到的类别」。
 *
 * 位置与语义都对应 ConflictPanel 底部的 BoundaryNotes：**不混进主列表**。
 * 但它比 BoundaryNotes 更重要 —— 认知入口真正值钱的地方，一半在这里：
 * 学生最想知道的问题（分数卡多少、要不要面试）校级通知答不了，
 * 如实说"答不了 + 去学院方案里找"本身就是答案。
 *
 * `absent_keywords` 折叠成「为什么判定没有」：那是负向断言的证据，
 * 不是装饰 —— 让"我们没找到"成为一句可被复核的话。
 */

import type { RuleGap } from '@/api/types'
import { categoryLabel, gapStatusLabel } from '@/lib/ruleMeta'

interface Props {
  gaps: RuleGap[]
  /** 当前筛选的类别：对应的缺口高亮，方便把"这里为什么是空的"接上 */
  activeCategory: string | null
}

export function RuleGapPanel({ gaps, activeCategory }: Props) {
  return (
    <section className="panel">
      <header className="panel__head">
        <h2 className="panel__title">查不到的类别</h2>
        <span className="muted tiny">{gaps.length} 处</span>
      </header>

      <p className="muted tiny gap__intro">
        这些问题校级通知回答不了。标出来，比编一个数字有用。
      </p>

      {gaps.map((gap) => (
        <div
          key={gap.category}
          className={`gap ${activeCategory === gap.category ? 'gap--active' : ''}`}
        >
          <div className="gap__head">
            <span className="small">{categoryLabel(gap.category)}</span>
            <span
              className={`badge ${
                gap.status === 'not_available' ? 'badge--gap-critical' : 'badge--gap-partial'
              }`}
            >
              {gapStatusLabel(gap.status)}
            </span>
          </div>

          <p className="small secondary gap__detail">{gap.detail}</p>

          {gap.where_to_find && (
            <p className="muted tiny gap__where">去哪查：{gap.where_to_find}</p>
          )}

          {gap.absent_keywords.length > 0 && (
            <details className="gap__evidence">
              <summary className="muted tiny">为什么判定「没有」</summary>
              <p className="muted tiny">
                这些词在原文里一次都没出现：{gap.absent_keywords.join(' / ')}
              </p>
              {gap.evidence_clause && (
                <p className="muted tiny">相关条款：{gap.evidence_clause}</p>
              )}
            </details>
          )}
        </div>
      ))}
    </section>
  )
}
