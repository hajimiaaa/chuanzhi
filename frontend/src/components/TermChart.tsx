/**
 * 每学期学分分布（堆叠柱）。
 *
 * 选堆叠柱而不是简单柱，是因为它能**一次回答两个问题**：每学期负荷多少、构成如何。
 * 而且与上方的类别 meter **共用同一套颜色** —— 全站"颜色跟随实体"，
 * 筛选或数值变化绝不重排颜色。
 *
 * 纪律（来自 dataviz 规范）：
 *  - 单一坐标轴，绝不做双轴
 *  - 超上限的柱子加标记，**不换整柱颜色**（颜色跟实体，不跟排名）
 *  - 上限线用实线 hairline，不用虚线（虚线读起来像"预测"）
 *  - 堆叠段之间留表面色缝隙
 *  - 网格线与坐标轴文字保持克制
 */

import { useEffect, useMemo, useRef } from 'react'

import type { CreditRule, Program } from '@/api/types'
import { categoryColor, CHROME } from '@/lib/colors'
import { round1 } from '@/lib/format'
import { echarts } from '@/lib/echarts'

interface Props {
  program: Program
  byTermCategory: Record<number, Record<string, number>>
  byTerm: Record<number, number>
  rules: CreditRule[]
  onSelectTerm: (term: number) => void
}

const OVER_COLOR = '#d03b3b'

