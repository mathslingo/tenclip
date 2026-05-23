import {
  FireFilled,
  HomeOutlined,
  ReadOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { Grid, Layout, Menu, Segmented, Typography, theme } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import type { ColorScheme } from "../theme/ThemeContext";
import { useAppTheme } from "../theme/ThemeContext";

const { Sider, Content, Footer } = Layout;
const { Text } = Typography;

type MenuKey = "home" | "discovery" | "wire" | "matches";

function scrollToSection(id: string) {
  requestAnimationFrame(() => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

export function SiteLayout() {
  const { token } = theme.useToken();
  const { scheme, setScheme, isDark } = useAppTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const screens = Grid.useBreakpoint();
  const [menuKey, setMenuKey] = useState<MenuKey>("home");

  const isHome = location.pathname === "/";

  useEffect(() => {
    if (!isHome) {
      setMenuKey("home");
    }
  }, [isHome, location.pathname]);

  useEffect(() => {
    const st = location.state as { scrollTo?: string } | null | undefined;
    if (st?.scrollTo) {
      scrollToSection(st.scrollTo);
      window.history.replaceState({}, document.title);
    }
  }, [location]);

  const selectedKeys = useMemo(() => {
    if (!isHome) return [] as string[];
    return [menuKey];
  }, [isHome, menuKey]);

  const goSection = (key: MenuKey) => {
    setMenuKey(key);
    if (key === "home") {
      navigate("/");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    const map: Record<Exclude<MenuKey, "home">, string> = {
      discovery: "section-discovery",
      wire: "section-wire",
      matches: "section-matches",
    };
    const id = map[key as Exclude<MenuKey, "home">];
    if (location.pathname !== "/") {
      navigate("/", { state: { scrollTo: id } });
    } else {
      scrollToSection(id);
    }
  };

  return (
    <Layout style={{ minHeight: "100vh", background: token.colorBgLayout }}>
      <Sider
        width={236}
        breakpoint="lg"
        collapsedWidth={0}
        style={{
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          background: isDark ? "rgba(8, 12, 10, 0.98)" : "#f1f5f0",
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
        }}
        theme={isDark ? "dark" : "light"}
      >
        <div
          style={{
            padding: "20px 16px 12px",
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            flexShrink: 0,
          }}
        >
          <Link
            to="/"
            onClick={() => {
              setMenuKey("home");
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            style={{
              display: "block",
              textDecoration: "none",
            }}
          >
            <span className="sport-brand-mark">TenClip</span>
            <div>
              <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.4 }}>
                网球资讯 · 赛程 · 社区风向
              </Text>
            </div>
          </Link>
        </div>

        <Menu
          mode="inline"
          theme={isDark ? "dark" : "light"}
          selectedKeys={selectedKeys}
          style={{ border: "none", marginTop: 8, flex: 1, minHeight: 0 }}
          items={[
            {
              key: "home",
              icon: <HomeOutlined />,
              label: "首页",
              onClick: () => goSection("home"),
            },
            {
              key: "discovery",
              icon: <FireFilled style={{ color: token.colorWarning }} />,
              label: "球场热议",
              onClick: () => goSection("discovery"),
            },
            {
              key: "wire",
              icon: <ReadOutlined />,
              label: "赛事前线",
              onClick: () => goSection("wire"),
            },
            {
              key: "matches",
              icon: <TrophyOutlined style={{ color: token.colorPrimary }} />,
              label: "巡回赛程",
              onClick: () => goSection("matches"),
            },
          ]}
        />

        <div
          style={{
            padding: 12,
            borderTop: `1px solid ${token.colorBorderSecondary}`,
            background: isDark ? "rgba(0,0,0,0.25)" : "rgba(255,255,255,0.6)",
            flexShrink: 0,
          }}
        >
          <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 6 }}>
            外观（可跟随系统日出日落）
          </Text>
          <Segmented<ColorScheme>
            size="small"
            block
            value={scheme}
            onChange={(v) => setScheme(v)}
            options={[
              { label: "系统", value: "system" },
              { label: "浅色", value: "light" },
              { label: "深色", value: "dark" },
            ]}
          />
        </div>
      </Sider>

      <Layout>
        {!screens.lg ? (
          <div
            style={{
              padding: "10px 16px",
              borderBottom: `1px solid ${token.colorBorderSecondary}`,
              background: token.colorBgContainer,
              fontSize: 13,
              color: token.colorTextSecondary,
            }}
          >
            窄屏下请点击左上角菜单图标展开导航
          </div>
        ) : null}
        <Content
          style={{
            minHeight: "calc(100vh - 120px)",
            display: "flex",
            flexDirection: "column",
            background: token.colorBgLayout,
          }}
        >
          <div
            style={{
              flex: 1,
              ...(isHome
                ? {}
                : {
                    padding: screens.md ? 28 : 16,
                    maxWidth: 1080,
                    width: "100%",
                    margin: "0 auto",
                  }),
            }}
          >
            <Outlet />
          </div>
        </Content>
        <Footer
          style={{
            textAlign: "center",
            background: isDark ? "#0f1411" : "#e3e8df",
            borderTop: `1px solid ${token.colorBorderSecondary}`,
            padding: "14px 16px",
            color: token.colorTextSecondary,
            fontSize: 12,
          }}
        >
          TenClip · 聚合网球社区热点与职业赛讯（数据来自 Core API）
        </Footer>
      </Layout>
    </Layout>
  );
}
