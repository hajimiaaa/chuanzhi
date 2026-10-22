/**
 * 认知入口：转专业规则查询。
 *
 * 三条信息架构决定：
 *  1. **先原文后解释**：条款卡把逐字引用放在结构化字段之上。结构化字段是辅助阅读，
 *     一旦视觉上压过原文，产品就变成了"我们替你解读" —— 那是这个项目明确不做的。
 *  2. **缺口不混进条款列表**：右侧独立成块，位置与语义对应 ConflictPanel 的 BoundaryNotes。
 *     它不随筛选隐藏 —— 那正是认知入口最该被看见的东西。
 *  3. **过滤后的 0 是合法结果，不是错误**：显示「这一类通知里没有条款」并指向缺口，
 *     而不是空列表或 404。`stats` 始终描述整份文件，所以要把「3 条 / 全文 17 条」写清楚，
 *     否则看起来像 bug。
 */

import { useState } from 'react'

import type { RuleCategory } from '@/api/types'
import { RuleGapPanel } from '@/components/RuleGapPanel'
import { RuleProvisionCard } from '@/components/RuleProvisionCard'
import { useRuleDoc, useRuleList } from '@/hooks/useRules'
import {
  CATEGORY_QUESTION,
  RULE_CATEGORY_ORDER,
  categoriesWithoutProvisions,
  categoryLabel,
  gapByCategory,
  groupProvisions,
} from '@/lib/ruleMeta'

