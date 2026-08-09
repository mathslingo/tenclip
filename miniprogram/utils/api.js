const {
  API_BASE_URL,
  LOCAL_DEV,
  UPLOAD_TIMEOUT_MS,
  REQUEST_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  HEALTH_TIMEOUT_MS,
  isApiConfigValid,
  apiConfigHint,
  domainWhitelistHint,
  isDomainListError,
  UPLOAD_COMPRESS_ABOVE_MB,
  UPLOAD_COMPRESS_QUALITY,
  UPLOAD_LARGE_ROUTE_MB,
  APP_BUILD_TAG,
} = require("./config");

function mapUploadProgressPercent(wxPct) {
  return Math.min(58, Math.max(22, 22 + Math.round((wxPct || 0) * 0.36)));
}

function compressProgressMessage(sizeBytes, simulatedPct) {
  var mb = sizeBytes ? (sizeBytes / (1024 * 1024)).toFixed(0) : "?";
  if (simulatedPct < 8) {
    return "正在读取并压缩视频（约 " + mb + " MB），请稍候…";
  }
  if (simulatedPct < 18) {
    return "压缩进行中（约 " + simulatedPct + "%），长视频可能需要 1～3 分钟…";
  }
  return "即将完成压缩（约 " + simulatedPct + "%），随后自动上传…";
}

function compressTickIntervalMs(sizeBytes) {
  var mb = sizeBytes / (1024 * 1024);
  if (mb >= 100) return 2200;
  if (mb >= 50) return 1800;
  if (mb >= 20) return 1400;
  return 1000;
}

function _errText(err) {
  return String((err && err.message) || (err && err.errMsg) || err || "").toLowerCase();
}

function isTimeoutError(err) {
  const msg = _errText(err);
  return msg.includes("timeout") || msg.includes("timed out");
}

/** 息屏、切后台、弱网导致的可恢复错误（轮询应继续而非判失败） */
function isTransientNetworkError(err) {
  const msg = _errText(err);
  return (
    isTimeoutError(err) ||
    msg.includes("interrupted") ||
    msg.includes("abort") ||
    msg.includes("cancel") ||
    msg.includes("network") ||
    msg.includes("连接") ||
    msg.includes("断开") ||
    msg.includes("connection_reset") ||
    msg.includes("connection reset") ||
    msg.includes("err_connection")
  );
}

function isConnectionResetError(err) {
  const msg = _errText(err);
  return (
    msg.includes("connection_reset") ||
    msg.includes("connection reset") ||
    msg.includes("err_connection_reset")
  );
}

function isUploadRetryableError(err) {
  if (isDomainListError(err)) return false;
  return isTransientNetworkError(err);
}

/** 服务端尚未部署分片上传接口时（404），回退普通 uploadFile */
function isChunkApiUnavailableError(err) {
  var msg = _errText(err);
  return (
    msg.indexOf("404") !== -1 ||
    msg.indexOf("not found") !== -1 ||
    msg.indexOf("upload-sessions") !== -1
  );
}

function isInterruptedError(err) {
  return _errText(err).includes("interrupted");
}

function pollRetryMessage(err, streak) {
  if (isInterruptedError(err)) {
    return "分析仍在服务器进行，可暂时息屏；亮屏后会自动继续…";
  }
  return "网络波动，继续等待…（" + streak + "）";
}

function setKeepScreenOn(keepOn) {
  if (typeof wx.setKeepScreenOn === "function") {
    wx.setKeepScreenOn({ keepScreenOn: !!keepOn });
  }
}

/** 微信聊天内浏览器能通、小程序 Cronet reset 时：禁用 http2/quic/httpdns（走 HTTP/1.1） */
function wxCronetCompatOpts() {
  return {
    enableHttp2: false,
    enableQuic: false,
    enableHttpDNS: false,
  };
}

function parseApiDetail(body, fallback) {
  if (!body) return fallback;
  var detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map(function (d) {
        return (d && d.msg) || String(d);
      })
      .join("; ");
  }
  return fallback;
}

