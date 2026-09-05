/* 前端鉴权状态源：可注入的认证判断。
 *
 * 骨架设计：框架不绑定具体登录业务，只定义「如何判断已登录 / 是否有权限」的接口。
 * 默认实现：存在 access_token 即视为已登录（配合 tokenStore）。
 * 业务接入真实登录后，可注入更严格的状态源（如校验过期时间、拉取用户信息）。
 */

import { getAccessToken } from '@/services/http/tokenStore'

export interface AuthStateSource {
  isAuthenticated: () => boolean
  hasPermission: (permission: string) => boolean
}

const defaultAuthState: AuthStateSource = {
  isAuthenticated: () => Boolean(getAccessToken()),
  // 骨架阶段默认放行所有权限；业务接入 RBAC 后注入真实判断
  hasPermission: () => true,
}

let authStateSource: AuthStateSource = defaultAuthState

/** 注入自定义鉴权状态源（业务在应用装配时调用，登录业务完成后替换） */
export function setAuthStateSource(source: AuthStateSource): void {
  authStateSource = source
}

export function isAuthenticated(): boolean {
  return authStateSource.isAuthenticated()
}

export function hasPermission(permission: string): boolean {
  return authStateSource.hasPermission(permission)
}
