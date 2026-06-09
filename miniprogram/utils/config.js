/**
 * API 地址配置
 *
 * 【本地调试】
 * 1. LOCAL_DEV = true
 * 2. LOCAL_API_HOST 填 WSL IP（WSL 里执行 hostname -I）
 * 3. 后端：GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh
 * 4. 微信开发者工具 → 详情 → 本地设置 → 勾选「不校验合法域名、web-view、TLS…」
 *
 * 【上线】LOCAL_DEV = false，填已在公众平台配置的 HTTPS 域名
 */

const LOCAL_DEV = true;

/** 改成你的 WSL/服务器地址，例如 http://172.22.123.45:7861 */
const LOCAL_API_HOST = "http://127.0.0.1:7861";

/** 上线时填写（须与微信公众平台 uploadFile/request 合法域名一致） */
const PROD_API_BASE_URL = "https://你的域名";

const API_BASE_URL = LOCAL_DEV ? LOCAL_API_HOST : PROD_API_BASE_URL;

/** wx.uploadFile / wx.downloadFile 超时（毫秒） */
const UPLOAD_TIMEOUT_MS = 600000;

/** wx.request 轮询超时（毫秒） */
const REQUEST_TIMEOUT_MS = 30000;

/** 下载集锦 MP4 超时（毫秒） */
const DOWNLOAD_TIMEOUT_MS = 600000;

const PLACEHOLDER_PATTERNS = [
  "your-domain",
  "example.com",
  "你的域名",
  "请改成",
  "x.x.x",
];

function isApiConfigValid() {
  const url = String(API_BASE_URL || "").trim();
  if (!url.startsWith("http://") && !url.startsWith("https://")) return false;
  const lower = url.toLowerCase();
  return !PLACEHOLDER_PATTERNS.some((p) => lower.includes(p));
}

function apiConfigHint() {
  if (isApiConfigValid()) return "";
  return (
    "请编辑 miniprogram/utils/config.js：\n" +
    "• LOCAL_DEV=true 时设置 LOCAL_API_HOST 为 WSL IP（hostname -I）\n" +
    "• 开发者工具勾选「不校验合法域名」\n" +
    "• 后端用 GRADIO_SERVER_NAME=0.0.0.0 启动"
  );
}

module.exports = {
  API_BASE_URL,
  LOCAL_DEV,
  UPLOAD_TIMEOUT_MS,
  REQUEST_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  isApiConfigValid,
  apiConfigHint,
};
