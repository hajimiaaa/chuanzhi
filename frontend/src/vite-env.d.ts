/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端地址。默认 http://127.0.0.1:8000（不用 localhost，避开 Windows 的 ::1 解析） */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