function diagnoseApiConnection() {
  return new Promise(function (resolve) {
    var result = {
      apiBase: API_BASE_URL,
      localDev: LOCAL_DEV,
      requestOk: false,
      httpStatus: 0,
      body: "",
      errMsg: "",
    };
    wx.request(
      Object.assign(
        {
          url: API_BASE_URL + "/api/mobile/health",
          method: "GET",
          timeout: HEALTH_TIMEOUT_MS,
          success: function (res) {
            result.httpStatus = res.statusCode;
            result.body =
              typeof res.data === "object" ? JSON.stringify(res.data) : String(res.data || "");
            result.requestOk = res.statusCode === 200 && res.data && res.data.ok;
            resolve(result);
          },
          fail: function (err) {
            result.errMsg = (err && err.errMsg) || String(err);
            resolve(result);
          },
        },
        wxCronetCompatOpts()
      )
    );
  });
}

/** 多路探针：对比 Cronet 选项、路径、对照域名（开发者工具需勾选不校验合法域名） */
function requestProbe(label, url, extraOpts) {
  return new Promise(function (resolve) {
    var started = Date.now();
    wx.request(
      Object.assign(
        {
          url: url,
          method: "GET",
          timeout: HEALTH_TIMEOUT_MS,
          success: function (res) {
            resolve({
              label: label,
              ok: res.statusCode >= 200 && res.statusCode < 500,
              ms: Date.now() - started,
              status: res.statusCode,
              errMsg: "",
            });
          },
          fail: function (err) {
            resolve({
              label: label,
              ok: false,
              ms: Date.now() - started,
              status: 0,
              errMsg: (err && err.errMsg) || String(err),
            });
          },
        },
        extraOpts || {}
      )
    );
  });
}

function runNetworkExperiments() {
  var health = API_BASE_URL + "/api/mobile/health";
  var probes = [
    requestProbe("① health + Cronet兼容", health, wxCronetCompatOpts()),
    requestProbe("② health + 默认Cronet", health, {}),
    requestProbe("③ 站点根路径 /", API_BASE_URL + "/", wxCronetCompatOpts()),
    requestProbe("④ qq.com对照", "https://www.qq.com/favicon.ico", wxCronetCompatOpts()),
  ];
  return Promise.all(probes);
}

function formatNetworkExperimentReport(results) {
  var lines = ["构建：" + APP_BUILD_TAG, "API：" + API_BASE_URL, ""];
  results.forEach(function (r) {
    var head = r.label + ": ";
    if (r.ok) {
      lines.push(head + "成功 HTTP " + r.status + " · " + r.ms + "ms");
    } else {
      lines.push(head + "失败 · " + r.ms + "ms");
      lines.push("    " + r.errMsg);
    }
  });
  lines.push("");
  lines.push("【如何解读】");
  lines.push("• ①成功②失败 → 保持 enableHttp2:false");
  lines.push("• ①②都 reset → 问题在小程序 Cronet↔你的域名");
  lines.push("• ④成功①失败 → 仅 api.uchance.tech 被拦（备案/TLS/SNI）");
  lines.push("• ④也失败 → 整机网络或开发者工具环境问题");
  lines.push("");
  lines.push("真机实验：同时 ECS 执行");
  lines.push("sudo tail -f /var/log/nginx/access.log");
  lines.push("若小程序请求时 access.log 无新行 → 包未到 Nginx（客户端中断）");
  return lines.join("\n");
}

function diagnoseWithExperiments() {
  return diagnoseApiConnection().then(function (diag) {
    return runNetworkExperiments().then(function (probes) {
      return {
        diag: diag,
        probes: probes,
        report:
          formatDiagnoseReport(diag) +
          "\n\n—— 对照实验 ——\n" +
          formatNetworkExperimentReport(probes),
      };
    });
  });
}

function formatDiagnoseReport(diag) {
  var lines = [
    "构建版本：" + APP_BUILD_TAG,
    "API 地址：" + diag.apiBase,
    "LOCAL_DEV：" + diag.localDev,
  ];
  if (diag.requestOk) {
    lines.push("request 探活：成功 " + diag.body);
    lines.push("");
    lines.push("若上传仍无 POST，请重点检查公众平台 uploadFile 合法域名（与 request 分开配置）。");
  } else if (diag.errMsg) {
    lines.push("request 探活：失败");
    lines.push("errMsg：" + diag.errMsg);
    lines.push("");
    if (isDomainListError({ errMsg: diag.errMsg })) {
      lines.push(domainWhitelistHint());
    } else {
      lines.push(
        "微信内打开链接正常、仅小程序失败时：\n" +
          "已关闭 HTTP/2（enableHttp2:false）。请更新体验版并重试。\n" +
          "ECS 同时执行: bash scripts/deploy/patch-nginx-wechat-upload.sh"
      );
    }
  } else {
    lines.push("HTTP " + diag.httpStatus + " " + diag.body);
  }
  return lines.join("\n");
}

