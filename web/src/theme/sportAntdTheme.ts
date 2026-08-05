import type { ThemeConfig } from "antd";
import { theme } from "antd";

const { darkAlgorithm, defaultAlgorithm } = theme;

/** 运动风：草地绿主色 + 高对比易读；深色模式略提亮主色 */
export function sportAntdTheme(isDark: boolean): ThemeConfig {
  return {
    cssVar: { prefix: "ant" },
    algorithm: isDark ? darkAlgorithm : defaultAlgorithm,
    token: {
      colorPrimary: isDark ? "#4ade80" : "#047857",
      colorInfo: "#0284c7",
      colorSuccess: "#16a34a",
      colorWarning: "#ea580c",
      colorError: "#dc2626",
      borderRadius: 12,
      fontFamily:
        '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif',
      fontSizeHeading1: 34,
      fontSizeHeading2: 26,
    },
    components: {
      Layout: {
        bodyBg: isDark ? "#0b0f0d" : "#eef1ec",
        headerBg: "transparent",
        footerBg: isDark ? "#0f1411" : "#e3e8df",
        siderBg: isDark ? "#0a100d" : "#f6f8f4",
      },
      Menu: {
        itemBg: "transparent",
        darkItemBg: "transparent",
        itemSelectedBg: isDark ? "rgba(74, 222, 128, 0.12)" : "rgba(4, 120, 87, 0.1)",
        itemHoverBg: isDark ? "rgba(255,255,255,0.06)" : "rgba(4, 120, 87, 0.06)",
      },
      Card: {
        headerBg: "transparent",
      },
    },
  };
}
