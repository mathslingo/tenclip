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
 *
 * 【上线 阿里云 / uchance.tech 已备案】见 scripts/deploy/DEPLOY_UCHANCE_TECH.md
 *   PROD_API_BASE_URL = "https://api.uchance.tech"
 *   公众平台 request/uploadFile 合法域名填 api.uchance.tech
 *
 * 【旧】clip.uchanceai.com — 见 DEPLOY_UCHANCEAI.md
 * 【备选】tenclip.qiongjingtiyu.com — 见 DEPLOY_QIONGJING.md
 */

/** true=读本机 news_feed.db（经 /api/news/feed）；false=读线上 api.uchance.tech */
const LOCAL_DEV = false;

/** 本地后端；WSL 里 hostname -I 取 IP，例如 http://172.22.123.45:7861
 *  Win11 镜像网络可用 127.0.0.1；模拟器不通时改成 WSL eth0 IP */
const LOCAL_API_HOST = "http://127.0.0.1:7861";

/** 上线时填写（须与微信公众平台 uploadFile/request 合法域名一致） */
const PROD_API_BASE_URL = "https://api.uchance.tech";

/** 每次上传体验版前改一下，用于确认手机跑的是新包 */
const APP_BUILD_TAG = "2026-09-30-mix-badge";

/** 发现页：true=本地 Mock；false=请求 /api/news/feed（失败回退 Mock；空库显示空态） */
const FEED_USE_MOCK = false;

/** 超过此大小（MB）自动走分片上传（10 分钟视频压缩后常 30～80MB，原 50MB 阈值过高） */
const UPLOAD_LARGE_ROUTE_MB = 15;

/** 超过此时长（秒）也走分片上传 */
const UPLOAD_CHUNK_DURATION_SEC = 300;

const API_BASE_URL = LOCAL_DEV ? LOCAL_API_HOST : PROD_API_BASE_URL;

/** web-view / 复制链接（本地调试时同样走 LOCAL_API_HOST） */
const WEB_STROKE_URL = API_BASE_URL + "/web/stroke";
const WEB_ANALYZE_URL = API_BASE_URL + "/web";
/** 实时关键点检测 H5（YOLO Pose ONNX Web）；微信内 web-view 常无法开摄像头，优先「复制链接」用系统浏览器/Safari */
const WEB_POSE_URL = API_BASE_URL + "/yolo-pose/";
/** 小程序原生 YOLO Pose：同源下载 ONNX 到本地再 InferenceSession */
const YOLO_POSE_MODEL_URL = WEB_POSE_URL + "models/yolo11n-pose.onnx";
const YOLO_POSE_IMGSZ = 640;

/**
 * 姿态检测后端（pose_server.py，默认 5000）
 * 本地：与 LOCAL_API_HOST 同主机、端口 5000
 * 上线：填公网 HTTPS 或与主 API 同域反代
 */
function poseApiBaseFromHost(apiBase) {
  try {
    var m = String(apiBase || "").match(/^(https?:\/\/[^/:]+)(?::(\d+))?/i);
    if (!m) return "http://127.0.0.1:5000";
    return m[1] + ":5000";
  } catch (e) {
    return "http://127.0.0.1:5000";
  }
}

const POSE_API_BASE = LOCAL_DEV
  ? poseApiBaseFromHost(LOCAL_API_HOST)
  : PROD_API_BASE_URL;
// 生产：/detect、/health 由 Nginx 转到 5000；/analyze-video 若 Nginx 未配，由主 API 转发
const POSE_DETECT_URL = POSE_API_BASE + "/detect";
const POSE_HEALTH_URL = POSE_API_BASE + "/health";

const RTMPOSE_V2_API_BASE = POSE_API_BASE;
const RTMPOSE_V2_DETECT_URL = POSE_DETECT_URL;
const RTMPOSE_V2_HEALTH_URL = POSE_HEALTH_URL;

