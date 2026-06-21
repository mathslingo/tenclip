/**
 * API 地址配置
 *
 * 【备案完成前】保持 LOCAL_DEV = true，勿请求 api.uchance.tech（会 ERR_CONNECTION_RESET）
 *
 * 【本地调试】
 * 1. LOCAL_DEV = true
 * 2. LOCAL_API_HOST 填 WSL IP（WSL 里执行 hostname -I）
 *    Windows 开发者工具模拟器可先试 http://127.0.0.1:7861，不通再改 WSL IP
 * 3. 后端：GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh
 * 4. 微信开发者工具 → 详情 → 本地设置 → 勾选「不校验合法域名、web-view、TLS…」
 *
 * 【上线】LOCAL_DEV = false，填已在公众平台配置的 HTTPS 域名（须 ICP 备案）
 */

const LOCAL_DEV = true;

/** 本地后端；WSL 里 hostname -I 取 IP，例如 http://172.22.123.45:7861 */
const LOCAL_API_HOST = "http://127.0.0.1:7861";

/** 上线时填写（须与微信公众平台 uploadFile/request 合法域名一致） */
const PROD_API_BASE_URL = "https://api.uchance.tech";

/** 每次上传体验版前改一下，用于确认手机跑的是新包 */
const APP_BUILD_TAG = "2026-06-14-local";

const API_BASE_URL = LOCAL_DEV ? LOCAL_API_HOST : PROD_API_BASE_URL;

/** web-view / 复制链接（本地调试时同样走 LOCAL_API_HOST） */
const WEB_STROKE_URL = API_BASE_URL + "/web/stroke";
const WEB_ANALYZE_URL = API_BASE_URL + "/web";

/** wx.uploadFile / wx.downloadFile 超时（毫秒，约 10 分钟；大视频 + 3Mbps 带宽可能仍较慢） */
const UPLOAD_TIMEOUT_MS = 600000;

/** 超过此大小（MB）提示用户压缩或换 WiFi */
const UPLOAD_WARN_SIZE_MB = 80;

/** 上传前用 wx.compressVideo 压缩的阈值（MB）；击球检测不需原画质 */
const UPLOAD_COMPRESS_ABOVE_MB = 1;

/** compressVideo 档位：low | medium | high（上传优先用 low 减小体积） */
const UPLOAD_COMPRESS_QUALITY = "low";

/** wx.request 轮询超时（毫秒） */
const REQUEST_TIMEOUT_MS = 30000;

/** 启动探活超时（毫秒）；本机无后端时会较快失败 */
/** 启动探活单次超时（毫秒）；弱网适当加长 */
const HEALTH_TIMEOUT_MS = 12000;

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

/** 公众平台「服务器域名」里应填的 host（不含 https:// 与路径） */
function apiHostForWhitelist() {
  var raw = LOCAL_DEV ? LOCAL_API_HOST : PROD_API_BASE_URL;
  return String(raw || "")
    .replace(/^https?:\/\//i, "")
    .split("/")[0]
    .split(":")[0];
}

function domainWhitelistHint() {
  var host = apiHostForWhitelist();
  if (LOCAL_DEV) {
    return (
      "本地调试：config.js 设置 LOCAL_API_HOST，开发者工具勾选「不校验合法域名」。"
    );
  }
  var url = "https://" + host;
  return (
    "真机/体验版须在微信公众平台配置合法域名：\n" +
    "开发管理 → 开发设置 → 服务器域名\n" +
    "• request / uploadFile / downloadFile 均填： " +
    url +
    "\n（单个域名末尾不要分号）\n保存后关掉小程序再重新打开。"
  );
}

function isDomainListError(err) {
  var msg = String((err && err.errMsg) || (err && err.message) || err || "");
  return msg.indexOf("url not in domain list") !== -1;
}

module.exports = {
  API_BASE_URL,
  LOCAL_DEV,
  UPLOAD_TIMEOUT_MS,
  REQUEST_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  HEALTH_TIMEOUT_MS,
  UPLOAD_WARN_SIZE_MB,
  UPLOAD_COMPRESS_ABOVE_MB,
  UPLOAD_COMPRESS_QUALITY,
  APP_BUILD_TAG,
  WEB_STROKE_URL,
  WEB_ANALYZE_URL,
  isApiConfigValid,
  apiConfigHint,
  apiHostForWhitelist,
  domainWhitelistHint,
  isDomainListError,
};
