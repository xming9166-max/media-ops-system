/* Token 存取：可注入的存储抽象。
 *
 * 框架默认使用 localStorage，业务可按需替换（如 cookie、内存、SSR 环境）。
 * 通过 setTokenStorage 注入自定义读写实现，保持低耦合。
 */

type TokenGetter = () => string | null
type TokenSetter = (token: string | null) => void

const STORAGE_KEY = 'access_token'

let tokenGetter: TokenGetter = () => localStorage.getItem(STORAGE_KEY)
let tokenSetter: TokenSetter = (token) => {
  if (token) {
    localStorage.setItem(STORAGE_KEY, token)
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export function setTokenStorage(getter: TokenGetter, setter: TokenSetter): void {
  tokenGetter = getter
  tokenSetter = setter
}

export function getAccessToken(): string | null {
  return tokenGetter()
}

export function setAccessToken(token: string | null): void {
  tokenSetter(token)
}

export function clearAccessToken(): void {
  tokenSetter(null)
}
