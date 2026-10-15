/**
 * 设计令牌：颜色。
 *
 * ⚠️ 这些十六进制值是**用 dataviz 的验证脚本实测过的，不是眼估**：
 *
 *   浅色（表面 #fcfcfb）  全部 PASS —— worst adjacent CVD ΔE 9.1、正常视觉 ΔE 22.9、亮度带与彩度带均 PASS
 *                         唯一 WARN：aqua 2.74 / yellow 2.11 的对比度低于 3:1
 *                         → 触发「relief 规则」：必须配**可见标签或表格视图**（两者都不可省）
 *   深色（表面 #1a1a19）  全部 PASS，含对比度
 *
 * 两条不变的纪律：
 *   1. **分类色按固定槽位分配，永不循环、永不按排名重排** —— 颜色跟随实体（课程类别），
 *      不跟随数量或名次。筛选导致序列数变化时，幸存者不得改色。
 *   2. **状态色是保留色**，绝不复用为第 5 个类别；且永远 **icon + 文字 + 颜色三者并存**，
 *      不让颜色单独承载语义（light 面上 warning 的对比度本来就只有 1.79）。
 *
 * 与 index.css 的 CSS 变量保持同步 —— 那边供 DOM 用，这边供 ECharts 用
 * （ECharts 需要具体色值，读不了 CSS 变量）。
 */

import { CATEGORIES, type Category } from '@/api/types'

// ---------- 分类色（固定槽位，顺序即语义）----------

export const CATEGORY_LIGHT: Record<Category, string> = {
  必修: '#2a78d6', // 槽 1 blue
  专业选修: '#eb6834', // 槽 2 orange
  通识: '#1baf7a', // 槽 3 aqua
  实践: '#eda100', // 槽 4 yellow
}

export const CATEGORY_DARK: Record<Category, string> = {
  必修: '#3987e5',
  专业选修: '#d95926',
  通识: '#199e70',
  实践: '#c98500',
}

/** 未在既定类别内的课程（后端 unknown_category 会报出来）走中性灰，不占用分类槽位 */
export const CATEGORY_FALLBACK = '#898781'

export function isCategory(value: string): value is Category {
  return (CATEGORIES as readonly string[]).includes(value)
}

export function categoryColor(category: string, mode: 'light' | 'dark' = 'light'): string {
  if (!isCategory(category)) return CATEGORY_FALLBACK
  return mode === 'dark' ? CATEGORY_DARK[category] : CATEGORY_LIGHT[category]
}

/** 固定顺序取色 —— 唯一的分配入口，杜绝"按数量取前 N 个"这种会改色的写法 */
export const CATEGORY_ORDER: readonly Category[] = CATEGORIES

export function categoryPalette(mode: 'light' | 'dark' = 'light'): string[] {
  return CATEGORY_ORDER.map((c) => categoryColor(c, mode))
}

/** 分类色配套的浅步，用作 meter 的轨道底色（同色浅步，让"状态"在整条上都读得出来）*/
export const CATEGORY_TRACK_LIGHT: Record<Category, string> = {
  必修: '#cde2fb',
  专业选修: '#fbdccf',
  通识: '#cdeee1',
  实践: '#fbe8c6',
}

// ---------- 状态色（保留，绝不复用为分类色）----------

export const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
} as const

export const SEVERITY_COLOR: Record<string, string> = {
  error: STATUS.critical,
  warning: STATUS.warning,
  info: '#898781', // info 走中性灰，视觉上明确降级
}

export const SEVERITY_ICON: Record<string, string> = {
  error: '✕',
  warning: '!',
  info: 'i',
}

export const SEVERITY_LABEL: Record<string, string> = {
  error: '错误',
  warning: '警告',
  info: '提示',
}

// ---------- 图表框架与文字 ----------

export const CHROME = {
  surface: '#fcfcfb',
  pagePlane: '#f9f9f7',
  inkPrimary: '#0b0b0b',
  inkSecondary: '#52514e',
  inkMuted: '#898781',
  gridline: '#e1e0d9',
  axis: '#c3c2b7',
  border: 'rgba(11,11,11,0.10)',
  /** 堆叠段之间留 2px 表面色缝隙 —— 这是"看不见但很重要"的细节 */
  surfaceGap: '#fcfcfb',
} as const
