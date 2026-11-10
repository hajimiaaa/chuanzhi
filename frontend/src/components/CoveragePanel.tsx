/**
 * 数据覆盖度面板。
 *
 * 存在的理由：评审最容易问「你的数据全不全」。与其让评委自己发现 107 个专业没有
 * 培养方案，不如把"缺什么"直接写在界面上——把不完善从缺陷变成透明的边界。
 */

import type { MajorsDoc, ProgramSummary } from '@/api/types'

type Status = 'ok' | 'partial' | 'missing'

const STATUS_LABEL: Record<Status, string> = {
  ok: '已接入',
  partial: '部分',
  missing: '未接入',
}

interface Props {
  majors: MajorsDoc
  programs: ProgramSummary[]
}

export function CoveragePanel({ majors, programs }: Props) {
  const rows: Array<{ label: string; value: string; status: Status }> = [
    {
      label: '专业目录',
      value: `${majors.stats.majors} 个专业 · ${majors.stats.colleges} 个学院`,
      status: 'ok',
    },
    {
      label: '培养方案',
      value: `${programs.length} / ${majors.stats.majors} 个专业`,
      status: programs.length >= majors.stats.majors ? 'ok' : 'partial',
    },
    { label: '学院转专业方案', value: '0 / 21 份', status: 'missing' },
    { label: '排课时段', value: '未接入', status: 'missing' },
    { label: '学分认定办法', value: '未获取', status: 'missing' },
  ]

  return (
    <section className="panel coverage">
      <div className="panel__head">
        <h2 className="panel__title">数据覆盖度</h2>
      </div>

      <ul className="coverage__list">
        {rows.map((row) => (
          <li key={row.label} className="coverage__row">
            <span className={`coverage__status coverage__status--${row.status}`}>
              {STATUS_LABEL[row.status]}
            </span>
            <span className="coverage__label">{row.label}</span>
            <span className="coverage__value muted tiny">{row.value}</span>
          </li>
        ))}
      </ul>

      <p className="muted tiny coverage__note">
        标「未接入」的部分不假装有数据：涉及它的结论会显式标注或置灰。
      </p>
    </section>
  )
}