const POSE_ANALYZE_VIDEO_URL = POSE_API_BASE + "/analyze-video";
const POSE_ANALYZE_STATUS_URL = POSE_API_BASE + "/analyze-video/status";
const POSE_ANALYZE_FILE_URL = POSE_API_BASE + "/analyze-video/file";

/** wx.uploadFile / 分片上传 / wx.downloadFile 超时（毫秒，约 30 分钟） */
const UPLOAD_TIMEOUT_MS = 1800000;

/** 超过此大小（MB）选视频时提示用户 */
const UPLOAD_WARN_SIZE_MB = 30;

/** 超过此时长（秒）选视频时提示用户（10 分钟） */
const UPLOAD_WARN_DURATION_SEC = 600;

/** 超过此大小（MB）才走 wx.compressVideo（过小文件压缩收益低） */
const UPLOAD_COMPRESS_ABOVE_MB = 0.5;

/** 超过此大小或时长时，压缩档位更激进 */
const UPLOAD_COMPRESS_AGGRESSIVE_MB = 60;
const UPLOAD_COMPRESS_AGGRESSIVE_SEC = 600;

/** compressVideo 默认档位 */
const UPLOAD_COMPRESS_QUALITY = "low";

/** wx.request 轮询超时（毫秒） */
const REQUEST_TIMEOUT_MS = 30000;

/** 启动探活超时（毫秒）；本机无后端时会较快失败 */
/** 启动探活单次超时（毫秒）；弱网适当加长 */
const HEALTH_TIMEOUT_MS = 12000;

/** 下载集锦 MP4 超时（毫秒） */
const DOWNLOAD_TIMEOUT_MS = 1800000;

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

var SLAM_STORAGE_KEY = "tenclip_slam_theme";

var SLAM_THEMES = [
  {
    id: "wimbledon",
    name: "温网草地",
    hint: "绿草条纹",
    nav: "#0c3b2e",
    front: "#ffffff",
    accent: "#3dffb0",
    accentInk: "#042018",
    swatch: "linear-gradient(90deg,#0c3b2e 0%,#0c3b2e 42%,#145c40 42%,#145c40 58%,#0c3b2e 58%,#0c3b2e 100%)",
    vars: "--court-a:#0c3b2e;--court-b:#145c40;--line:#9dffe0;--accent:#3dffb0;--accent-ink:#042018;--ink:#e8fff4;--muted:#9dffe0;",
  },
  {
    id: "roland",
    name: "法网红土",
    hint: "陶土球场",
    nav: "#7a341f",
    front: "#ffffff",
    accent: "#ffe14a",
    accentInk: "#3a140c",
    swatch: "linear-gradient(90deg,#8d4030 0%,#8d4030 42%,#c4623e 42%,#c4623e 58%,#8d4030 58%,#8d4030 100%)",
    vars: "--court-a:#8d4030;--court-b:#c4623e;--line:#ffe7c2;--accent:#ffe14a;--accent-ink:#3a140c;--ink:#fff6ec;--muted:#ffe7c2;",
  },
  {
    id: "australian",
    name: "澳网硬地",
    hint: "蓝色硬地",
    nav: "#0a3d86",
    front: "#ffffff",
    accent: "#7ee0ff",
    accentInk: "#042033",
    swatch: "linear-gradient(90deg,#0d4ea3 0%,#0d4ea3 42%,#1a6fd4 42%,#1a6fd4 58%,#0d4ea3 58%,#0d4ea3 100%)",
    vars: "--court-a:#0d4ea3;--court-b:#1a6fd4;--line:#c9f4ff;--accent:#7ee0ff;--accent-ink:#042033;--ink:#eef9ff;--muted:#c9f4ff;",
  },
  {
    id: "usopen",
    name: "美网夜场",
    hint: "深蓝夜场",
    nav: "#071428",
    front: "#ffffff",
    accent: "#f5c16c",
    accentInk: "#1a1206",
    swatch: "linear-gradient(90deg,#071833 0%,#071833 42%,#12305f 42%,#12305f 58%,#071833 58%,#071833 100%)",
    vars: "--court-a:#071833;--court-b:#12305f;--line:#d7e4ff;--accent:#f5c16c;--accent-ink:#1a1206;--ink:#f4f7ff;--muted:#d7e4ff;",
  },
];