function pingHealthOnce() {
  return new Promise(function (resolve, reject) {
    wx.request(
      Object.assign(
        {
          url: API_BASE_URL + "/api/mobile/health",
          method: "GET",
          timeout: HEALTH_TIMEOUT_MS,
          success: function (res) {
            if (res.statusCode === 200 && res.data && res.data.ok) {
              resolve(res.data);
              return;
            }
            reject(new Error("后端未就绪 (HTTP " + res.statusCode + ")"));
          },
          fail: function (err) {
            reject(normalizeError(err, "无法连接后端，请确认已启动 app.py 且 LOCAL_API_HOST 正确"));
          },
        },
        wxCronetCompatOpts()
      )
    );
  });
}

function pingHealth(maxAttempts) {
  var limit = maxAttempts != null ? maxAttempts : 5;
  var attempt = 0;
  function run() {
    attempt += 1;
    return pingHealthOnce().catch(function (err) {
      if (isTransientNetworkError(err) && attempt < limit) {
        return new Promise(function (resolve) {
          setTimeout(resolve, 500 * attempt);
        }).then(run);
      }
      return Promise.reject(err);
    });
  }
  return run();
}

function normalizeError(err, fallback) {
  if (isTimeoutError(err)) {
    return new Error(
      "上传超时：请用 WiFi、换较短视频（<1 分钟试跑），或联系检查服务器 Nginx client_body_timeout"
    );
  }
  if (isConnectionResetError(err)) {
    return new Error(
      "连接被中断（ERR_CONNECTION_RESET）。请换 WiFi 重试；大视频请先压缩或选较短片段。服务器检查：systemctl status tenclip-uchanceai、Nginx 反代需 proxy_request_buffering on、443 勿开 http2/quic。"
    );
  }
  var raw = (err && err.errMsg) || (err && err.message) || "";
  if (/^request:fail\s*$/i.test(raw.trim())) {
    return new Error(
      "无法连接 API（request:fail）\n当前地址：" +
        API_BASE_URL +
        "\n请检查手机网络、HTTPS 证书、微信公众平台 request 合法域名，以及 ECS 上 tenclip-api 是否在运行。"
    );
  }
  if (err && err.message && err.message !== "request:fail") return err;
  if (raw) return new Error(raw);
  return new Error(fallback || "网络错误");
}

function requestJson(url, method) {
  const m = method || "GET";
  return new Promise(function (resolve, reject) {
    wx.request(
      Object.assign(
        {
          url: url,
          method: m,
          timeout: REQUEST_TIMEOUT_MS,
          success: function (res) {
            if (res.statusCode === 404) {
              reject(new Error("任务不存在"));
              return;
            }
            if (res.statusCode < 200 || res.statusCode >= 300) {
              var body = res.data;
              var detail =
                (typeof body === "object" && parseApiDetail(body, "")) ||
                "请求失败 (" + res.statusCode + ")";
              reject(new Error(detail));
              return;
            }
            resolve(res.data);
          },
          fail: function (err) {
            reject(normalizeError(err, "网络错误"));
          },
        },
        wxCronetCompatOpts()
      )
    );
  });
}

function uploadMultipart(opts) {
  if (!isApiConfigValid()) {
    return Promise.reject(new Error(apiConfigHint()));
  }
  var onProgress = opts.onProgress;
  return new Promise(function (resolve, reject) {
    var task = wx.uploadFile(
      Object.assign(
        {
          url: opts.url,
          filePath: opts.filePath,
          name: opts.name,
          formData: opts.formData,
          timeout: UPLOAD_TIMEOUT_MS,
          success: function (res) {
            if (res.statusCode < 200 || res.statusCode >= 300) {
              var detail = "上传失败 (" + res.statusCode + ")";
              try {
                var body = JSON.parse(res.data || "{}");
                detail = parseApiDetail(body, detail);
              } catch (e) {
                /* ignore */
              }
              reject(new Error(detail));
              return;
            }
            try {
              resolve(JSON.parse(res.data));
            } catch (e2) {
              reject(new Error("响应解析失败"));
            }
          },
          fail: function (err) {
            if (isDomainListError(err)) {
              reject(new Error("域名未在白名单\n\n" + domainWhitelistHint()));
              return;
            }
            reject(normalizeError(err, "上传失败"));
          },
        },
        wxCronetCompatOpts()
      )
    );
    if (onProgress && task && typeof task.onProgressUpdate === "function") {
      task.onProgressUpdate(function (ev) {
        onProgress({
          progress: ev.progress,
          sent: ev.totalBytesSent,
          total: ev.totalBytesExpectedToSend,
        });
      });
    }
  });
}

