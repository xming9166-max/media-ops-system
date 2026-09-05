/* 统一常量出口。
 *
 * 约定：跨模块共享的业务常量统一在此管理；feature 私有常量留在 feature 内。
 */

/** 应用级常量 */
export const APP = {
  NAME: '基础框架',
  /** localStorage 键统一前缀，避免与其他应用冲突 */
  STORAGE_PREFIX: 'app',
} as const

/** 分页默认值 */
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100],
} as const

/** 业务错误码（对齐后端 app/core/errors.py 的 ApiCode） */
export const BUSINESS_CODE = {
  SUCCESS: 0,
  PARAM_ERROR: 40000,
  UNAUTHORIZED: 40100,
  FORBIDDEN: 40300,
  NOT_FOUND: 40400,
  CONFLICT: 40900,
  INTERNAL_ERROR: 50000,
} as const

/** HTTP 状态码（对齐后端 docs/http/api-contract.md 状态码表） */
export const HTTP_STATUS = {
  OK: 200,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  INTERNAL_ERROR: 500,
} as const
