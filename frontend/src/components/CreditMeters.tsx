/**
 * 四个课程类别的学分进度。
 *
 * **刻意用 CSS 而不是 ECharts**：
 *  1. 规划一变 ECharts 要重绘 canvas 带动画，而 CSS 只改一个 width 百分比 ——
 *     拖拽时的手感差别肉眼可见
 *  2. meter 上要放精确标签（"17 / 19 · 差 2"），CSS 里就是一个绝对定位 span
 *  3. 少一条配置路径要维护
 *
 * ⚠️ 配色验证脚本对浅色面给出过一条 WARN：通识(2.74) 与 实践(2.11) 的对比度低于 3:1，
 *    触发「relief 规则」—— **必须有可见标签或表格视图**。
 *    这里两者都给了（每条 meter 带数值标签 + 下方表格视图开关），不是可选项。
 */

import { useState } from 'react'

import type { CreditRule } from '@/api/types'
import { categoryColor, CATEGORY_TRACK_LIGHT, isCategory } from '@/lib/colors'
import { formatCredits, round1 } from '@/lib/format'

interface Props {
  rules: CreditRule[]
  earnedByCategory: Record<string, number>
}

export function CreditMeters({ rules, earnedByCategory }: Props) {
  const [showTable, setShowTable] = useState(false)

  if (rules.length === 0) {
    return <div className="muted small">本培养方案未设分类学分要求。</div>
  }

  return (
    <div className="meters">
      {rules.map((rule) => {
        const earned = round1(earnedByCategory[rule.category] ?? 0)
        const required = round1(rule.min_credits)
        const ratio = required > 0 ? Math.min(earned / required, 1) : 1
        const met = earned >= required
        const delta = round1(Math.abs(earned - required))
        const color = categoryColor(rule.category)
        const track = isCategory(rule.category) ? CATEGORY_TRACK_LIGHT[rule.category] : 'var(--gridline)'

        return (
          <div key={rule.category} className="catmeter">
            <div className="catmeter__row">
              <span className="catmeter__label">
                <span className="catmeter__swatch" style={{ background: color }} aria-hidden="true" />
                {rule.category}
              </span>
              <span className="catmeter__value tabular">
                {formatCredits(earned)}
                <span className="muted"> / {formatCredits(required)}</span>
                <span className={`catmeter__delta ${met ? 'catmeter__delta--ok' : 'catmeter__delta--gap'}`}>
                  {met ? '已达标' : `差 ${formatCredits(delta)}`}
                </span>
              </span>
            </div>
            <div className="catmeter__rail" style={{ background: track }}>
              <div
                className="catmeter__fill"
                style={{ width: `${ratio * 100}%`, background: color }}
              />
            </div>
          </div>
        )
      })}

      <button className="btn btn--quiet tiny" onClick={() => setShowTable((v) => !v)}>
        {showTable ? '收起表格视图' : '表格视图'}
      </button>

      {showTable && (
        <table className="credit-table tabular">
          <thead>
            <tr>
              <th scope="col">类别</th>
              <th scope="col">已修</th>
              <th scope="col">要求</th>
              <th scope="col">差额</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => {
              const earned = round1(earnedByCategory[rule.category] ?? 0)
              const required = round1(rule.min_credits)
              const delta = round1(earned - required)
              return (
                <tr key={rule.category}>
                  <th scope="row">{rule.category}</th>
                  <td>{formatCredits(earned)}</td>
                  <td>{formatCredits(required)}</td>
                  <td className={delta < 0 ? 'credit-table__short' : ''}>
                    {delta >= 0 ? `+${formatCredits(delta)}` : formatCredits(delta)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
