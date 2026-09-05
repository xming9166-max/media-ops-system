/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_API_TIMEOUT_MS?: string
  readonly VITE_LOG_LEVEL?: 'debug' | 'info' | 'warn' | 'error' | 'off'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
