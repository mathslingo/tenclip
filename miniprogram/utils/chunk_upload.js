const {
  API_BASE_URL,
  UPLOAD_TIMEOUT_MS,
  isApiConfigValid,
  apiConfigHint,
  domainWhitelistHint,
  isDomainListError,
} = require("./config");

const CHUNK_SIZE_BYTES = 2 * 1024 * 1024;

function basename(filePath) {
  var p = String(filePath || "");
  var i = Math.max(p.lastIndexOf("/"), p.lastIndexOf("\\"));
  return i >= 0 ? p.slice(i + 1) : p || "video.mp4";
}

function parseApiDetail(body, fallback) {
  if (!body) return fallback;
  if (typeof body === "string") return body;
  if (body.detail) {
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  }
  if (body.message) return String(body.message);
  return fallback;
}

function normalizeError(err, fallback) {
  var raw = (err && err.errMsg) || (err && err.message) || "";
  if (err && err.message) return err;
  if (raw) return new Error(raw);
  return new Error(fallback || "网络错误");
}

function wxCronetCompatOpts() {
  return {
    enableHttp2: false,
    enableQuic: false,
    enableHttpDNS: false,
  };
}

function requestForm(url, data) {
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

function requestBinary(method, url, data) {
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

function readFileChunk(filePath, position, length) {
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

function isUploadRetryableError(err) {
  var msg = String((err && err.message) || (err && err.errMsg) || "").toLowerCase();
  return (
    msg.indexOf("timeout") !== -1 ||
    msg.indexOf("network") !== -1 ||
    msg.indexOf("连接") !== -1 ||
    msg.indexOf("connection") !== -1 ||
    msg.indexOf("reset") !== -1 ||
    msg.indexOf("interrupt") !== -1
  );
}

function uploadChunkWithRetry(sessionId, chunkIndex, buffer, onRetry, maxAttempts) {
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
    return requestBinary("PUT", url, buffer).catch(function (err) {
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
    filename: basename(filePath),
    total_chunks: String(totalChunks),
    chunk_size: String(CHUNK_SIZE_BYTES),
  });

  return requestForm(API_BASE_URL + "/api/mobile/upload-sessions", initData).then(function (
    session
  ) {
    var sessionId = session.session_id;
    var chunkSize = session.chunk_size || CHUNK_SIZE_BYTES;
    var chunks = session.total_chunks || totalChunks;
    var index = 0;

    function next() {
      if (index >= chunks) {
        return requestForm(
          API_BASE_URL + "/api/mobile/upload-sessions/" + sessionId + "/complete",
          {}
        );
      }
      var offset = index * chunkSize;
      var length = Math.min(chunkSize, fileSize - offset);
      return readFileChunk(filePath, offset, length)
        .then(function (buffer) {
          return uploadChunkWithRetry(sessionId, index, buffer, onRetry);
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
  });
}

module.exports = {
  CHUNK_SIZE_BYTES,
  chunkVideoUpload,
};