export function RulesView() {
  const list = useRuleList()
  const [category, setCategory] = useState<RuleCategory | null>(null)

  // 目前只有一份校级通知。未来 21 份学院方案进来时，这里换成选择器即可，接口不用改。
  const ruleId = list.items[0]?.id ?? null
  const rule = useRuleDoc(ruleId, category)
  const doc = rule.doc

  const errorText = list.error || rule.error

  if (!doc) {
    const noDocs = list.status === 'ready' && list.items.length === 0
    return (
      <div className="panel rules__placeholder">
        <p className="secondary small">
          {noDocs ? '后端没有可用的规则文件（data/rules/ 为空）。' : errorText || '正在加载转专业规则…'}
        </p>
        {noDocs && (
          <p className="muted tiny">
            先运行 <code>py -3.11 tools/build_rules_json.py</code> 生成规则数据。
          </p>
        )}
        {errorText && (
          <button
            className="btn tiny"
            onClick={() => {
              list.retry()
              rule.reload()
            }}
          >
            重试
          </button>
        )}
      </div>
    )
  }

  const gaps = gapByCategory(doc.gaps)
  const groups = groupProvisions(doc.provisions)
  const emptyCategories = categoriesWithoutProvisions(doc.stats)
  const matched =
    doc.filter && doc.filter.category === category ? doc.filter.matched : null

  return (
    <div className={`shell__body ${rule.loading ? 'rules--loading' : ''}`}>
      <main className="shell__main">
        <header className="panel rules__header">
          <div className="rules__title-row">
            <h2 className="rules__title">{doc.title}</h2>
            <span
              className={`badge ${doc.data_status === 'official' ? 'badge--official' : 'badge--sample'}`}
            >
              {doc.data_status === 'official' ? '官方文件' : '样例数据'}
            </span>
            {rule.stale && (
              <span className="badge badge--stale" title={rule.error}>
                已过期
              </span>
            )}
          </div>
          <p className="small secondary rules__meta">
            发布：{doc.source.issuer || doc.source.school}
            {doc.source.issued_date ? ` · ${doc.source.issued_date}` : ''}
          </p>
          <p className="small secondary rules__meta">
            适用：{doc.applies_to.grade} · {doc.applies_to.student_types.join(' / ')}
          </p>
        </header>

        {rule.stale && (
          <div className="rules__stale small">
            本次请求失败，下方为<strong>上一次</strong>的结果：{rule.error}
          </div>
        )}

        <div className="rules__chips" role="group" aria-label="按规则类别筛选">
          <button
            className={`chip ${category === null ? 'chip--active' : ''}`}
            onClick={() => setCategory(null)}
          >
            全部 <span className="rules__count">{doc.stats.provisions}</span>
          </button>

          {RULE_CATEGORY_ORDER.map((item) => {
            const count = doc.stats.by_category[item] ?? 0
            const hasGap = gaps.has(item)
            return (
              <button
                key={item}
                className={`chip ${category === item ? 'chip--active' : ''} ${count === 0 ? 'chip--empty' : ''}`}
                onClick={() => setCategory(category === item ? null : item)}
                title={count === 0 && hasGap ? '通知里没有这一类条款，原因见右侧缺口' : undefined}
              >
                {categoryLabel(item)} <span className="rules__count">{count}</span>
                {count === 0 && hasGap && <span className="rules__hint">未规定</span>}
              </button>
            )
          })}
        </div>

        {category !== null && (
          <p className="muted tiny rules__summary">
            {categoryLabel(category)} · {matched === null ? '…' : matched} 条 / 全文{' '}
            {doc.stats.provisions} 条
            {rule.loading && ' · 更新中…'}
          </p>
        )}

        {groups.length === 0 ? (
          <div className="panel">
            <div className="rules__empty">
              <div className="rules__empty-title">这一类通知里没有条款</div>
              {category && (
                <p className="muted small">{CATEGORY_QUESTION[category]}</p>
              )}
              {category && gaps.has(category) ? (
                <p className="muted tiny">
                  不是我们漏了，是校级通知本身没规定。原因与去处见右侧「查不到的类别」。
                </p>
              ) : (
                <p className="muted tiny">换一个类别，或点「全部」看完整条款。</p>
              )}
            </div>
          </div>
        ) : (
          groups.map(([groupCategory, items]) => (
            <section className="panel" key={groupCategory}>
              <div className="panel__head">
                <h3 className="panel__title">{categoryLabel(groupCategory)}</h3>
                <span className="shell__spacer" />
                <span className="muted tiny">{items.length} 条</span>
              </div>
              <p className="muted tiny rules__group-question">
                {CATEGORY_QUESTION[groupCategory as RuleCategory] ?? ''}
              </p>
              <div className="rules__group">
                {items.map((provision) => (
                  <RuleProvisionCard key={provision.id} provision={provision} />
                ))}
              </div>
            </section>
          ))
        )}

        {emptyCategories.length > 0 && category === null && (
          <p className="muted tiny rules__footnote">
            另有 {emptyCategories.map((item) => categoryLabel(item)).join('、')}{' '}
            等类别，通知里没有对应条款 —— 见右侧「查不到的类别」。
          </p>
        )}
      </main>

      <aside className="shell__aside">
        <RuleGapPanel gaps={doc.gaps} activeCategory={category} />

        <section className="panel">
          <header className="panel__head">
            <h2 className="panel__title">时间线</h2>
            <span className="muted tiny">{doc.timeline.length} 个节点</span>
          </header>
          <ol className="timeline">
            {doc.timeline.map((step) => (
              <li key={step.id} className="timeline__item">
                <span className="timeline__date tabular">{step.deadline}</span>
                <div>
                  <div className="small">{step.label}</div>
                  <details className="timeline__quote">
                    <summary className="muted tiny">{step.clause} 原文</summary>
                    <p className="muted tiny">{step.quote}</p>
                  </details>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <details className="panel">
          <summary className="panel__title" style={{ cursor: 'pointer' }}>
            数据来源与边界
          </summary>
          <p className="small secondary" style={{ marginBottom: 4 }}>
            {doc.source.origin}
          </p>
          <p className="muted tiny" style={{ marginBottom: 2 }}>
            原文：{doc.source.raw_file}
          </p>
          <p className="muted tiny" style={{ marginBottom: 2 }}>
            生成：{doc.source.generator}
          </p>
          <p className="muted tiny" style={{ marginBottom: 0 }}>
            {doc.note}
          </p>
        </details>
      </aside>
    </div>
  )
}
