/**
 * RTMpose 实时姿态检测（新版本）
 * 
 * 功能：
 * - 实时摄像头采集
 * - RTMpose 多人检测
 * - FPS 和推理时间显示
 * - 关键点置信度过滤
 * - 检测结果可视化
 */

const {
  RTMPOSE_V2_DETECT_URL,
  RTMPOSE_V2_HEALTH_URL,
  LOCAL_DEV,
  REQUEST_TIMEOUT_MS,
} = require("../../utils/config");
const { requirePrivacyIfNeeded } = require("../../utils/api");

const INTERVAL_MS = 400; // 帧采集间隔 (ms)

Page({
  data: {
    // 摄像头配置
    devicePosition: "front",
    camReady: false,
    
    // 检测状态
    running: false,
    statusText: "准备摄像头…",
    fpsText: "",
    peopleCountText: "",
    keypointCountText: "",
    resultSrc: "",
    
    // 性能监控
    avgInferenceTime: 0,
    peakFps: 0,
    
    // 检测参数
    confidenceThreshold: 0.5,
    showStats: false,
  },

  // 私有成员
  _timer: null,
  _busy: false,
  _camCtx: null,
  _privacyOk: false,
  _frameCount: 0,
  _lastFpsTime: 0,
  _lastInferenceTimes: [], // 用于计算平均推理时间

  // ============ 生命周期 ============

  onLoad() {
    console.log("[RTMpose] Page loaded");
    this._camCtx = wx.createCameraContext();
    this._ensurePrivacy().then(() => this._checkBackend());
  },

  onUnload() {
    console.log("[RTMpose] Page unloaded");
    this._stopLoop();
  },

  onHide() {
    console.log("[RTMpose] Page hidden");
    this._stopLoop();
    this.setData({ running: false });
  },

  // ============ 隐私和后端检查 ============

  _ensurePrivacy() {
    return requirePrivacyIfNeeded()
      .then(() => {
        this._privacyOk = true;
        console.log("[RTMpose] Privacy consent obtained");
      })
      .catch(() => {
        this._privacyOk = false;
        this.setData({ statusText: "需同意隐私后才能使用摄像头" });
        console.warn("[RTMpose] Privacy consent denied");
      });
  },

  _checkBackend() {
    if (!RTMPOSE_V2_HEALTH_URL) {
      this.setData({ statusText: "未配置 RTMpose v2 服务地址" });
      console.error("[RTMpose] RTMPOSE_V2_HEALTH_URL not configured");
      return;
    }

    wx.request({
      url: RTMPOSE_V2_HEALTH_URL,
      method: "GET",
      timeout: Math.min(REQUEST_TIMEOUT_MS || 30000, 8000),
      success: (res) => {
        const ok = res.statusCode === 200 && res.data && res.data.status === "ok";
        if (ok) {
          const modelName = res.data.model_config?.model_name || "RTMpose";
          const device = res.data.gpu_info?.available ? "GPU" : "CPU";
          const statusSuffix = `${modelName} · ${device}`;
          
          this.setData({
            statusText: this.data.camReady
              ? `摄像头就绪 · ${statusSuffix}`
              : `${statusSuffix} · 等待摄像头…`,
          });
          console.log("[RTMpose] Backend check passed:", statusSuffix);
        } else {
          this.setData({
            statusText: "RTMpose v2 服务未就绪",
          });
          console.warn("[RTMpose] Backend not ready:", res.data);
        }
      },
      fail: (err) => {
        this.setData({
          statusText: `连不上 RTMpose 服务${LOCAL_DEV ? "（请启动 pose_server_v2.py）" : ""}`,
        });
        console.error("[RTMpose] Backend health check failed:", err);
      },
    });
  },

  // ============ 摄像头事件 ============

  onCamReady() {
    this.setData({
      camReady: true,
      statusText: this.data.running 
        ? this.data.statusText 
        : "摄像头就绪，点「开始检测」",
    });
    console.log("[RTMpose] Camera ready");
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
    
    console.error("[RTMpose] Camera error:", msg);
  },

  // ============ 用户交互 ============

  onToggleDevice() {
    const next = this.data.devicePosition === "front" ? "back" : "front";
    this.setData({ devicePosition: next, resultSrc: "" });
    console.log("[RTMpose] Switched camera to:", next);
  },

  onToggleRun() {
    if (this.data.running) {
      this._stopLoop();
      this.setData({
        running: false,
        statusText: "已停止检测",
        fpsText: "",
        peopleCountText: "",
        keypointCountText: "",
      });
      console.log("[RTMpose] Detection stopped");
      return;
    }

    const start = () => {
      if (!this.data.camReady) {
        wx.showToast({ title: "摄像头未就绪", icon: "none" });
        return;
      }
      
      this.setData({ 
        running: true, 
        statusText: "检测中…",
        avgInferenceTime: 0,
        peakFps: 0,
      });
      this._frameCount = 0;
      this._lastFpsTime = Date.now();
      this._lastInferenceTimes = [];
      
      this._tick();
      this._timer = setInterval(() => this._tick(), INTERVAL_MS);
      console.log("[RTMpose] Detection started");
    };

    if (!this._privacyOk) {
      this._ensurePrivacy().then(start);
      return;
    }
    start();
  },

  onToggleStats() {
    const show = !this.data.showStats;
    this.setData({ showStats: show });
    console.log("[RTMpose] Stats panel toggled:", show);
  },

  onConfidenceChange(e) {
    const value = parseFloat(e.detail.value);
    this.setData({ confidenceThreshold: value });
    console.log("[RTMpose] Confidence threshold changed to:", value);
  },

  onBack() {
    this._stopLoop();
    wx.navigateBack({
      fail: () => {
        wx.redirectTo({ url: "/pages/pose-detect/index" });
      },
    });
  },

  // ============ 内部循环 ============

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
        console.error("[RTMpose] takePhoto failed:", err);
      },
    });
  },

  _uploadFrame(filePath) {
    const fs = wx.getFileSystemManager();
    
    fs.readFile({
      filePath: filePath,
      encoding: "base64",
      success: (fileRes) => {
        const startTime = Date.now();
        
        wx.request({
          url: RTMPOSE_V2_DETECT_URL,
          method: "POST",
          timeout: REQUEST_TIMEOUT_MS || 30000,
          header: { "Content-Type": "application/json" },
          data: {
            image: "data:image/jpeg;base64," + fileRes.data,
            confidence_threshold: this.data.confidenceThreshold,
            return_visualization: true,
          },
          success: (res) => {
            const inferenceTime = Date.now() - startTime;
            this._busy = false;

            if (res.statusCode !== 200 || !res.data || !res.data.success) {
              const err =
                (res.data && res.data.error) || "HTTP " + res.statusCode;
              this.setData({ 
                statusText: "检测失败：" + err,
                fpsText: "",
              });
              console.error("[RTMpose] Detection API failed:", err, res.data);
              return;
            }

            const data = res.data;
            this._updateDetectionResult(data, inferenceTime);
          },
          fail: (err) => {
            this._busy = false;
            this.setData({
              statusText:
                "请求失败：" +
                ((err && err.errMsg) || "网络错误") +
                (LOCAL_DEV ? "（确认 pose_server_v2.py 已启动）" : ""),
            });
            console.error("[RTMpose] API request failed:", err);
          },
        });
      },
      fail: () => {
        this._busy = false;
        this.setData({ statusText: "读取照片失败" });
        console.error("[RTMpose] Failed to read photo file");
      },
    });
  },

  _updateDetectionResult(data, totalTime) {
    const src = data.image ? "data:image/jpeg;base64," + data.image : "";
    
    // 更新帧计数和 FPS
    this._frameCount++;
    const now = Date.now();
    const elapsed = now - this._lastFpsTime;
    let fps = 0;
    
    if (elapsed >= 1000) {
      fps = Math.round((this._frameCount * 1000) / elapsed);
      this._frameCount = 0;
      this._lastFpsTime = now;
    }
    
    // 更新推理时间统计
    if (data.inference_time_ms) {
      this._lastInferenceTimes.push(data.inference_time_ms);
      if (this._lastInferenceTimes.length > 30) {
        this._lastInferenceTimes.shift();
      }
    }
    
    const avgInferenceTime = this._lastInferenceTimes.length > 0
      ? (this._lastInferenceTimes.reduce((a, b) => a + b, 0) / this._lastInferenceTimes.length).toFixed(1)
      : 0;
    
    // 计算总体 FPS
    const overallFps = totalTime > 0 ? Math.round(1000 / totalTime) : 0;
    const peakFps = Math.max(this.data.peakFps, overallFps);
    
    // 构建统计文本
    let statusLine = `🎯 ${data.num_people} 人`;
    if (data.people && data.people.length > 0) {
      const totalKeypoints = data.people.reduce(
        (sum, p) => sum + (p.keypoint_count || 0),
        0
      );
      statusLine += ` · ${totalKeypoints} 关键点`;
    }
    
    const fpsLine = `${overallFps} FPS · ${data.inference_time_ms}ms`;
    
    this.setData({
      resultSrc: src || this.data.resultSrc,
      statusText: statusLine,
      fpsText: fpsLine,
      peopleCountText: `人数: ${data.num_people}`,
      keypointCountText: data.people
        ? `关键点: ${data.people.reduce((sum, p) => sum + (p.keypoint_count || 0), 0)}`
        : "关键点: 0",
      avgInferenceTime: parseFloat(avgInferenceTime),
      peakFps: peakFps,
    });
  },
});
