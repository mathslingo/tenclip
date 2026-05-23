import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ThemeProvider, useAppTheme } from "./theme/ThemeContext";
import { sportAntdTheme } from "./theme/sportAntdTheme";
import "./index.css";

function ThemedApp() {
  const { isDark } = useAppTheme();
  return (
    <ConfigProvider locale={zhCN} theme={sportAntdTheme(isDark)}>
      <AntApp>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  </StrictMode>,
);
