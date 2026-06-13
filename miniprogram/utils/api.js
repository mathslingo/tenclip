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
} = require("./config");

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

function formatDiagnoseReport(diag) {
  var lines = [
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
      "连接被中断（ERR_CONNECTION_RESET）。请换 WiFi 重试；若反复出现，在 ECS 检查 systemctl status tenclip-api 与 Nginx。"
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

function uploadStrokeExtract(opts) {
  return uploadMultipartRetry({
    url: API_BASE_URL + "/api/mobile/stroke-extract/submit",
    filePath: opts.filePath,
    name: "video",
    formData: {
      detect_mode: opts.detectMode || "combined",
      motion_percentile: String(opts.motionPercentile != null ? opts.motionPercentile : 72),
      vlm_filter: opts.vlmFilter ? "1" : "0",
    },
    onProgress: opts.onProgress,
    onRetry: opts.onRetry,
  });
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
  return uploadMultipartRetry({
    url: API_BASE_URL + "/api/mobile/analyze-video/submit",
    filePath: opts.filePath,
    name: "video",
    formData: {
      perf_mode: opts.perfMode || "eco",
      prompt_profile: opts.promptProfile || "default",
    },
    onProgress: opts.onProgress,
    onRetry: opts.onRetry,
  });
}

function getAnalyzeTask(taskId) {
  return requestJson(API_BASE_URL + "/api/mobile/analyze-video/tasks/" + taskId);
}

function isUserCancelPick(err) {
  var msg = (err && err.errMsg) || "";
  return msg.indexOf("cancel") !== -1 || msg.indexOf("用户取消") !== -1;
}

var CHOOSE_VIDEO_MAX_SEC = 60;

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

function prepareVideoForUpload(filePath, sizeBytes, onStatus) {
  var threshold = UPLOAD_COMPRESS_ABOVE_MB * 1024 * 1024;
  if (!sizeBytes || sizeBytes < threshold || typeof wx.compressVideo !== "function") {
    return Promise.resolve({ filePath: filePath, size: sizeBytes || 0 });
  }
  if (onStatus) onStatus("compressing");
  return new Promise(function (resolve) {
    wx.compressVideo({
      src: filePath,
      quality: UPLOAD_COMPRESS_QUALITY,
      success: function (res) {
        statFileSize(res.tempFilePath).then(function (newSize) {
          resolve({
            filePath: res.tempFilePath,
            size: newSize || sizeBytes,
            compressed: true,
          });
        });
      },
      fail: function () {
        resolve({ filePath: filePath, size: sizeBytes, compressed: false });
      },
    });
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
  return pickChooseVideo({ sourceType: ["album"], compressed: true })
    .catch(function (err) {
      if (isUserCancelPick(err)) throw err;
      if (isPrivacyError(err)) {
        return requirePrivacyIfNeeded().then(function () {
          return pickChooseVideo({ sourceType: ["album"], compressed: true });
        });
      }
      return pickChooseMedia({ sourceType: ["album"] });
    })
    .catch(function (err) {
      if (isUserCancelPick(err)) throw err;
      return pickChooseMedia({
        sourceType: ["album", "camera"],
        maxDuration: CHOOSE_VIDEO_MAX_SEC,
      });
    })
    .catch(function (err) {
      if (isUserCancelPick(err)) throw err;
      if (isPrivacyError(err)) {
        return requirePrivacyIfNeeded().then(function () {
          return pickChooseVideo({ sourceType: ["album", "camera"], compressed: true });
        });
      }
      return pickChooseVideo({ sourceType: ["album", "camera"], compressed: true });
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
  showChooseFail,
  prepareVideoForUpload,
  formatUploadProgress,
  diagnoseApiConnection,
  formatDiagnoseReport,
};
