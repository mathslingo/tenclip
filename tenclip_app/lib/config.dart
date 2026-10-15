/// 全局配置（对齐 miniprogram/utils/config.js）
library;

const String appDisplayName = 'UChance';

/// 本机调试开关：true=走 [localApiHost]；false=走线上 [prodApiBaseUrl]
const bool localDev = false;

/// 本地后端（WSL/本机局域网 IP + 7861，真机调试须 GRADIO_SERVER_NAME=0.0.0.0）
const String localApiHost = 'http://127.0.0.1:7861';

/// 线上 API（与小程序 PROD_API_BASE_URL 一致）
const String prodApiBaseUrl = 'https://api.uchance.tech';

const String apiBaseUrl = localDev ? localApiHost : prodApiBaseUrl;

/// 每次发布前更新，用于确认手机跑的是新包
const String appBuildTag = '2026-10-15-ios-port';

/// 发现页：true=本地 Mock；false=请求 /api/news/feed（失败回退 Mock）
const bool feedUseMockDefault = false;

// ── 上传策略（与小程序一致）──
const int uploadLargeRouteMb = 15; // 超过此大小自动走分片上传
const int uploadChunkDurationSec = 300; // 超过此时长也走分片
const int uploadTimeoutMs = 1800000; // 上传/下载总超时（30 分钟）
const int requestTimeoutMs = 30000; // 普通请求超时
const int healthTimeoutMs = 12000; // 探活超时
const int downloadTimeoutMs = 1800000;
const int uploadWarnSizeMb = 30; // 选视频时提示阈值
const int uploadWarnDurationSec = 600;
const double uploadCompressAboveMb = 0.5; // 超过才压缩
const int uploadCompressAggressiveMb = 60;
const int uploadCompressAggressiveSec = 600;
const int chunkSizeBytes = 2 * 1024 * 1024; // 分片大小 2MB
const int chooseVideoMaxSec = 60; // 拍摄最长 60s

// ── H5 对照页 ──
const String webStrokeUrl = '$apiBaseUrl/web/stroke';
const String webAnalyzeUrl = '$apiBaseUrl/web';
const String webPoseUrl = '$apiBaseUrl/yolo-pose/';

// ── 旧版默认（击球检测参数与小程序一致）──
const String defaultDetectMode = 'spike';
const double defaultMotionPercentile = 74;

/// 秒 → 「N 秒 / N 分 N 秒」
String formatDurationShort(num sec) {
  final s = sec < 0 ? 0 : sec.round();
  if (s < 60) return '$s 秒';
  final m = s ~/ 60;
  final r = s % 60;
  return r > 0 ? '$m 分 $r 秒' : '$m 分钟';
}
