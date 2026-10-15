import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  resolve: {
    // ⚠️ 这个别名必须与 tsconfig.app.json 的 paths 两处一致。
    // 不一致的表现是"编辑器不报错、npm run dev 报模块找不到"。
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },

  server: {
    port: 5173,
    // 后端 CORS 白名单只放行 localhost:5173 与 127.0.0.1:5173。
    // Vite 默认在端口被占时静默 +1，结果是页面能打开、每个请求都跨域失败 —— 最难查的一种坏法。
    // 宁可让 npm run dev 直接报错退出。
    strictPort: true,
    host: 'localhost',
    open: true,
  },

  // 让 npm run preview 也落在白名单端口上
  preview: { port: 5173, strictPort: true },

  build: {
    target: 'es2022',
    rollupOptions: {
      output: {
        // ECharts 单独切块，不阻塞首屏
        manualChunks(id) {
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) {
            return 'echarts'
          }
        },
      },
    },
  },
})
