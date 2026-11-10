/**
 * 转专业学分核对单：一页 A4，可打印、可签字、可复制成文本。
 *
 * 这是对「产品功能不完善导致学生没拿到学分怎么办」的直接回答：
 * 输出的不是最终结论，而是一份**写明哪几条确定、哪几条需要人去确认**的草案。
 *
 * 两条纪律：
 *  1. 样例数据下**打印按钮置灰**——不生成一张"看起来能签字"的单子
 *  2. 页脚始终写明"以教务系统与教务处审核结果为准"
 */

import type { AuditSheetResponse } from '@/api/types'
import { CONFIDENCE_LABEL, formatAuditSheet } from '@/lib/auditText'

interface Props {
  data: AuditSheetResponse
  onClose: () => void
}

export function CreditAuditSheet({ data, onClose }: Props) {
  const official = data.program.data_status === 'official'

  return (
    <div className="audit-overlay" role="dialog" aria-modal="true" aria-label="转专业学分核对单">
      <article className="audit">
        <header className="audit__head">
          <div>
            <h2 className="audit__title">转专业学分核对单</h2>
            <p className="audit__sub">
              {data.program.name} · {data.program.college}
            </p>
          </div>
          <button className="btn tiny audit__close" onClick={onClose}>
            关闭
          </button>
        </header>

        {!data.printable && (
          <div className="audit__banner">样例数据 · 不可用于真实毕业审核</div>
        )}

        <dl className="audit__meta">
          <div>
            <dt>数据状态</dt>
            <dd>{official ? '官方培养方案' : '样例数据'}</dd>
          </div>
          <div>
            <dt>专业目录</dt>
            <dd>{data.program.catalog_ref || '—'}</dd>
          </div>
          <div>
            <dt>生成时间</dt>
            <dd>{data.generated_at}</dd>
          </div>
          <div>
            <dt>引擎版本</dt>
            <dd>v{data.engine_version}</dd>
          </div>
        </dl>

        <ul className="audit__check">
          {data.self_check.map((check) => (
            <li
              key={check.name}
              className={check.passed ? 'audit__check--ok' : 'audit__check--bad'}
            >
              <span aria-hidden="true">{check.passed ? '✓' : '✕'}</span> {check.name}：
              {check.detail}
            </li>
          ))}
        </ul>

        {data.sections.map((section) => (
          <section key={section.key} className="audit__section">
            <h3 className="audit__section-title">
              {section.title}
              <span className="audit__count">
                {section.cases.length} 门 · {CONFIDENCE_LABEL[section.confidence]}
              </span>
            </h3>
            <p className="audit__action">该做什么：{section.action}</p>
            {section.cases.length > 0 && (
              <table className="audit__table">
                <thead>
                  <tr>
                    <th>课程号</th>
                    <th>课程名称</th>
                    <th>学分</th>
                    <th>成绩</th>
                  </tr>
                </thead>
                <tbody>
                  {section.cases.map((item) => (
                    <tr key={`${section.key}-${item.course_code}`}>
                      <td className="audit__code">{item.course_code}</td>
                      <td>{item.name || '（原专业课程）'}</td>
                      <td className="audit__num">{item.credits}</td>
                      <td className="audit__num">{item.grade ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        ))}

        <section className="audit__section">
          <h3 className="audit__section-title">下一步</h3>
          <ol className="audit__next">
            {data.next_actions.map((action) => (
              <li key={action.step}>
                {action.text}
                <span className="audit__where">{action.where}</span>
              </li>
            ))}
          </ol>
        </section>

        <p className="audit__disclaimer">{data.disclaimer}</p>

        <div className="audit__sign">
          <div>
            本人签字：<span className="audit__line" />
          </div>
          <div>
            辅导员：<span className="audit__line" />
          </div>
          <div>
            教务处：<span className="audit__line" />
          </div>
          <div>
            日期：<span className="audit__line" />
          </div>
        </div>

        <div className="audit__actions">
          <button
            className="btn btn--primary tiny"
            onClick={() => window.print()}
            disabled={!data.printable}
            title={
              data.printable
                ? '打印或另存为 PDF'
                : '样例数据不可打印 —— 避免生成一张看起来能签字、实际却是编造数据的单子'
            }
          >
            打印 / 另存为 PDF
          </button>
          <button
            className="btn btn--quiet tiny"
            onClick={() => {
              void navigator.clipboard?.writeText(formatAuditSheet(data))
            }}
          >
            复制为文本
          </button>
        </div>
      </article>
    </div>
  )
}
