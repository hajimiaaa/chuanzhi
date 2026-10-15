import { createRoot } from 'react-dom/client'

import App from './App'
import './index.css'
import './components.css'

/*
 * 刻意不套 <StrictMode>。
 *
 * StrictMode 在开发模式下会挂载→卸载→再挂载，副作用跑两遍：
 *   - SSE 流会被开一次、中断、再开一次（页面上看到"生成"闪两下）
 *   - 校验请求会多发一轮
 * 对一个要用来录演示视频的页面，这点噪声不值得 —— 而且它掩盖不了任何真实问题，
 * 因为后端的所有接口都是幂等的只读计算。
 */
const host = document.getElementById('root')
if (!host) {
  throw new Error('找不到 #root 挂载点')
}

createRoot(host).render(<App />)
