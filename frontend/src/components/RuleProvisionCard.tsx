/**
 * 一条规则条款。
 *
 * 版式顺序是刻意的：**先给原文，再给解释**。`quote` 是逐字引用，校验脚本会回原文复核；
 * 结构化字段（受限方向 / 上限 / 比例）只是帮助阅读，绝不能在视觉上压过原文。
 */

import type { Provision } from '@/api/types'
import { describeProvision, verdictMeta } from '@/lib/ruleMeta'

interface Props {
  provision: Provision
}

export function RuleProvisionCard({ provision }: Props) {
  const verdict = verdictMeta(provision.verdict)
  const facts = describeProvision(provision)

  return (
    <article className="provision" style={{ ['--verdict' as string]: verdict.color }}>
      <header className="provision__head">
        <span className="provision__badge">
          <span aria-hidden="true">{verdict.icon}</span>
          {verdict.label}
        </span>
        <span className="muted tiny">条号 {provision.clause}</span>
      </header>

      <blockquote className="provision__quote">{provision.quote}</blockquote>

      {facts.length > 0 && (
        <ul className="provision__facts">
          {facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}
    </article>
  )
}
