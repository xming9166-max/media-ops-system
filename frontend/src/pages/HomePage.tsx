import { Typography } from 'antd'
import HealthCheckButton from '@/components/common/HealthCheckButton'

const { Title, Paragraph } = Typography

export default function HomePage() {
  return (
    <div>
      <Title>前后端分离基础开发框架</Title>
      <Paragraph>前端工程骨架已就绪，可点击按钮测试后端接口连接。</Paragraph>
      <HealthCheckButton />
    </div>
  )
}
