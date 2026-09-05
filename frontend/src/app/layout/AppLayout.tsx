/* 通用后台布局骨架。
 *
 * 使用 Ant Design Layout：侧边菜单 + 顶栏 + 内容区。
 * 菜单数据来自 feature registry（getFeatureMenus），新增 feature 自动出现。
 * 本组件属于装配层（app），因此允许依赖 feature registry。
 * 后续可扩展：折叠、面包屑、用户信息区、主题切换。
 */

import { Layout, Menu, Spin } from 'antd'
import type { MenuProps } from 'antd'
import { Outlet, useNavigate } from 'react-router-dom'
import { Suspense, useState } from 'react'

import { getFeatureMenus } from '@/features/registry'
import type { MenuItem } from '@/features/types'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

const { Header, Sider, Content } = Layout

/** 将 feature 菜单递归转换为 antd Menu items */
function toAntdItems(menus: MenuItem[]): NonNullable<MenuProps['items']> {
  return (menus ?? []).map((item) => ({
    key: item.key,
    icon: item.icon,
    label: item.label,
    children: item.children ? toAntdItems(item.children) : undefined,
  }))
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const menus = getFeatureMenus() ?? []
  useDocumentTitle()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div
          style={{
            height: 32,
            margin: 16,
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: collapsed ? 14 : 16,
            fontWeight: 600,
          }}
        >
          {collapsed ? '框架' : '基础框架'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          items={toAntdItems(menus)}
          onClick={({ key }) => {
            const target = menus.find((m) => m.key === key)?.path
            if (target) navigate(target)
          }}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px' }}>{/* 顶栏扩展位 */}</Header>
        <Content style={{ margin: 16 }}>
          {/* Suspense：支撑 React.lazy 懒加载页面，加载期显示居中 Spin */}
          <Suspense
            fallback={
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  minHeight: 240,
                }}
              >
                <Spin size="large" description="加载中…" />
              </div>
            }
          >
            <Outlet />
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  )
}
