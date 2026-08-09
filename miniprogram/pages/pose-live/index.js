const {
  POSE_DETECT_URL,
  POSE_HEALTH_URL,
  LOCAL_DEV,
  REQUEST_TIMEOUT_MS,
} = require("../../utils/config");
const { requirePrivacyIfNeeded } = require("../../utils/api");

const INTERVAL_MS = 450;

Page({
  data: {
    devicePosition: "front",
    running: false,
    camReady: false,
    statusText: "准备摄像头…",
    fpsText: "",
    resultSrc: "",
  },

  _timer: null,
  _busy: false,
  _camCtx: null,
  _privacyOk: false,

  onLoad() {
    this._camCtx = wx.createCameraContext();
    this._ensurePrivacy().then(() => this._checkBackend());
  },

  onUnload() {
    this._stopLoop();
  },

  onHide() {
    this._stopLoop();
    this.setData({ running: false });
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
    this.setData({
      camReady: true,
      statusText: this.data.running ? "检测中…" : "摄像头就绪，点「开始检测」",
    });
  },

  onCamError(e) {
    const msg =
      (e && e.detail && (e.detail.errMsg || e.detail.message)) ||
      "摄像头打开失败";
    this.setData({ statusText: msg, camReady: false });
    wx.showModal({
      title: "无法使用摄像头",
      content:
        String(msg) +
        "\n\n请检查：\n1. 手机系统是否允许微信使用相机\n2. 小程序隐私指引是否声明了摄像头\n3. 请用真机调试（模拟器相机能力有限）",
      showCancel: false,
    });
  },

  _checkBackend() {
    if (!POSE_HEALTH_URL) {
      this.setData({ statusText: "未配置姿态服务地址" });
      return;
    }
    wx.request({
      url: POSE_HEALTH_URL,
      method: "GET",
      timeout: Math.min(REQUEST_TIMEOUT_MS || 30000, 8000),
      success: (res) => {
        const ok = res.statusCode === 200 && res.data && res.data.status === "ok";
        if (ok) {
          const device =
            (res.data.device || "CPU") +
            (res.data.backend ? " · " + res.data.backend : "");
          this.setData({
            statusText: this.data.camReady
              ? "摄像头就绪 · 后端 " + device
              : "后端就绪，等待摄像头…",
          });
        } else {
          this.setData({
            statusText: "姿态服务未就绪，可先预览相机；检测需启动 pose_server",
          });
        }
      },
      fail: () => {
        this.setData({
          statusText:
            "连不上姿态服务（" +
            (LOCAL_DEV ? "请启动 pose_server.py:5000" : "检查 POSE_API_BASE") +
            "）",
        });
      },
    });
  },

  onToggleDevice() {
    const next = this.data.devicePosition === "front" ? "back" : "front";
    this.setData({ devicePosition: next, resultSrc: "" });
  },

  onToggleRun() {
    if (this.data.running) {
      this._stopLoop();
      this.setData({
        running: false,
        statusText: "已停止",
        fpsText: "",
      });
      return;
    }
    const start = () => {
      if (!this.data.camReady) {
        wx.showToast({ title: "摄像头未就绪", icon: "none" });
        return;
      }
      this.setData({ running: true, statusText: "检测中…" });
      this._tick();
      this._timer = setInterval(() => this._tick(), INTERVAL_MS);
    };
    if (!this._privacyOk) {
      this._ensurePrivacy().then(start);
      return;
    }
    start();
  },

  _stopLoop() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    this._busy = false;
  },

  _tick() {
    if (!this.data.running || this._busy || !this._camCtx) return;
    this._busy = true;
    this._camCtx.takePhoto({
      quality: "normal",
      success: (res) => {
        this._uploadFrame(res.tempImagePath);
      },
      fail: (err) => {
        this._busy = false;
        this.setData({
          statusText: "拍照失败：" + ((err && err.errMsg) || "未知错误"),
        });
      },
    });
  },

  _uploadFrame(filePath) {
    const fs = wx.getFileSystemManager();
    fs.readFile({
      filePath: filePath,
      encoding: "base64",
      success: (fileRes) => {
        wx.request({
          url: POSE_DETECT_URL,
          method: "POST",
          timeout: REQUEST_TIMEOUT_MS || 30000,
          header: { "Content-Type": "application/json" },
          data: { image: "data:image/jpeg;base64," + fileRes.data },
          success: (res) => {
            this._busy = false;
            if (res.statusCode !== 200 || !res.data || res.data.error) {
              const err =
                (res.data && res.data.error) || "HTTP " + res.statusCode;
              this.setData({ statusText: "检测失败：" + err });
              return;
            }
            const d = res.data;
            const src = d.image ? "data:image/jpeg;base64," + d.image : "";
            this.setData({
              resultSrc: src || this.data.resultSrc,
              statusText:
                "人数 " +
                (d.num_people || 0) +
                " · 关键点 " +
                ((d.keypoints && d.keypoints.length) || 0),
              fpsText: d.inference_time_ms ? d.inference_time_ms + " ms" : "",
            });
          },
          fail: (err) => {
            this._busy = false;
            this.setData({
              statusText:
                "请求失败：" +
                ((err && err.errMsg) || "网络错误") +
                (LOCAL_DEV ? "（确认 pose_server 已启动）" : ""),
            });
          },
        });
      },
      fail: () => {
        this._busy = false;
        this.setData({ statusText: "读取照片失败" });
      },
    });
  },

  onBack() {
    this._stopLoop();
    wx.navigateBack({
      fail: () => {
        wx.redirectTo({ url: "/pages/pose-detect/index" });
      },
    });
  },
});