export function TermChart({ program, byTermCategory, byTerm, rules, onSelectTerm }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  const terms = useMemo(
    () => Array.from({ length: program.total_terms }, (_, i) => i + 1),
    [program.total_terms],
  )

  // 只画培养方案里真的出现过的类别，但**顺序固定**（按 credit_rules 的声明顺序）
  const categories = useMemo(() => {
    const declared = rules.map((r) => r.category)
    const extra = new Set<string>()
    for (const perTerm of Object.values(byTermCategory)) {
      for (const cat of Object.keys(perTerm)) {
        if (!declared.includes(cat)) extra.add(cat)
      }
    }
    return [...declared, ...extra]
  }, [rules, byTermCategory])

  /**
   * y 轴上限要**主动抬到上限线之上**。
   * 否则：上限 26、各学期最高 21 时，ECharts 会把 y 轴收到 25，
   * 那条 markLine 落在坐标系外被静默裁掉 —— 页面看着一切正常，线就是不见了。
   */
  const yMax = useMemo(() => {
    const cap = round1(program.max_credits_per_term ?? 0)
    const dataMax = Math.max(cap, ...terms.map((t) => round1(byTerm[t] ?? 0)), 0)
    return dataMax > 0 ? Math.ceil(dataMax * 1.08) : undefined
  }, [terms, byTerm, program.max_credits_per_term])

  const option = useMemo(() => {
    const cap = round1(program.max_credits_per_term ?? 0)
    const overTerms = cap > 0 ? terms.filter((t) => round1(byTerm[t] ?? 0) > cap) : []

    const series = categories.map((category, index) => {
      const isTop = index === categories.length - 1
      const isFirst = index === 0
      return {
        name: category,
        type: 'bar' as const,
        stack: 'term',
        barMaxWidth: 22,
        itemStyle: {
          color: categoryColor(category),
          // 1px 表面色描边 —— 相邻两段之间就有了 2px 的缝
          borderColor: CHROME.surface,
          borderWidth: 1,
          // 只在最上面一段做圆角，形成"数据端 4px 圆角"的观感
          borderRadius: isTop ? ([4, 4, 0, 0] as [number, number, number, number]) : 0,
        },
        emphasis: { focus: 'series' as const },
        data: terms.map((t) => round1(byTermCategory[t]?.[category] ?? 0)),
        // 上限线与超载标记挂在**第一个类别系列**上。
        // 之前是用一个 type:'line' 的占位系列来挂 markLine，但只注册了 BarChart，
        // 于是 ECharts 静默丢弃该系列 —— 线根本没画出来，页面却看不出异常。
        ...(isFirst
          ? {
              markLine:
                cap > 0
                  ? {
                      silent: true,
                      symbol: 'none',
                      lineStyle: { color: CHROME.inkMuted, width: 1, type: 'solid' as const },
                      label: {
                        formatter: `上限 ${cap}`,
                        color: CHROME.inkMuted,
                        fontSize: 10,
                        position: 'insideEndTop' as const,
                      },
                      data: [{ yAxis: cap }],
                    }
                  : undefined,
              markPoint: overTerms.length
                ? {
                    symbol: 'triangle',
                    symbolSize: 9,
                    symbolOffset: [0, -2],
                    itemStyle: { color: OVER_COLOR },
                    label: { show: false },
                    // 超上限的学期只加一枚标记，不给整柱换色 —— 颜色跟着实体走
                    data: overTerms.map((t) => ({ coord: [String(t), round1(byTerm[t] ?? 0)] })),
                    tooltip: { show: false },
                  }
                : undefined,
            }
          : {}),
      }
    })

    return {
      animationDuration: 220,
      animationDurationUpdate: 220,
      grid: { left: 34, right: 12, top: 28, bottom: 24, containLabel: false },
      tooltip: {
        trigger: 'axis' as const,
        axisPointer: { type: 'shadow' as const },
        backgroundColor: CHROME.surface,
        borderColor: CHROME.gridline,
        textStyle: { color: CHROME.inkPrimary, fontSize: 12 },
        formatter: (params: unknown) => {
          const list = Array.isArray(params) ? params : [params]
          const term = terms[(list[0] as { dataIndex: number })?.dataIndex ?? 0]
          const total = round1(byTerm[term] ?? 0)
          const head = cap > 0 ? `第 ${term} 学期 · ${total} / ${cap} 学分` : `第 ${term} 学期 · ${total} 学分`
          const rows = list
            .filter((p) => Number((p as { value: number }).value) > 0)
            .map((p) => {
              const item = p as { marker: string; seriesName: string; value: number }
              return `${item.marker}${item.seriesName} ${item.value}`
            })
            .join('<br/>')
          return `<b>${head}</b><br/>${rows || '<span style="color:#898781">本学期未排课</span>'}`
        },
      },
      legend: {
        show: categories.length >= 2,
        // 显式限定图例条目：后面还有一个全透明的占位系列（只为挂 markPoint），
        // 不加这一行它的名字「超出上限」会混进图例里变成噪声
        data: categories,
        bottom: 0,
        itemWidth: 10,
        itemHeight: 10,
        icon: 'roundRect',
        textStyle: { color: CHROME.inkSecondary, fontSize: 11 },
      },
      xAxis: {
        type: 'category' as const,
        data: terms.map((t) => `${t}`),
        axisLine: { lineStyle: { color: CHROME.axis } },
        axisTick: { show: false },
        axisLabel: { color: CHROME.inkMuted, fontSize: 11, formatter: '{value}' },
      },
      yAxis: {
        type: 'value' as const,
        max: yMax,
        splitLine: { lineStyle: { color: CHROME.gridline, width: 1, type: 'solid' as const } },
        axisLabel: { color: CHROME.inkMuted, fontSize: 11 },
      },
      series,
    }
  }, [categories, terms, byTermCategory, byTerm, program.max_credits_per_term, yMax])

  useEffect(() => {
    if (!hostRef.current) return
    const chart = echarts.init(hostRef.current, undefined, { renderer: 'canvas' })
    chartRef.current = chart
    chart.on('click', (params: { dataIndex?: number }) => {
      if (typeof params?.dataIndex === 'number') onSelectTerm(terms[params.dataIndex] ?? 1)
    })

    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(hostRef.current)

    return () => {
      observer.disconnect()
      chart.dispose()
      chartRef.current = null
    }
    // terms / onSelectTerm 在组件生命周期内稳定
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true })
  }, [option])

  return (
    <div className="chart">
      <div ref={hostRef} className="chart__canvas" />
      {rules.length === 0 && <p className="muted small">本培养方案未设分类学分要求。</p>}
    </div>
  )
}