function downloadToTemp(url, onProgress) {
  return new Promise(function (resolve, reject) {
    var task = wx.downloadFile(
      Object.assign(
        {
          url: url,
          timeout: DOWNLOAD_TIMEOUT_MS,
          success: function (res) {
            if (res.statusCode !== 200) {
              reject(new Error("下载失败 (" + res.statusCode + ")"));
              return;
            }
            resolve(res.tempFilePath);
          },
          fail: function (err) {
            reject(normalizeError(err, "下载失败"));
          },
        },
        wxCronetCompatOpts()
      )
    );
    if (onProgress && task && typeof task.onProgressUpdate === "function") {
      task.onProgressUpdate(function (ev) {
        onProgress({ progress: ev.progress });
      });
    }
  });
}

function uploadMultipartRetry(opts) {
  var maxAttempts = opts.maxAttempts != null ? opts.maxAttempts : 5;
  var attempt = 0;
  function tryOnce() {
    attempt += 1;
    return uploadMultipart(opts).catch(function (err) {
      if (!isUploadRetryableError(err) || attempt >= maxAttempts) {
        return Promise.reject(normalizeError(err, "上传失败"));
      }
      if (opts.onRetry) {
        opts.onRetry({ attempt: attempt, maxAttempts: maxAttempts });
      }
      return new Promise(function (resolve) {
        setTimeout(resolve, 1500 * attempt);
      }).then(tryOnce);
    });
  }
  return tryOnce();
}

var CHUNK_SIZE_BYTES = 2 * 1024 * 1024;

function _videoBasename(filePath) {
  var p = String(filePath || "");
  var i = Math.max(p.lastIndexOf("/"), p.lastIndexOf("\\"));
  return i >= 0 ? p.slice(i + 1) : p || "video.mp4";
}

function _chunkRequestForm(url, data) {
  return new Promise(function (resolve, reject) {
    wx.request(
      Object.assign(
        {
          url: url,
          method: "POST",
          timeout: UPLOAD_TIMEOUT_MS,
          header: { "content-type": "application/x-www-form-urlencoded" },
          data: data,
          success: function (res) {
            if (res.statusCode < 200 || res.statusCode >= 300) {
              var detail = parseApiDetail(res.data, "请求失败 (" + res.statusCode + ")");
              reject(new Error(detail));
              return;
            }
            resolve(res.data);
          },
          fail: function (err) {
            if (isDomainListError(err)) {
              reject(new Error("域名未在白名单\n\n" + domainWhitelistHint()));
              return;
            }
            reject(normalizeError(err, "网络错误"));
          },
        },
        wxCronetCompatOpts()
      )
    );
  });
}

function _chunkRequestBinary(method, url, data) {
  return new Promise(function (resolve, reject) {
    wx.request(
      Object.assign(
        {
          url: url,
          method: method,
          timeout: UPLOAD_TIMEOUT_MS,
          header: { "content-type": "application/octet-stream" },
          data: data,
          success: function (res) {
            if (res.statusCode < 200 || res.statusCode >= 300) {
              var detail = parseApiDetail(res.data, "上传失败 (" + res.statusCode + ")");
              reject(new Error(detail));
              return;
            }
            resolve(res.data);
          },
          fail: function (err) {
            if (isDomainListError(err)) {
              reject(new Error("域名未在白名单\n\n" + domainWhitelistHint()));
              return;
            }
            reject(normalizeError(err, "上传失败"));
          },
        },
        wxCronetCompatOpts()
      )
    );
  });
}

