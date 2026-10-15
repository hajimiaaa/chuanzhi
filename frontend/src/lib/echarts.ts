/**
 * ECharts 按需引入。
 *
 * 全量 `echarts` 约 1MB（min），对只画一个堆叠柱的页面不值。
 * 只注册用到的模块，`npm run build` 时核实实际体积。
 * 不引 `echarts-for-react` —— 组件里自己写 useEffect + ResizeObserver 就够，少一个依赖。
 */

import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  CanvasRenderer,
])

export { echarts }