function slamCurrent() {
  var id = "";
  try {
    id = wx.getStorageSync(SLAM_STORAGE_KEY) || "";
  } catch (e) {}
  for (var i = 0; i < SLAM_THEMES.length; i++) {
    if (SLAM_THEMES[i].id === id) return SLAM_THEMES[i];
  }
  return SLAM_THEMES[0];
}

function slamPageStyle(theme) {
  return (theme || slamCurrent()).vars;
}

/** 下拉刷新 / 窗口底色用的纯色（与球场主色一致） */
function slamBgColor(theme) {
  theme = theme || slamCurrent();
  var m = String(theme.vars || "").match(/--court-a:\s*(#[0-9a-fA-F]{3,8})/);
  return (m && m[1]) || theme.nav || "#0c3b2e";
}

function slamApplyNav(theme) {
  theme = theme || slamCurrent();
  if (typeof wx.setNavigationBarColor === "function") {
    wx.setNavigationBarColor({
      backgroundColor: theme.nav,
      frontColor: theme.front || "#ffffff",
      animation: { duration: 0, timingFunc: "linear" },
    });
  }
  // 下拉刷新露出来的窗口背景，需与球场风格同步（否则会残留默认绿）
  if (typeof wx.setBackgroundColor === "function") {
    var bg = slamBgColor(theme);
    wx.setBackgroundColor({
      backgroundColor: bg,
      backgroundColorTop: bg,
      backgroundColorBottom: bg,
    });
  }
}

function slamRefreshTabBar(theme) {
  theme = theme || slamCurrent();
  var ok = false;
  try {
    var pages = getCurrentPages();
    for (var i = pages.length - 1; i >= 0; i--) {
      var page = pages[i];
      if (!page || typeof page.getTabBar !== "function") continue;
      var bar = page.getTabBar();
      if (!bar) continue;
      if (typeof bar.applyTheme === "function") {
        bar.applyTheme(theme);
        ok = true;
      } else if (typeof bar.updateSelected === "function") {
        bar.updateSelected();
        ok = true;
      }
    }
  } catch (e) {}
  return ok;
}

function slamSetTheme(id) {
  try {
    wx.setStorageSync(SLAM_STORAGE_KEY, id);
  } catch (e) {}
  var theme = slamCurrent();
  slamApplyNav(theme);
  slamRefreshTabBar(theme);
  return theme;
}

/** 给 H5 链接带上当前球场风格 ?court=（已有则替换） */
function slamWithCourt(url) {
  var raw = String(url || "");
  if (!raw) return raw;
  var id = slamCurrent().id || "wimbledon";
  if (/[?&]court=/.test(raw)) {
    return raw.replace(/([?&]court=)[^&]*/, "$1" + id);
  }
  return raw + (raw.indexOf("?") >= 0 ? "&" : "?") + "court=" + id;
}

var slamTheme = {
  STORAGE_KEY: SLAM_STORAGE_KEY,
  THEMES: SLAM_THEMES,
  current: slamCurrent,
  pageStyle: slamPageStyle,
  bgColor: slamBgColor,
  applyNav: slamApplyNav,
  setTheme: slamSetTheme,
  withCourt: slamWithCourt,
  refreshTabBar: slamRefreshTabBar,
};

/** 小程序前端全局配置（打包进客户端） */
var APP_CONFIG = {};
try {
  APP_CONFIG = require("../config/app_config.json") || {};
} catch (e) {
  APP_CONFIG = {};
}

function isDevModeAllowed(uid) {
  var list = (APP_CONFIG && APP_CONFIG.devModeWhitelist) || [];
  if (!Array.isArray(list) || !list.length) return false;
  var id = String(uid || "").trim();
  if (!id) return false;
  for (var i = 0; i < list.length; i++) {
    if (String(list[i]).trim() === id) return true;
  }
  return false;
}

function readDevMode(uid) {
  if (!isDevModeAllowed(uid)) {
    try {
      wx.setStorageSync("dev_mode", false);
    } catch (e) {}
    return false;
  }
  try {
    return !!(wx.getStorageSync("dev_mode") || false);
  } catch (e) {
    return false;
  }
}

function writeDevMode(uid, on) {
  if (on && !isDevModeAllowed(uid)) {
    try {
      wx.setStorageSync("dev_mode", false);
    } catch (e) {}
    return false;
  }
  try {
    wx.setStorageSync("dev_mode", !!on);
  } catch (e) {}
  return !!on;
}

/** 测测球速：带上当前球场风格，打开内嵌检测页 */
function openPoseTest() {
  if (!WEB_POSE_URL) {
    wx.showToast({ title: "未配置检测地址", icon: "none" });
    return;
  }
  var url = slamWithCourt(WEB_POSE_URL);
  wx.navigateTo({
    url: "/pages/pose-webview/index?url=" + encodeURIComponent(url),
  });
}

var _slamBehavior = null;

function getSlamBehavior() {
  if (_slamBehavior) return _slamBehavior;
  _slamBehavior = Behavior({
    data: {
      pageStyle: slamTheme.pageStyle(),
      slamId: slamTheme.current().id,
      slamBg: slamTheme.bgColor(),
    },

    lifetimes: {
      attached: function () {
        this.applySlamTheme();
      },
    },

    pageLifetimes: {
      show: function () {
        this.applySlamTheme();
      },
    },

    methods: {
      applySlamTheme: function () {
        var theme = slamTheme.current();
        slamTheme.applyNav(theme);
        slamTheme.refreshTabBar(theme);
        var style = slamTheme.pageStyle(theme);
        var bg = slamTheme.bgColor(theme);
        if (
          this.data.pageStyle !== style ||
          this.data.slamId !== theme.id ||
          this.data.slamBg !== bg
        ) {
          this.setData({ pageStyle: style, slamId: theme.id, slamBg: bg });
        }
      },
    },
  });
  return _slamBehavior;
}

module.exports = {
  API_BASE_URL,
  LOCAL_DEV,
  UPLOAD_TIMEOUT_MS,
  REQUEST_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  HEALTH_TIMEOUT_MS,
  UPLOAD_WARN_SIZE_MB,
  UPLOAD_WARN_DURATION_SEC,
  UPLOAD_LARGE_ROUTE_MB,
  UPLOAD_CHUNK_DURATION_SEC,
  UPLOAD_COMPRESS_ABOVE_MB,
  UPLOAD_COMPRESS_AGGRESSIVE_MB,
  UPLOAD_COMPRESS_AGGRESSIVE_SEC,
  UPLOAD_COMPRESS_QUALITY,
  FEED_USE_MOCK,
  APP_BUILD_TAG,
  WEB_STROKE_URL,
  WEB_ANALYZE_URL,
  WEB_POSE_URL,
  YOLO_POSE_MODEL_URL,
  YOLO_POSE_IMGSZ,
  POSE_API_BASE,
  POSE_DETECT_URL,
  POSE_HEALTH_URL,
  RTMPOSE_V2_API_BASE,
  RTMPOSE_V2_DETECT_URL,
  RTMPOSE_V2_HEALTH_URL,
  POSE_ANALYZE_VIDEO_URL,
  POSE_ANALYZE_STATUS_URL,
  POSE_ANALYZE_FILE_URL,
  isApiConfigValid,
  apiConfigHint,
  apiHostForWhitelist,
  domainWhitelistHint,
  isDomainListError,
  slamTheme,
  openPoseTest,
  APP_CONFIG,
  isDevModeAllowed,
  readDevMode,
  writeDevMode,
  get slamBehavior() {
    return getSlamBehavior();
  },
};