function _readFileChunk(filePath, position, length) {
  return new Promise(function (resolve, reject) {
    wx.getFileSystemManager().readFile({
      filePath: filePath,
      position: position,
      length: length,
      success: function (res) {
        resolve(res.data);
      },
      fail: function (err) {
        reject(normalizeError(err, "读取视频分片失败"));
      },
    });
  });
}

function _uploadChunkWithRetry(sessionId, chunkIndex, buffer, onRetry, maxAttempts) {
  var limit = maxAttempts != null ? maxAttempts : 5;
  var attempt = 0;
  var url =
    API_BASE_URL +
    "/api/mobile/upload-sessions/" +
    sessionId +
    "/chunks/" +
    chunkIndex;

  function tryOnce() {
    attempt += 1;
    return _chunkRequestBinary("PUT", url, buffer).catch(function (err) {
      if (!isUploadRetryableError(err) || attempt >= limit) {
        return Promise.reject(err);
      }
      if (onRetry) {
        onRetry({ attempt: attempt, maxAttempts: limit, chunkIndex: chunkIndex });
      }
      return new Promise(function (resolve) {
        setTimeout(resolve, 1500 * attempt);
      }).then(tryOnce);
    });
  }
  return tryOnce();
}

function chunkVideoUpload(opts) {
  if (!isApiConfigValid()) {
    return Promise.reject(new Error(apiConfigHint()));
  }

  var filePath = opts.filePath;
  var fileSize = opts.fileSize;
  var purpose = opts.purpose;
  var formData = opts.formData || {};
  var onProgress = opts.onProgress;
  var onRetry = opts.onRetry;

  var totalChunks = Math.max(1, Math.ceil(fileSize / CHUNK_SIZE_BYTES));
  var initData = Object.assign({}, formData, {
    purpose: purpose,
    file_size: String(fileSize),
    filename: _videoBasename(filePath),
    total_chunks: String(totalChunks),
    chunk_size: String(CHUNK_SIZE_BYTES),
  });

  return _chunkRequestForm(API_BASE_URL + "/api/mobile/upload-sessions", initData).then(
    function (session) {
      var sessionId = session.session_id;
      var chunkSize = session.chunk_size || CHUNK_SIZE_BYTES;
      var chunks = session.total_chunks || totalChunks;
      var index = 0;

      function next() {
        if (index >= chunks) {
          return _chunkRequestForm(
            API_BASE_URL + "/api/mobile/upload-sessions/" + sessionId + "/complete",
            {}
          );
        }
        var offset = index * chunkSize;
        var length = Math.min(chunkSize, fileSize - offset);
        return _readFileChunk(filePath, offset, length)
          .then(function (buffer) {
            return _uploadChunkWithRetry(sessionId, index, buffer, onRetry);
          })
          .then(function () {
            index += 1;
            if (onProgress) {
              var pct = Math.min(99, Math.round((index / chunks) * 100));
              onProgress({
                progress: pct,
                sent: Math.min(fileSize, index * chunkSize),
                total: fileSize,
              });
            }
            return next();
          });
      }

      return next();
    }
  );
}

function routeVideoUpload(filePath, fileSize, smallUploadFn, chunkOpts) {
  var getSize =
    fileSize != null && fileSize > 0
      ? Promise.resolve(fileSize)
      : statFileSize(filePath);
  return getSize.then(function (sizeBytes) {
    var threshold = UPLOAD_LARGE_ROUTE_MB * 1024 * 1024;
    if (sizeBytes > threshold) {
      return chunkVideoUpload(
        Object.assign({}, chunkOpts, {
          filePath: filePath,
          fileSize: sizeBytes,
        })
      ).catch(function (err) {
        if (isChunkApiUnavailableError(err)) {
          console.warn("[TenniTi] chunk upload unavailable, fallback to uploadFile");
          return smallUploadFn();
        }
        return Promise.reject(err);
      });
    }
    return smallUploadFn();
  });
}

function uploadStrokeExtract(opts) {
  var multipart = {
    url: API_BASE_URL + "/api/mobile/stroke-extract/submit",
    filePath: opts.filePath,
    name: "video",
    formData: {
      detect_mode: opts.detectMode || "combined",
      motion_percentile: String(opts.motionPercentile != null ? opts.motionPercentile : 74),
      vlm_filter: opts.vlmFilter ? "1" : "0",
    },
    onProgress: opts.onProgress,
    onRetry: opts.onRetry,
  };
  return routeVideoUpload(
    opts.filePath,
    opts.fileSize,
    function () {
      return uploadMultipartRetry(multipart);
    },
    {
      purpose: "stroke",
      formData: multipart.formData,
      onProgress: opts.onProgress,
      onRetry: opts.onRetry,
    }
  );
}

