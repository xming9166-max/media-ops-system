import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'node_modules']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
  },
  {
    // feature manifest 是「注册文件」（导出配置对象而非组件），react-refresh 规则不适用
    files: ['src/features/*/manifest.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // 框架依赖方向约束：仅对基础设施/共享层生效，禁止反向依赖业务 feature 内部实现
    files: ['src/{services,stores,components,hooks,utils,types}/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['*/features/**'],
              message: '基础设施/共享层禁止依赖业务 feature 内部实现',
            },
          ],
        },
      ],
    },
  },
])
