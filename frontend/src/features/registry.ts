/* Feature 自动发现与注册。
 *
 * 约定：每个 feature 包内存在 manifest.tsx 并默认导出 FeatureManifest。
 * 框架通过 Vite 的 import.meta.glob 自动收集，无需修改 app 装配层。
 */

import type { AppRouteObject, FeatureManifest } from './types'

// Vite 自动发现所有 feature 的 manifest.tsx（eager: true 用于同步获取配置）
const manifestModules = import.meta.glob<{
  default: FeatureManifest
}>('/src/features/*/manifest.tsx', { eager: true })

function collectManifests(): FeatureManifest[] {
  return Object.values(manifestModules).map((mod) => mod.default)
}

export function getFeatureRoutes(): AppRouteObject[] {
  const manifests = collectManifests()
  return manifests.flatMap((manifest) => manifest.routes ?? [])
}

export function getFeatureMenus(): FeatureManifest['menu'] {
  const manifests = collectManifests()
  return manifests.flatMap((manifest) => manifest.menu ?? [])
}