function getStrokeTask(taskId) {
  return requestJson(API_BASE_URL + "/api/mobile/stroke-extract/tasks/" + taskId);
}

function strokeDownloadUrl(taskId) {
  return API_BASE_URL + "/api/mobile/stroke-extract/tasks/" + taskId + "/download";
}

function downloadStrokeResult(taskId, onProgress) {
  return downloadToTemp(strokeDownloadUrl(taskId), onProgress);
}

function uploadAnalyzeSubmit(opts) {
  var multipart = {
    url: API_BASE_URL + "/api/mobile/analyze-video/submit",
    filePath: opts.filePath,
    name: "video",
    formData: {
      perf_mode: opts.perfMode || "eco",
      prompt_profile: opts.promptProfile || "default",
    },
    onProgress: opts.onProgress,
    onRetry: opts.onRetry,
  };
  return routeVideoUpload(
    opts.filePath,
    opts.fileSize,
    function () {
      return uploadMultipartRetry(multipart);
    },
    {
      purpose: "analyze",
      formData: multipart.formData,
      onProgress: opts.onProgress,
      onRetry: opts.onRetry,
    }
  );
}

function getAnalyzeTask(taskId) {
  return requestJson(API_BASE_URL + "/api/mobile/analyze-video/tasks/" + taskId);
}

function isUserCancelPick(err) {
  var msg = (err && err.errMsg) || "";
  return msg.indexOf("cancel") !== -1 || msg.indexOf("用户取消") !== -1;
}

var CHOOSE_VIDEO_MAX_SEC = 60;
var CHOOSE_GUIDE_SEEN_KEY = "tenclip_choose_video_guide_seen";

var CHOOSE_VIDEO_HELP_TEXT =
  "在预览页点绿色「发送」后，微信会显示「正在加载」。这是在读入视频文件，大视频可能需要 1～3 分钟，属于正常现象，并非小程序报错。\n\n请耐心等待，不要重复点击发送或退出。";

function showChooseVideoHelp() {
  return new Promise(function (resolve) {
    wx.showModal({
      title: "为什么发送后很慢？",
      content: CHOOSE_VIDEO_HELP_TEXT,
      confirmText: "知道了",
      showCancel: false,
      success: function () {
        resolve();
      },
      fail: function () {
        resolve();
      },
    });
  });
}

function ensureChooseVideoGuide() {
  if (wx.getStorageSync(CHOOSE_GUIDE_SEEN_KEY)) {
    return Promise.resolve();
  }
  return new Promise(function (resolve, reject) {
    wx.showModal({
      title: "选择视频提示",
      content: CHOOSE_VIDEO_HELP_TEXT,
      confirmText: "去选择",
      cancelText: "取消",
      success: function (res) {
        wx.setStorageSync(CHOOSE_GUIDE_SEEN_KEY, "1");
        if (res.confirm) {
          resolve();
        } else {
          reject({ errMsg: "chooseVideo:fail cancel" });
        }
      },
      fail: function () {
        resolve();
      },
    });
  });
}

function pickFromAlbumCompressed() {
  return pickChooseVideo({ sourceType: ["album"], compressed: true }).catch(function (err) {
    if (isUserCancelPick(err)) throw err;
    if (isPrivacyError(err)) {
      return requirePrivacyIfNeeded().then(function () {
        return pickChooseVideo({ sourceType: ["album"], compressed: true });
      });
    }
    return pickChooseMedia({ sourceType: ["album"] });
  });
}

function pickFromAlbumOrCamera() {
  return pickChooseMedia({
    sourceType: ["album", "camera"],
    maxDuration: CHOOSE_VIDEO_MAX_SEC,
  }).catch(function (err) {
    if (isUserCancelPick(err)) throw err;
    if (isPrivacyError(err)) {
      return requirePrivacyIfNeeded().then(function () {
        return pickChooseVideo({ sourceType: ["album", "camera"], compressed: true });
      });
    }
    return pickChooseVideo({ sourceType: ["album", "camera"], compressed: true });
  });
}

