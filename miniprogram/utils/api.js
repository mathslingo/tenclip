const {
  API_BASE_URL,
  UPLOAD_TIMEOUT_MS,
  REQUEST_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  isApiConfigValid,
  apiConfigHint,
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
      timeout: 8000,
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
    return new Error("请求超时：视频较大或网络较慢，请检查 API 地址与后端是否已用 0.0.0.0 启动");
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
        var raw = (err && err.errMsg) || "";
        if (raw.indexOf("url not in domain list") !== -1) {
          reject(
            new Error(
              "域名未在白名单：请在 config.js 配置 LOCAL_API_HOST，并在开发者工具勾选「不校验合法域名」"
            )
          );
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

module.exports = {
  isTimeoutError,
  pingHealth,
  uploadStrokeExtract,
  getStrokeTask,
  strokeDownloadUrl,
  downloadStrokeResult,
  uploadAnalyzeSubmit,
  getAnalyzeTask,
};
