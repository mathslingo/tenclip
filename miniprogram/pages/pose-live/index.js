const {
  POSE_ANALYZE_VIDEO_URL,
  POSE_ANALYZE_STATUS_URL,
  POSE_ANALYZE_FILE_URL,
  LOCAL_DEV,
  REQUEST_TIMEOUT_MS,
  UPLOAD_TIMEOUT_MS,
} = require("../../utils/config");
const { requirePrivacyIfNeeded } = require("../../utils/api");

const MAX_RECORD_SEC = 8;

Page({
  data: {
    devicePosition: "front",
    camReady: false,
    recording: false,
    busy: false,
    showResult: false,
    resultVideo: "",
    statusText: "准备摄像头…",
    timerText: "0s",
    progressText: "",
  },

  _camCtx: null,
  _privacyOk: false,
  _tickTimer: null,
  _pollTimer: null,
  _elapsed: 0,
  _taskId: "",

  onLoad() {
    this._ensurePrivacy();
  },

  onUnload() {
    this._clearTimers();
    if (this.data.recording) {
      try {
        this._camCtx && this._camCtx.stopRecord({ complete: () => {} });
      } catch (e) {}
    }
  },

  onHide() {
    if (this.data.recording) {
      this.onToggleRecord();
    }
  },

  _ensurePrivacy() {
    return requirePrivacyIfNeeded()
      .then(() => {
        this._privacyOk = true;
      })
      .catch(() => {
        this._privacyOk = false;
        this.setData({ statusText: "需同意隐私后才能使用摄像头" });
      });
  },

  onCamReady() {
    this._camCtx = wx.createCameraContext();
    this.setData({
      camReady: true,
      statusText: "摄像头就绪，点「开始录制」",
    });
  },

  onCamError(e) {
    const msg =
      (e && e.detail && (e.detail.errMsg || e.detail.message)) ||
      "摄像头打开失败";
    this.setData({ statusText: msg, camReady: false });
  },

  onToggleDevice() {
    if (this.data.recording || this.data.busy) return;
    const next = this.data.devicePosition === "front" ? "back" : "front";
    this._camCtx = null;
    this.setData({ devicePosition: next, camReady: false, statusText: "切换摄像头…" });
  },

  _ensureCameraAuth() {
    return new Promise((resolve, reject) => {
      wx.getSetting({
        success: (s) => {
          if (s.authSetting && s.authSetting["scope.camera"] === true) {
            resolve();
            return;
          }
          wx.authorize({
            scope: "scope.camera",
            success: () => resolve(),
            fail: () => {
              wx.showModal({
                title: "需要相机权限",
                content: "请在设置中允许使用摄像头，才能录制动作。",
                confirmText: "去设置",
                success: (m) => {
                  if (m.confirm) wx.openSetting({});
                },
              });
              reject(new Error("no camera permission"));
            },
          });
        },
        fail: () => resolve(),
      });
    });
  },

  onChooseVideo() {
    if (this.data.recording || this.data.busy) return;
    const pick = () => {
      wx.chooseVideo({
        sourceType: ["camera", "album"],
        camera: this.data.devicePosition === "front" ? "front" : "back",
        maxDuration: MAX_RECORD_SEC,
        compressed: true,
        success: (res) => this._onRecordFile(res.tempFilePath),
        fail: (err) => {
          this.setData({
            statusText: "未选择视频：" + ((err && err.errMsg) || ""),
          });
        },
      });
    };
    if (!this._privacyOk) {
      this._ensurePrivacy().then(pick);
      return;
    }
    pick();
  },

  onToggleRecord() {
    if (this.data.busy) return;
    if (this.data.recording) {
      this._stopRecord();
      return;
    }
    const start = () => {
      if (!this.data.camReady || !this._camCtx) {
        this.onChooseVideo();
        return;
      }
      this._elapsed = 0;
      this.setData({
        recording: true,
        statusText: "录制中，最多 8 秒",
        timerText: "0s",
        progressText: "",
      });
      this._camCtx.startRecord({
        timeout: MAX_RECORD_SEC,
        timeoutCallback: (res) => {
          this._onRecordFile(res && res.tempVideoPath);
        },
        success: () => {
          this._tickTimer = setInterval(() => {
            this._elapsed += 1;
            this.setData({ timerText: this._elapsed + "s" });
            if (this._elapsed >= MAX_RECORD_SEC) {
              this._stopRecord();
            }
          }, 1000);
        },
        fail: (err) => {
          const msg = (err && err.errMsg) || "";
          this.setData({ recording: false });
          wx.showModal({
            title: "页内录制不可用",
            content:
              msg +
              "\n\n开发者工具通常不支持页内录像。请用真机，或点「系统相机」拍摄。",
            confirmText: "系统相机",
            success: (m) => {
              if (m.confirm) this.onChooseVideo();
            },
          });
        },
      });
    };
    const run = () => this._ensureCameraAuth().then(start).catch(() => {});
    if (!this._privacyOk) {
      this._ensurePrivacy().then(run);
      return;
    }
    run();
  },

  _stopRecord() {
    if (!this.data.recording) return;
    this._clearTick();
    this.setData({ recording: false, busy: true, statusText: "正在保存…" });
    this._camCtx.stopRecord({
      success: (res) => this._onRecordFile(res.tempVideoPath),
      fail: (err) => {
        this.setData({
          busy: false,
          statusText: "停止录制失败：" + ((err && err.errMsg) || ""),
        });
      },
    });
  },

  _onRecordFile(filePath) {
    this._clearTick();
    this.setData({ recording: false });
    if (!filePath) {
      this.setData({ busy: false, statusText: "没有录到视频，请重试" });
      return;
    }
    if (!POSE_ANALYZE_VIDEO_URL) {
      this.setData({ busy: false, statusText: "未配置姿态服务地址" });
      return;
    }
    this.setData({ busy: true, statusText: "上传中…", progressText: "" });
    wx.uploadFile({
      url: POSE_ANALYZE_VIDEO_URL,
      filePath: filePath,
      name: "video",
      timeout: UPLOAD_TIMEOUT_MS || 600000,
      success: (res) => {
        let body = {};
        try {
          body = JSON.parse(res.data || "{}");
        } catch (e) {
          body = {};
        }
        if ((res.statusCode !== 200 && res.statusCode !== 202) || !body.task_id) {
          this.setData({
            busy: false,
            statusText:
              "上传失败：" + (body.error || "HTTP " + res.statusCode),
          });
          return;
        }
        this._taskId = body.task_id;
        this.setData({ statusText: "分析中…", progressText: "排队" });
        this._pollStatus();
      },
      fail: (err) => {
        this.setData({
          busy: false,
          statusText:
            "上传失败：" +
            ((err && err.errMsg) || "网络错误") +
            (LOCAL_DEV ? "（请确认 pose_server_v2 已启动）" : ""),
        });
      },
    });
  },

  _pollStatus() {
    this._clearPoll();
    const tick = () => {
      wx.request({
        url: POSE_ANALYZE_STATUS_URL,
        data: { id: this._taskId },
        timeout: REQUEST_TIMEOUT_MS || 30000,
        success: (res) => {
          const d = res.data || {};
          if (res.statusCode !== 200) {
            this.setData({
              busy: false,
              statusText: "查询失败：" + (d.error || res.statusCode),
            });
            this._clearPoll();
            return;
          }
          const pct = Math.round((d.progress || 0) * 100);
          this.setData({
            statusText: d.message || "分析中…",
            progressText: pct + "%",
          });
          if (d.status === "succeeded") {
            this._clearPoll();
            this._downloadResult();
          } else if (d.status === "failed") {
            this._clearPoll();
            this.setData({
              busy: false,
              statusText: "分析失败：" + (d.error || "未知错误"),
              progressText: "",
            });
          }
        },
        fail: () => {
          this._clearPoll();
          this.setData({ busy: false, statusText: "无法查询分析进度" });
        },
      });
    };
    tick();
    this._pollTimer = setInterval(tick, 1500);
  },

  _downloadResult() {
    this.setData({ statusText: "下载回放…", progressText: "100%" });
    wx.downloadFile({
      url: POSE_ANALYZE_FILE_URL + "?id=" + encodeURIComponent(this._taskId),
      timeout: UPLOAD_TIMEOUT_MS || 600000,
      success: (res) => {
        if (res.statusCode !== 200 || !res.tempFilePath) {
          this.setData({ busy: false, statusText: "回放下载失败" });
          return;
        }
        this.setData({
          busy: false,
          showResult: true,
          resultVideo: res.tempFilePath,
          statusText: "骨架回放",
          progressText: "",
        });
      },
      fail: () => {
        this.setData({ busy: false, statusText: "回放下载失败" });
      },
    });
  },

  onRetake() {
    this._taskId = "";
    this.setData({
      showResult: false,
      resultVideo: "",
      busy: false,
      recording: false,
      statusText: this.data.camReady ? "摄像头就绪，点「开始录制」" : "准备摄像头…",
      progressText: "",
      timerText: "0s",
    });
  },

  onBack() {
    this._clearTimers();
    wx.navigateBack({
      fail: () => {
        wx.redirectTo({ url: "/pages/pose-detect/index" });
      },
    });
  },

  _clearTick() {
    if (this._tickTimer) {
      clearInterval(this._tickTimer);
      this._tickTimer = null;
    }
  },

  _clearPoll() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  },

  _clearTimers() {
    this._clearTick();
    this._clearPoll();
  },
});
