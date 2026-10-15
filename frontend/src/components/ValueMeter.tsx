/**
 * 数值对比条。后端 `Conflict` 的 `expected` / `actual` 就是给这个用的
 * （见 backend/app/models.py 里 Conflict 的注释）。
 *
 * 两种变体**必须分开**，因为语义相反：
 *   over —— 越界（如 28 / 26 学分）。填充会**画到轨道之外**，让"越界"在几何上可见，
 *           而不只是变个颜色。
 *   gap  —— 还差（如 17 / 19 学分）。缺口段留白，右端用虚线刻度标出目标。
 * 长得一样会让人读错方向。
 */

import { formatCredits } from '@/lib/format'

export type MeterVariant = 'over' | 'gap'

interface Props {
  variant: MeterVariant
  actual: number
  expected: number
  unit?: string
}

export function ValueMeter({ variant, actual, expected, unit = '学分' }: Props) {
  const max = Math.max(expected, actual, 0.0001)
  const trackPct = Math.max(0, Math.min(100, (expected / max) * 100))
  const fillPct = Math.max(0, Math.min(100, (actual / max) * 100))
  const delta = Math.abs(actual - expected)

  return (
    <div className="meter">
      <div className="meter__rail">
        <div className="meter__track" style={{ width: `${trackPct}%` }} />
        <div
          className={`meter__fill meter__fill--${variant}`}
          style={{ width: `${fillPct}%` }}
          role="img"
          aria-label={`${formatCredits(actual)} / ${formatCredits(expected)} ${unit}`}
        />
        <div className="meter__tick" style={{ left: `${trackPct}%` }} />
      </div>
      <div className="meter__caption tabular">
        <span className="secondary">
          {formatCredits(actual)} / {formatCredits(expected)} {unit}
        </span>
        <span className={`meter__delta meter__delta--${variant}`}>
          {variant === 'over'
            ? `超出 ${formatCredits(delta)}`
            : `差 ${formatCredits(delta)}`}
        </span>
      </div>
    </div>
  )
}
