import {
  FileTextOutlined,
  TeamOutlined,
  TrophyOutlined,
  VideoCameraOutlined,
} from "@ant-design/icons";
import { Layout, Menu, theme } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/news", icon: <FileTextOutlined />, label: "新闻" },
  { key: "/players", icon: <TeamOutlined />, label: "球员" },
  { key: "/matches", icon: <TrophyOutlined />, label: "比赛" },
  { key: "/videos", icon: <VideoCameraOutlined />, label: "视频" },
];

export function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();

  const selected = menuItems.find((m) => location.pathname.startsWith(m.key))?.key ?? "/news";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth={64} theme="dark" width={220}>
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: token.colorWhite,
            fontWeight: 600,
            fontSize: 16,
          }}
        >
          TenClip 后台
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: "0 24px",
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            lineHeight: "64px",
            fontSize: 16,
            fontWeight: 500,
          }}
        >
          Core API 管理
        </Header>
        <Content style={{ margin: 24, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
