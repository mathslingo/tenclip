const {
  API_BASE_URL,
  UPLOAD_TIMEOUT_MS,
  REQUEST_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  HEALTH_TIMEOUT_MS,
  isApiConfigValid,
  apiConfigHint,
  domainWhitelistHint,
  isDomainListError,
} = require("./config");

function isTimeoutError(err) {
  const msg = String((err && err.message) || (err && err.errMsg) || err || "").toLowerCase();
  return msg.includes("timeout") || msg.includes("timed out");
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

function pingHealth() {
  return new Promise(function (resolve, reject) {
    wx.request({
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
    });
  });
}

function normalizeError(err, fallback) {
  if (isTimeoutError(err)) {
    return new Error(
      "上传超时：请用 WiFi、换较短视频（<1 分钟试跑），或联系检查服务器 Nginx client_body_timeout"
    );
  }
  if (err && err.message) return err;
  if (err && err.errMsg) return new Error(err.errMsg);
  return new Error(fallback || "网络错误");
}

function requestJson(url, method) {
  const m = method || "GET";
  return new Promise(function (resolve, reject) {
    wx.request({
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
    });
  });
}

function uploadMultipart(opts) {
  if (!isApiConfigValid()) {
    return Promise.reject(new Error(apiConfigHint()));
  }
  var onProgress = opts.onProgress;
  return new Promise(function (resolve, reject) {
    var task = wx.uploadFile({
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
    });
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
    var task = wx.downloadFile({
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
    });
    if (onProgress && task && typeof task.onProgressUpdate === "function") {
      task.onProgressUpdate(function (ev) {
        onProgress({ progress: ev.progress });
      });
    }
  });
}

function uploadStrokeExtract(opts) {
  return uploadMultipart({
    url: API_BASE_URL + "/api/mobile/stroke-extract/submit",
    filePath: opts.filePath,
    name: "video",
    formData: {
      detect_mode: opts.detectMode || "combined",
      motion_percentile: String(opts.motionPercentile != null ? opts.motionPercentile : 72),
      vlm_filter: opts.vlmFilter ? "1" : "0",
    },
    onProgress: opts.onProgress,
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
  return uploadMultipart({
    url: API_BASE_URL + "/api/mobile/analyze-video/submit",
    filePath: opts.filePath,
    name: "video",
    formData: {
      perf_mode: opts.perfMode || "eco",
      prompt_profile: opts.promptProfile || "default",
    },
    onProgress: opts.onProgress,
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

function pickChooseVideoLegacy() {
  return new Promise(function (resolve, reject) {
    wx.chooseVideo({
      sourceType: ["album", "camera"],
      compressed: true,
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
  return pickChooseMedia({ sourceType: ["album"] })
    .catch(function (err) {
      if (isUserCancelPick(err)) throw err;
      if (isPrivacyError(err)) {
        return requirePrivacyIfNeeded().then(function () {
          return pickChooseMedia({ sourceType: ["album"] });
        });
      }
      return pickChooseMedia({
        sourceType: ["album", "camera"],
        maxDuration: CHOOSE_VIDEO_MAX_SEC,
      });
    })
    .catch(function (err) {
      if (isUserCancelPick(err)) throw err;
      if (isPrivacyError(err)) {
        return requirePrivacyIfNeeded().then(pickChooseVideoLegacy);
      }
      return pickChooseVideoLegacy();
    });
}

module.exports = {
  isTimeoutError,
  pingHealth,
  uploadStrokeExtract,
  getStrokeTask,
  strokeDownloadUrl,
  downloadStrokeResult,
  uploadAnalyzeSubmit,
  getAnalyzeTask,
  chooseTennisVideo,
  showChooseFail,
};