function pickChooseMedia(opts) {
  opts = opts || {};
  var sourceType = opts.sourceType || ["album"];
  return new Promise(function (resolve, reject) {
    var req = {
      count: 1,
      mediaType: ["video"],
      sourceType: sourceType,
      success: function (res) {
        var file = (res.tempFiles && res.tempFiles[0]) || {};
        if (!file.tempFilePath) {
          reject(new Error("未获取到视频路径"));
          return;
        }
        resolve({ tempFilePath: file.tempFilePath, size: file.size || 0 });
      },
      fail: function (err) {
        reject(err || new Error("chooseMedia 失败"));
      },
    };
    if (sourceType.indexOf("camera") !== -1) {
      var sec = opts.maxDuration || CHOOSE_VIDEO_MAX_SEC;
      req.maxDuration = Math.min(sec, CHOOSE_VIDEO_MAX_SEC);
    }
    wx.chooseMedia(req);
  });
}

function pickChooseVideo(opts) {
  opts = opts || {};
  return new Promise(function (resolve, reject) {
    wx.chooseVideo({
      sourceType: opts.sourceType || ["album"],
      compressed: opts.compressed !== false,
      maxDuration: CHOOSE_VIDEO_MAX_SEC,
      success: function (res) {
        if (!res.tempFilePath) {
          reject(new Error("未获取到视频路径"));
          return;
        }
        resolve({ tempFilePath: res.tempFilePath, size: res.size || 0 });
      },
      fail: function (err) {
        reject(err || new Error("chooseVideo 失败"));
      },
    });
  });
}

function statFileSize(filePath) {
  return new Promise(function (resolve) {
    try {
      wx.getFileSystemManager().stat({
        path: filePath,
        success: function (res) {
          resolve((res.stats && res.stats.size) || 0);
        },
        fail: function () {
          resolve(0);
        },
      });
    } catch (e) {
      resolve(0);
    }
  });
}

function compressionProfile(sizeBytes) {
  var mb = sizeBytes / (1024 * 1024);
  if (mb >= 100) {
    return { quality: UPLOAD_COMPRESS_QUALITY, bitrate: 350, resolution: 0.45, fps: 24 };
  }
  if (mb >= 60) {
    return { quality: UPLOAD_COMPRESS_QUALITY, bitrate: 450, resolution: 0.5, fps: 24 };
  }
  if (mb >= 30) {
    return { quality: UPLOAD_COMPRESS_QUALITY, bitrate: 600, resolution: 0.65, fps: 24 };
  }
  if (mb >= 10) {
    return { quality: UPLOAD_COMPRESS_QUALITY, bitrate: 800, resolution: 0.75, fps: 30 };
  }
  return { quality: UPLOAD_COMPRESS_QUALITY };
}

function prepareVideoForUpload(filePath, sizeBytes, callbacks) {
  var onStatus;
  var onCompressProgress;
  if (typeof callbacks === "function") {
    onStatus = callbacks;
  } else if (callbacks) {
    onStatus = callbacks.onStatus;
    onCompressProgress = callbacks.onCompressProgress;
  }

  var threshold = UPLOAD_COMPRESS_ABOVE_MB * 1024 * 1024;
  if (!sizeBytes || sizeBytes < threshold || typeof wx.compressVideo !== "function") {
    if (onCompressProgress) {
      onCompressProgress(12, "视频较小，跳过压缩，准备上传…");
    }
    return Promise.resolve({ filePath: filePath, size: sizeBytes || 0 });
  }
  if (onStatus) onStatus("compressing");

  var profile = compressionProfile(sizeBytes);
  var simTimer = null;
  var simulated = 2;
  var maxSim = 22;

  function stopSim() {
    if (simTimer) {
      clearInterval(simTimer);
      simTimer = null;
    }
  }

  function startSim() {
    if (!onCompressProgress) return;
    onCompressProgress(simulated, compressProgressMessage(sizeBytes, simulated));
    simTimer = setInterval(function () {
      if (simulated >= maxSim) return;
      simulated += 1;
      onCompressProgress(simulated, compressProgressMessage(sizeBytes, simulated));
    }, compressTickIntervalMs(sizeBytes));
  }

  startSim();

  return new Promise(function (resolve) {
    wx.compressVideo(
      Object.assign(
        {
          src: filePath,
          success: function (res) {
            stopSim();
            if (onCompressProgress) {
              onCompressProgress(24, "压缩完成，正在准备上传…");
            }
            statFileSize(res.tempFilePath).then(function (newSize) {
              resolve({
                filePath: res.tempFilePath,
                size: newSize || sizeBytes,
                compressed: true,
              });
            });
          },
          fail: function () {
            stopSim();
            if (onCompressProgress) {
              onCompressProgress(20, "压缩跳过，将上传原视频…");
            }
            resolve({ filePath: filePath, size: sizeBytes, compressed: false });
          },
        },
        profile
      )
    );
  });
}

