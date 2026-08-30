/**
 * 小程序原生 YOLO Pose（实验）
 * camera + wx.createInferenceSession(ONNX) + 本地 letterbox/NMS
 * 模型从 YOLO_POSE_MODEL_URL 下载到 USER_DATA_PATH
 */

const {
  YOLO_POSE_MODEL_URL,
  YOLO_POSE_IMGSZ,
  LOCAL_DEV,
} = require("../../utils/config");
const { requirePrivacyIfNeeded } = require("../../utils/api");
const {
  COCO_EDGES,
  letterboxFromRgba,
  decodePoseOutput,
  normalizeOrtOutput,
} = require("../../utils/yolo_pose_codec");

const MODEL_FILE = "yolo11n-pose.onnx";
const MIN_GAP_MS = 280;
const CONF = 0.25;
const KPT_CONF = 0.3;
const IOU = 0.45;
const MAX_DET = 10;
const INPUT_NAME = "images";
const OUTPUT_NAME = "output0";

Page({
  data: {
    devicePosition: "front",
    camReady: false,
    running: false,
    statusText: "准备中…",
    metricsText: "",
    overlaySrc: "",
  },

  _camCtx: null,
  _frameListener: null,
  _session: null,
  _modelPath: "",
  _busy: false,
  _lastTs: 0,
  _inputBuf: null,
  _workCanvas: null,
  _workCtx: null,
  _privacyOk: false,
  _inputName: INPUT_NAME,
  _outputName: OUTPUT_NAME,

  onLoad() {
    if (typeof wx.createInferenceSession !== "function") {
      this.setData({
        statusText: "当前基础库过低，需 ≥2.30 才支持 ONNX 推理",
      });
      return;
    }
    this._ensurePrivacy().then(() => this._prepareModel());
  },

  onUnload() {
    this._stopRun();
    this._destroySession();
  },

  onHide() {
    if (this.data.running) this._stopRun();
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
    this.setData({ camReady: true });
    if (this._session) {
      this.setData({ statusText: "模型就绪，点「开始检测」" });
    }
  },

  onCamError(e) {
    const msg =
      (e && e.detail && (e.detail.errMsg || e.detail.message)) ||
      "摄像头打开失败";
    this.setData({ statusText: msg, camReady: false });
  },

  onToggleDevice() {
    if (this.data.running) return;
    const next = this.data.devicePosition === "front" ? "back" : "front";
    this._camCtx = null;
    this.setData({
      devicePosition: next,
      camReady: false,
      statusText: "切换摄像头…",
      overlaySrc: "",
    });
  },

  onToggleRun() {
    if (this.data.running) {
      this._stopRun();
      return;
    }
    if (!this._privacyOk) {
      this._ensurePrivacy().then(() => this.onToggleRun());
      return;
    }
    if (!this._session) {
      this.setData({ statusText: "模型未就绪" });
      return;
    }
    if (!this._camCtx) {
      this.setData({ statusText: "摄像头未就绪" });
      return;
    }
    this._startRun();
  },

  onBack() {
    this._stopRun();
    wx.navigateBack({
      fail: () => wx.redirectTo({ url: "/pages/pose-realtime/index" }),
    });
  },

  _modelLocalPath() {
    return wx.env.USER_DATA_PATH + "/" + MODEL_FILE;
  },

  _prepareModel() {
    const path = this._modelLocalPath();
    this._modelPath = path;
    const fs = wx.getFileSystemManager();
    try {
      fs.accessSync(path);
      this.setData({ statusText: "加载本地模型…" });
      this._createSession(path);
      return;
    } catch (e) {}

    if (!YOLO_POSE_MODEL_URL) {
      this.setData({ statusText: "未配置 YOLO_POSE_MODEL_URL" });
      return;
    }

    this.setData({ statusText: "下载模型（约 12MB）…" });
    wx.downloadFile({
      url: YOLO_POSE_MODEL_URL,
      success: (res) => {
        if (res.statusCode !== 200 || !res.tempFilePath) {
          this.setData({
            statusText: "模型下载失败 HTTP " + res.statusCode,
          });
          return;
        }
        try {
          fs.saveFileSync(res.tempFilePath, path);
        } catch (err) {
          // 部分基础库 saveFile 路径受限，直接用临时文件
          this._modelPath = res.tempFilePath;
          this._createSession(this._modelPath);
          return;
        }
        this._createSession(path);
      },
      fail: (err) => {
        this.setData({
          statusText:
            "模型下载失败：" +
            ((err && err.errMsg) || "") +
            (LOCAL_DEV ? "（检查合法域名）" : ""),
        });
      },
    });
  },

  _createSession(modelPath) {
    try {
      this._destroySession();
      const session = wx.createInferenceSession({
        model: modelPath,
        precisionLevel: 2,
        allowNPU: true,
        allowQuantize: false,
        typicalShape: {
          images: [1, 3, YOLO_POSE_IMGSZ || 640, YOLO_POSE_IMGSZ || 640],
        },
      });
      session.onError((err) => {
        console.error("[pose-yolo] session error", err);
        this.setData({
          statusText:
            "模型加载失败：" +
            (err && (err.errMsg || err.message)
              ? err.errMsg || err.message
              : "未知"),
        });
      });
      session.onLoad(() => {
        this._session = session;
        this.setData({
          statusText: this.data.camReady
            ? "模型就绪，点「开始检测」"
            : "模型就绪，等待摄像头…",
        });
      });
    } catch (e) {
      this.setData({
        statusText: "createInferenceSession 异常：" + (e.message || e),
      });
    }
  },

  _destroySession() {
    if (this._session) {
      try {
        this._session.destroy();
      } catch (e) {}
      this._session = null;
    }
  },

  _startRun() {
    this.setData({ running: true, statusText: "检测中…", overlaySrc: "" });
    this._lastTs = 0;
    this._busy = false;

    // 优先 onCameraFrame；失败则 takePhoto 轮询
    try {
      const listener = this._camCtx.onCameraFrame((frame) => {
        this._onFrame(frame);
      });
      listener.start();
      this._frameListener = listener;
    } catch (e) {
      console.warn("[pose-yolo] onCameraFrame unavailable", e);
      this._photoTimer = setInterval(() => this._tickPhoto(), MIN_GAP_MS);
    }
  },

  _stopRun() {
    this.setData({ running: false, statusText: "已停止" });
    if (this._frameListener) {
      try {
        this._frameListener.stop();
      } catch (e) {}
      this._frameListener = null;
    }
    if (this._photoTimer) {
      clearInterval(this._photoTimer);
      this._photoTimer = null;
    }
    this._busy = false;
  },

  _tickPhoto() {
    if (!this.data.running || this._busy || !this._camCtx) return;
    this._busy = true;
    this._camCtx.takePhoto({
      quality: "low",
      success: (res) => {
        this._inferFromPath(res.tempImagePath).finally(() => {
          this._busy = false;
        });
      },
      fail: () => {
        this._busy = false;
      },
    });
  },

  _onFrame(frame) {
    if (!this.data.running || this._busy || !this._session) return;
    const now = Date.now();
    if (now - this._lastTs < MIN_GAP_MS) return;
    this._lastTs = now;
    this._busy = true;

    const w = frame.width;
    const h = frame.height;
    let rgba;
    try {
      rgba = new Uint8Array(frame.data);
    } catch (e) {
      this._busy = false;
      return;
    }

    this._inferRgba(rgba, w, h)
      .catch((err) => {
        console.error("[pose-yolo] infer", err);
        this.setData({
          statusText: "推理失败：" + (err.message || err),
        });
      })
      .finally(() => {
        this._busy = false;
      });
  },

  _ensureWorkCanvas() {
    return new Promise((resolve, reject) => {
      if (this._workCanvas && this._workCtx) {
        resolve();
        return;
      }
      wx.createSelectorQuery()
        .in(this)
        .select("#workCanvas")
        .fields({ node: true, size: true })
        .exec((res) => {
          const node = res && res[0] && res[0].node;
          if (!node) {
            reject(new Error("workCanvas 未就绪"));
            return;
          }
          const dpr = wx.getSystemInfoSync().pixelRatio || 1;
          const imgsz = YOLO_POSE_IMGSZ || 640;
          node.width = imgsz * dpr;
          node.height = imgsz * dpr;
          const ctx = node.getContext("2d");
          ctx.scale(dpr, dpr);
          this._workCanvas = node;
          this._workCtx = ctx;
          resolve();
        });
    });
  },

  _inferFromPath(path) {
    return this._ensureWorkCanvas().then(() => {
      const canvas = this._workCanvas;
      const ctx = this._workCtx;
      const imgsz = YOLO_POSE_IMGSZ || 640;
      return new Promise((resolve, reject) => {
        const img = canvas.createImage();
        img.onload = () => {
          try {
            ctx.clearRect(0, 0, imgsz, imgsz);
            // 先画到临时尺寸再取像素：缩放到 letterbox 前的原图尺寸用 canvas
            const iw = img.width;
            const ih = img.height;
            const off = wx.createOffscreenCanvas
              ? wx.createOffscreenCanvas({ type: "2d", width: iw, height: ih })
              : null;
            let rgba;
            let sw = iw;
            let sh = ih;
            if (off) {
              const octx = off.getContext("2d");
              octx.drawImage(img, 0, 0);
              const id = octx.getImageData(0, 0, iw, ih);
              rgba = id.data;
            } else {
              // 降级：直接缩到 imgsz 再读（略损 letterbox 精度）
              ctx.drawImage(img, 0, 0, imgsz, imgsz);
              const id = ctx.getImageData(0, 0, imgsz, imgsz);
              rgba = id.data;
              sw = imgsz;
              sh = imgsz;
            }
            this._inferRgba(rgba, sw, sh).then(resolve).catch(reject);
          } catch (e) {
            reject(e);
          }
        };
        img.onerror = () => reject(new Error("图片加载失败"));
        img.src = path;
      });
    });
  },

  _inferRgba(rgba, w, h) {
    const imgsz = YOLO_POSE_IMGSZ || 640;
    const boxed = letterboxFromRgba(rgba, w, h, imgsz, this._inputBuf);
    this._inputBuf = boxed.tensor;

    const feeds = {};
    feeds[this._inputName] = {
      type: "float32",
      data: boxed.tensor.buffer.slice(
        boxed.tensor.byteOffset,
        boxed.tensor.byteOffset + boxed.tensor.byteLength
      ),
      shape: [1, 3, imgsz, imgsz],
    };

    const t0 = Date.now();
    return this._session.run(feeds).then((res) => {
      const ms = Date.now() - t0;
      const raw =
        res[this._outputName] ||
        res.output0 ||
        res[Object.keys(res || {})[0]];
      const norm = normalizeOrtOutput(raw);
      const dets = decodePoseOutput(
        norm.data,
        norm.dims,
        boxed.meta,
        CONF,
        IOU,
        MAX_DET
      );
      return this._renderOverlay(rgba, w, h, dets).then(() => {
        this.setData({
          statusText: "检测完成：" + dets.length + " 人",
          metricsText: "推理 " + ms + "ms · 原生 ONNX",
        });
      });
    });
  },

  _renderOverlay(rgba, w, h, dets) {
    return this._ensureWorkCanvas().then(() => {
      const canvas = this._workCanvas;
      const ctx = this._workCtx;
      // 用离屏按源分辨率画骨架再导出
      const outW = Math.min(w, 720);
      const scale = outW / w;
      const outH = Math.round(h * scale);

      const paint = (c, cctx, cw, ch, sx) => {
        const imgData = cctx.createImageData(cw, ch);
        // 最近邻缩略原帧
        for (var y = 0; y < ch; y++) {
          var sy = Math.min(h - 1, Math.floor(y / sx));
          for (var x = 0; x < cw; x++) {
            var sx0 = Math.min(w - 1, Math.floor(x / sx));
            var si = (sy * w + sx0) * 4;
            var di = (y * cw + x) * 4;
            imgData.data[di] = rgba[si];
            imgData.data[di + 1] = rgba[si + 1];
            imgData.data[di + 2] = rgba[si + 2];
            imgData.data[di + 3] = 255;
          }
        }
        cctx.putImageData(imgData, 0, 0);

        dets.forEach((d) => {
          const x1 = d.x1 * sx;
          const y1 = d.y1 * sx;
          const bw = (d.x2 - d.x1) * sx;
          const bh = (d.y2 - d.y1) * sx;
          cctx.strokeStyle = "#00ff00";
          cctx.lineWidth = 2;
          cctx.strokeRect(x1, y1, bw, bh);
          cctx.fillStyle = "#00ff00";
          cctx.font = "14px sans-serif";
          cctx.fillText(
            "person " + Math.round(d.score * 100) + "%",
            x1,
            Math.max(12, y1 - 4)
          );
          cctx.strokeStyle = "#00e5ff";
          COCO_EDGES.forEach((ab) => {
            const pa = d.kpts[ab[0]];
            const pb = d.kpts[ab[1]];
            if (!pa || !pb || pa.conf < KPT_CONF || pb.conf < KPT_CONF) return;
            cctx.beginPath();
            cctx.moveTo(pa.x * sx, pa.y * sx);
            cctx.lineTo(pb.x * sx, pb.y * sx);
            cctx.stroke();
          });
          d.kpts.forEach((p) => {
            if (p.conf < KPT_CONF) return;
            cctx.fillStyle = "#ff0000";
            cctx.beginPath();
            cctx.arc(p.x * sx, p.y * sx, 3, 0, Math.PI * 2);
            cctx.fill();
          });
        });
      };

      // 复用 work canvas：临时改尺寸画完再导出
      const dpr = 1;
      canvas.width = outW * dpr;
      canvas.height = outH * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      paint(canvas, ctx, outW, outH, scale);

      return new Promise((resolve) => {
        wx.canvasToTempFilePath({
          canvas: canvas,
          fileType: "jpg",
          quality: 0.7,
          success: (r) => {
            this.setData({ overlaySrc: r.tempFilePath });
            resolve();
          },
          fail: () => resolve(),
        });
      });
    });
  },
});