function formatUploadProgress(ev, startMs) {
  var pct = Math.round(ev.progress || 0);
  var sent = ev.sent || 0;
  var total = ev.total || 0;
  var msg = "正在上传视频（" + pct + "%）";
  if (total > 0) {
    msg +=
      " · " +
      (sent / (1024 * 1024)).toFixed(1) +
      "/" +
      (total / (1024 * 1024)).toFixed(1) +
      " MB";
  }
  if (startMs && sent > 0) {
    var sec = (Date.now() - startMs) / 1000;
    if (sec >= 1) {
      msg += " · " + (sent / (1024 * 1024) / sec).toFixed(1) + " MB/s";
    }
  }
  return { pct: pct, message: msg };
}

function isPrivacyError(err) {
  var raw = (err && err.errMsg) || (err && err.message) || "";
  return /privacy|隐私|authorize|未同意|用户隐私/i.test(raw);
}

function requirePrivacyIfNeeded() {
  return new Promise(function (resolve, reject) {
    if (typeof wx.requirePrivacyAuthorize !== "function") {
      resolve();
      return;
    }
    var settled = false;
    function finish(fn, arg) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      fn(arg);
    }
    var timer = setTimeout(function () {
      finish(resolve);
    }, 8000);
    wx.requirePrivacyAuthorize({
      success: function () {
        finish(resolve);
      },
      fail: function (err) {
        finish(reject, err || new Error("未同意隐私协议，无法访问相册/相机"));
      },
    });
  });
}

function showChooseFail(err) {
  if (isUserCancelPick(err)) return;
  var raw = (err && err.errMsg) || (err && err.message) || String(err);
  var hint = raw;
  if (isPrivacyError(err) || raw.indexOf("privacy") !== -1 || raw.indexOf("隐私") !== -1) {
    hint +=
      "\n\n请在微信公众平台 → 设置 → 服务内容声明 → 用户隐私保护指引中勾选相册/选视频（chooseMedia），提交并发布指引后重新上传体验版。";
  }
  if (raw.indexOf("maxDuration") !== -1) {
    hint += "\n\n拍摄最长 60 秒；从相册可选更长比赛视频。";
  }
  wx.showModal({
    title: "选择视频失败",
    content: hint,
    showCancel: false,
  });
}

function chooseTennisVideo() {
  return ensureChooseVideoGuide()
    .then(function () {
      var t0 = Date.now();
      wx.showLoading({ title: "等待微信读入…", mask: true });
      return pickFromAlbumCompressed()
        .catch(function (err) {
          if (isUserCancelPick(err)) throw err;
          return pickFromAlbumOrCamera();
        })
        .finally(function () {
          wx.hideLoading();
        })
        .then(function (file) {
          if (Date.now() - t0 > 4000) {
            wx.showToast({ title: "视频已选入", icon: "success", duration: 1800 });
          }
          return file;
        });
    });
}

module.exports = {
  isTimeoutError,
  isTransientNetworkError,
  isInterruptedError,
  pollRetryMessage,
  setKeepScreenOn,
  pingHealth,
  uploadStrokeExtract,
  getStrokeTask,
  strokeDownloadUrl,
  downloadStrokeResult,
  uploadAnalyzeSubmit,
  getAnalyzeTask,
  chooseTennisVideo,
  showChooseVideoHelp,
  showChooseFail,
  requirePrivacyIfNeeded,
  prepareVideoForUpload,
  formatUploadProgress,
  mapUploadProgressPercent,
  diagnoseApiConnection,
  formatDiagnoseReport,
  runNetworkExperiments,
  formatNetworkExperimentReport,
  diagnoseWithExperiments,
};
