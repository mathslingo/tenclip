/**
 * YOLO Pose + Tennis · ONNX Runtime Web
 * Pose: [1, 56, N] · Detect: [1, 84, N] (COCO; class 32 = sports ball)
 */

const COCO_EDGES = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12], [11, 13], [13, 15],
  [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4], [0, 5], [0, 6],
];

/** COCO sports ball */
const SPORTS_BALL_CLS = 32;

const qs = new URLSearchParams(location.search);
const cfg = {
  modelUrl: qs.get("model") || "./models/yolo11n-pose.onnx",
  tennisModelUrl: qs.get("tennisModel") || "./models/yolo11n-tennis.onnx",
  imgsz: Number(qs.get("imgsz") || 640),
  webgpu: qs.get("webgpu") !== "0",
  confThresh: Number(qs.get("conf") || 0.25),
  tennisConf: Number(qs.get("tennisConf") || 0.2),
  kptThresh: 0.3,
  iouThresh: 0.45,
  maxFps: 30,
  maxDet: 20,
  maxTennis: 3,
  testImageUrl: "./assets/bus.jpg",
  tennisSampleUrl: "./assets/tennis-sample.jpg",
  idbName: "tenclip-yolo-pose",
  idbStore: "models",
  idbKey: "yolo11n-pose.onnx",
  tennisIdbKey: "yolo11n-tennis.onnx",
};

const els = {
  video: document.getElementById("video"),
  canvas: document.getElementById("canvas"),
  camBtn: document.getElementById("camBtn"),
  pickBtn: document.getElementById("pickBtn"),
  busBtn: document.getElementById("busBtn"),
  tennisBtn: document.getElementById("tennisBtn"),
  tennisSampleBtn: document.getElementById("tennisSampleBtn"),
  fileInput: document.getElementById("fileInput"),
  status: document.getElementById("status"),
  metrics: document.getElementById("metrics"),
};

let session = null;
let tennisSession = null;
let poseInputName = "images";
let tennisInputName = "images";
let tennisEnabled = false;
let tennisMode = "off"; // off | onnx | hsv
let backendName = "wasm";
let camRunning = false;
let stream = null;
let rafId = 0;
let lastInferTs = 0;
let inferBusy = false;
let inputBuf = null;
const letterboxCanvas = document.createElement("canvas");
const letterboxCtx = letterboxCanvas.getContext("2d", { willReadFrequently: true });
const sourceCanvas = document.createElement("canvas");
const sourceCtx = sourceCanvas.getContext("2d", { willReadFrequently: true });
const ballTracker = createBallTracker({ maxMiss: 12, matchPx: 90, smooth: 0.55 });

function setStatus(msg) {
  els.status.textContent = msg;
}

function setMetrics(info) {
  if (!info) {
    els.metrics.textContent = "";
    return;
  }
  var parts = [
    "persons: " + (info.persons || 0),
    "tennis: " + (info.tennis || 0),
  ];
  if (info.distM != null && info.tennis > 0) {
    parts.push("轨迹 " + info.distM.toFixed(2) + "m");
  }
  if (info.speedKmh != null && info.tennis > 0) {
    parts.push("估速 " + Math.round(info.speedKmh) + " km/h");
  }
  if (info.poseMs != null) parts.push("姿态 " + Math.round(info.poseMs) + "ms");
  if (info.tennisMs != null && tennisEnabled) {
    parts.push("网球 " + Math.round(info.tennisMs) + "ms");
  }
  if (info.totalMs != null) {
    parts.push(
      "整帧 " +
        Math.round(info.totalMs) +
        "ms (~" +
        Math.max(1, Math.round(1000 / Math.max(info.totalMs, 1))) +
        " FPS)"
    );
  }
  if (info.tennisMode) parts.push("[" + info.tennisMode + "]");
  parts.push("[" + backendName + "]");
  els.metrics.textContent = parts.join(" | ");
}

function syncTennisBtn() {
  if (!els.tennisBtn) return;
  if (tennisEnabled) {
    els.tennisBtn.textContent =
      tennisMode === "hsv" ? "网球：HSV" : "网球已开启";
    els.tennisBtn.className = "tennis-on";
  } else {
    els.tennisBtn.textContent = "网球：关";
    els.tennisBtn.className = "tennis-off";
  }
}

function openIdb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(cfg.idbName, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(cfg.idbStore)) {
        db.createObjectStore(cfg.idbStore);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(key) {
  const db = await openIdb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(cfg.idbStore, "readonly");
    const req = tx.objectStore(cfg.idbStore).get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

async function idbPut(key, value) {
  const db = await openIdb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(cfg.idbStore, "readwrite");
    tx.objectStore(cfg.idbStore).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function fetchModelBuffer(url, idbKey) {
  const cacheKey = idbKey + "@" + url + "@" + cfg.imgsz;
  try {
    const cached = await idbGet(cacheKey);
    if (cached instanceof ArrayBuffer && cached.byteLength > 1000) {
      return cached;
    }
  } catch (_) {}

  setStatus("下载模型 " + url + " …");
  const res = await fetch(url);
  if (!res.ok) throw new Error("模型 HTTP " + res.status + " · " + url);
  const buf = await res.arrayBuffer();
  try {
    await idbPut(cacheKey, buf);
  } catch (_) {}
  return buf;
}

function ensureOrt() {
  if (!window.ort) throw new Error("onnxruntime-web 未加载");
  ort.env.wasm = ort.env.wasm || {};
  ort.env.wasm.wasmPaths =
    "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
  // 多线程依赖 SharedArrayBuffer，只有跨源隔离（Nginx 发 COOP/COEP）时可用
  ort.env.wasm.numThreads = self.crossOriginIsolated
    ? Math.max(1, Math.min(4, navigator.hardwareConcurrency || 1))
    : 1;
  ort.env.wasm.simd = true;
}

async function createSession(buf) {
  if (cfg.webgpu && navigator.gpu) {
    try {
      const s = await ort.InferenceSession.create(buf, {
        executionProviders: ["webgpu"],
        graphOptimizationLevel: "all",
      });
      backendName = "webgpu";
      return s;
    } catch (e) {
      console.warn("webgpu 不可用，回退 wasm", e);
    }
  }
  const s = await ort.InferenceSession.create(buf, {
    executionProviders: ["wasm"],
    graphOptimizationLevel: "all",
  });
  const n = ort.env.wasm.numThreads || 1;
  backendName = n > 1 ? "wasm x" + n : "wasm";
  return s;
}

function letterbox(srcCanvas, imgsz) {
  const iw = srcCanvas.width;
  const ih = srcCanvas.height;
  const scale = Math.min(imgsz / iw, imgsz / ih);
  const nw = Math.round(iw * scale);
  const nh = Math.round(ih * scale);
  const left = Math.floor((imgsz - nw) / 2);
  const top = Math.floor((imgsz - nh) / 2);

  if (letterboxCanvas.width !== imgsz || letterboxCanvas.height !== imgsz) {
    letterboxCanvas.width = imgsz;
    letterboxCanvas.height = imgsz;
  }
  letterboxCtx.fillStyle = "#000";
  letterboxCtx.fillRect(0, 0, imgsz, imgsz);
  letterboxCtx.drawImage(srcCanvas, 0, 0, iw, ih, left, top, nw, nh);

  const { data } = letterboxCtx.getImageData(0, 0, imgsz, imgsz);
  const plane = imgsz * imgsz;
  // 复用输入缓冲，避免每帧新分配 ~5MB 触发 GC
  if (!inputBuf || inputBuf.length !== 3 * plane) {
    inputBuf = new Float32Array(3 * plane);
  }
  const float = inputBuf;
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    float[p] = data[i] / 255;
    float[p + plane] = data[i + 1] / 255;
    float[p + plane * 2] = data[i + 2] / 255;
  }
  return { tensor: float, meta: { scale, padX: left, padY: top, iw, ih } };
}

function iou(a, b) {
  const x1 = Math.max(a.x1, b.x1);
  const y1 = Math.max(a.y1, b.y1);
  const x2 = Math.min(a.x2, b.x2);
  const y2 = Math.min(a.y2, b.y2);
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  const ua =
    (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter;
  return ua <= 0 ? 0 : inter / ua;
}

function nms(dets, maxKeep) {
  dets.sort((a, b) => b.score - a.score);
  const keep = [];
  const limit = maxKeep != null ? maxKeep : cfg.maxDet;
  for (const d of dets) {
    if (keep.every((k) => iou(d, k) <= cfg.iouThresh)) keep.push(d);
    if (keep.length >= limit) break;
  }
  return keep;
}

function decodePose(out, meta) {
  const dims = out.dims;
  const data = out.data;
  let num;
  let rows;

  if (dims.length === 3 && dims[1] === 56) {
    num = dims[2];
    rows = new Float32Array(num * 56);
    for (let i = 0; i < num; i++) {
      for (let c = 0; c < 56; c++) rows[i * 56 + c] = data[c * num + i];
    }
  } else if (dims.length === 3 && dims[2] === 56) {
    num = dims[1];
    rows = data instanceof Float32Array ? data : new Float32Array(data);
  } else {
    throw new Error("意外 pose 输出形状: " + dims.join("x"));
  }

  const { scale, padX, padY } = meta;
  const dets = [];
  for (let i = 0; i < num; i++) {
    const o = i * 56;
    const score = rows[o + 4];
    if (score < cfg.confThresh) continue;
    const cx = rows[o];
    const cy = rows[o + 1];
    const w = rows[o + 2];
    const h = rows[o + 3];
    const kpts = [];
    for (let k = 0; k < 17; k++) {
      const base = o + 5 + k * 3;
      kpts.push({
        x: (rows[base] - padX) / scale,
        y: (rows[base + 1] - padY) / scale,
        conf: rows[base + 2],
      });
    }
    dets.push({
      x1: (cx - w / 2 - padX) / scale,
      y1: (cy - h / 2 - padY) / scale,
      x2: (cx + w / 2 - padX) / scale,
      y2: (cy + h / 2 - padY) / scale,
      score,
      kpts,
    });
  }
  return nms(dets);
}

/** YOLO detect COCO: [1, 84, N] or [1, N, 84] */
function decodeDetectSportsBall(out, meta) {
  const dims = out.dims;
  const data = out.data;
  let num;
  let channels;
  let get;

  if (dims.length === 3 && dims[1] >= 84 && dims[1] <= 144) {
    channels = dims[1];
    num = dims[2];
    get = (c, i) => data[c * num + i];
  } else if (dims.length === 3 && dims[2] >= 84 && dims[2] <= 144) {
    num = dims[1];
    channels = dims[2];
    get = (c, i) => data[i * channels + c];
  } else {
    throw new Error("意外 detect 输出形状: " + dims.join("x"));
  }

  const clsCount = channels - 4;
  if (SPORTS_BALL_CLS >= clsCount) {
    throw new Error("输出类别数不足，无法取 sports ball");
  }

  const { scale, padX, padY } = meta;
  const dets = [];
  for (let i = 0; i < num; i++) {
    const score = get(4 + SPORTS_BALL_CLS, i);
    if (score < cfg.tennisConf) continue;
    const cx = get(0, i);
    const cy = get(1, i);
    const w = get(2, i);
    const h = get(3, i);
    dets.push({
      x1: (cx - w / 2 - padX) / scale,
      y1: (cy - h / 2 - padY) / scale,
      x2: (cx + w / 2 - padX) / scale,
      y2: (cy + h / 2 - padY) / scale,
      score,
    });
  }
  return nms(dets, cfg.maxTennis);
}

/** HSV yellow-green blob fallback (no ONNX) */
function detectTennisHsv(srcCanvas) {
  const w = srcCanvas.width;
  const h = srcCanvas.height;
  const ctx = srcCanvas.getContext("2d", { willReadFrequently: true });
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  const mask = new Uint8Array(w * h);
  let count = 0;

  for (let i = 0, p = 0; i < d.length; i += 4, p++) {
    const r = d[i] / 255;
    const g = d[i + 1] / 255;
    const b = d[i + 2] / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const v = max;
    const s = max === 0 ? 0 : (max - min) / max;
    let hue = 0;
    if (max !== min) {
      if (max === r) hue = ((g - b) / (max - min)) * 60;
      else if (max === g) hue = (2 + (b - r) / (max - min)) * 60;
      else hue = (4 + (r - g) / (max - min)) * 60;
      if (hue < 0) hue += 360;
    }
    // tennis yellow-green
    if (hue >= 35 && hue <= 95 && s >= 0.35 && v >= 0.35) {
      mask[p] = 1;
      count++;
    }
  }

  if (count < 8) return [];

  // connected components (4-neigh), keep largest few blob bboxes
  const visited = new Uint8Array(w * h);
  const blobs = [];
  const stack = [];

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const start = y * w + x;
      if (!mask[start] || visited[start]) continue;
      let minX = x;
      let maxX = x;
      let minY = y;
      let maxY = y;
      let area = 0;
      stack.length = 0;
      stack.push(start);
      visited[start] = 1;
      while (stack.length) {
        const idx = stack.pop();
        const cx = idx % w;
        const cy = (idx / w) | 0;
        area++;
        if (cx < minX) minX = cx;
        if (cx > maxX) maxX = cx;
        if (cy < minY) minY = cy;
        if (cy > maxY) maxY = cy;
        const neigh = [idx - 1, idx + 1, idx - w, idx + w];
        for (const n of neigh) {
          if (n < 0 || n >= mask.length) continue;
          if (!mask[n] || visited[n]) continue;
          visited[n] = 1;
          stack.push(n);
        }
      }
      const bw = maxX - minX + 1;
      const bh = maxY - minY + 1;
      if (area < 12 || bw < 4 || bh < 4) continue;
      if (bw > w * 0.35 || bh > h * 0.35) continue; // too big = court paint
      const aspect = bw / bh;
      if (aspect < 0.45 || aspect > 2.2) continue;
      blobs.push({
        x1: minX,
        y1: minY,
        x2: maxX + 1,
        y2: maxY + 1,
        score: Math.min(0.95, 0.4 + area / 800),
        area: area,
      });
    }
  }

  blobs.sort((a, b) => b.area - a.area);
  return blobs.slice(0, cfg.maxTennis).map((b) => ({
    x1: b.x1,
    y1: b.y1,
    x2: b.x2,
    y2: b.y2,
    score: b.score,
  }));
}

function pickPrimaryBall(balls) {
  if (!balls || !balls.length) return null;
  return balls.slice().sort((a, b) => b.score - a.score)[0];
}

function draw(source, persons, balls, trailState) {
  const canvas = els.canvas;
  const w = source.width;
  const h = source.height;
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.drawImage(source, 0, 0);
  const lw = Math.max(2, Math.round(Math.min(w, h) / 320));

  for (const d of persons) {
    const bw = d.x2 - d.x1;
    const bh = d.y2 - d.y1;
    ctx.strokeStyle = "#00ff00";
    ctx.lineWidth = lw;
    ctx.strokeRect(d.x1, d.y1, bw, bh);

    const label = "person " + Math.round(d.score * 100) + "%";
    ctx.font = "bold 14px -apple-system, sans-serif";
    const tw = ctx.measureText(label).width + 8;
    const th = 18;
    const ly = Math.max(0, d.y1 - th);
    ctx.fillStyle = "#00ff00";
    ctx.fillRect(d.x1, ly, tw, th);
    ctx.fillStyle = "#000";
    ctx.fillText(label, d.x1 + 4, ly + 13);

    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 2;
    for (const [a, b] of COCO_EDGES) {
      const pa = d.kpts[a];
      const pb = d.kpts[b];
      if (!pa || !pb || pa.conf < cfg.kptThresh || pb.conf < cfg.kptThresh) continue;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
    }
    for (const p of d.kpts) {
      if (p.conf < cfg.kptThresh) continue;
      ctx.fillStyle = "#ff0000";
      ctx.beginPath();
      ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (trailState && trailState.trail && trailState.trail.length > 1) {
    ctx.strokeStyle = "#ffb020";
    ctx.lineWidth = 2;
    ctx.beginPath();
    trailState.trail.forEach((p, i) => {
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.stroke();
  }

  for (const d of balls || []) {
    const bw = d.x2 - d.x1;
    const bh = d.y2 - d.y1;
    ctx.strokeStyle = "#f5e000";
    ctx.lineWidth = lw;
    ctx.strokeRect(d.x1, d.y1, bw, bh);
    const label = "tennis " + Math.round(d.score * 100) + "%";
    ctx.font = "bold 14px -apple-system, sans-serif";
    const tw = ctx.measureText(label).width + 8;
    const th = 18;
    const ly = Math.max(0, d.y1 - th);
    ctx.fillStyle = "#f5e000";
    ctx.fillRect(d.x1, ly, tw, th);
    ctx.fillStyle = "#111";
    ctx.fillText(label, d.x1 + 4, ly + 13);

    const cx = (d.x1 + d.x2) / 2;
    const cy = (d.y1 + d.y2) / 2;
    ctx.strokeStyle = "#3b82f6";
    ctx.beginPath();
    ctx.moveTo(cx - 18, cy);
    ctx.lineTo(cx + 18, cy);
    ctx.stroke();
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.fill();
  }
}

async function loadPoseModel() {
  if (session) return;
  ensureOrt();
  setStatus("加载姿态模型…");
  const buf = await fetchModelBuffer(cfg.modelUrl, cfg.idbKey);
  setStatus("创建姿态推理会话…");
  session = await createSession(buf);
  poseInputName = session.inputNames[0] || "images";
  setStatus("姿态模型就绪。可开摄像头 / 图片；点「网球」加载球检测");
  setMetrics(null);
}

async function loadTennisModel() {
  if (tennisSession) {
    tennisMode = "onnx";
    return true;
  }
  ensureOrt();
  try {
    const t0 = performance.now();
    setStatus("加载网球检测模型…");
    const buf = await fetchModelBuffer(cfg.tennisModelUrl, cfg.tennisIdbKey);
    tennisSession = await createSession(buf);
    tennisInputName = tennisSession.inputNames[0] || "images";
    tennisMode = "onnx";
    setStatus(
      "网球模型就绪（" +
        ((performance.now() - t0) / 1000).toFixed(1) +
        "s）。再点一次可关闭。"
    );
    return true;
  } catch (e) {
    console.warn("tennis onnx unavailable, HSV fallback", e);
    tennisSession = null;
    tennisMode = "hsv";
    setStatus(
      "未找到网球 ONNX（" +
        (e.message || e) +
        "），已用 HSV 黄绿兜底。可运行 python export_tennis_onnx.py"
    );
    return false;
  }
}

async function toggleTennis() {
  if (tennisEnabled) {
    tennisEnabled = false;
    tennisMode = "off";
    ballTracker.reset();
    syncTennisBtn();
    setStatus("网球检测已关闭");
    return;
  }
  tennisEnabled = true;
  syncTennisBtn();
  await loadTennisModel();
  syncTennisBtn();
}

async function runOnCanvas(src) {
  if (!session) await loadPoseModel();
  const tAll = performance.now();
  const { tensor, meta } = letterbox(src, cfg.imgsz);
  const poseFeeds = {};
  poseFeeds[poseInputName] = new ort.Tensor("float32", tensor, [
    1,
    3,
    cfg.imgsz,
    cfg.imgsz,
  ]);

  const tPose0 = performance.now();
  const poseOut = await session.run(poseFeeds);
  const poseMs = performance.now() - tPose0;
  const persons = decodePose(poseOut[session.outputNames[0]], meta);

  let balls = [];
  let tennisMs = 0;
  if (tennisEnabled) {
    const t1 = performance.now();
    if (tennisMode === "onnx" && tennisSession) {
      const tennisFeeds = {};
      tennisFeeds[tennisInputName] = new ort.Tensor("float32", tensor, [
        1,
        3,
        cfg.imgsz,
        cfg.imgsz,
      ]);
      const tennisOut = await tennisSession.run(tennisFeeds);
      balls = decodeDetectSportsBall(
        tennisOut[tennisSession.outputNames[0]],
        meta
      );
    } else {
      balls = detectTennisHsv(src);
    }
    tennisMs = performance.now() - t1;
  } else {
    ballTracker.reset();
  }

  const primary = pickPrimaryBall(balls);
  const trail = tennisEnabled
    ? ballTracker.update(primary, performance.now())
    : { active: false, trail: [], distM: 0, speedKmh: 0 };

  draw(src, persons, balls, trail);

  const totalMs = performance.now() - tAll;
  setStatus(
    "检测完成：" +
      persons.length +
      " 人" +
      (tennisEnabled ? " · " + balls.length + " 球" : "")
  );
  setMetrics({
    persons: persons.length,
    tennis: balls.length,
    distM: trail.distM,
    speedKmh: trail.speedKmh,
    poseMs: poseMs,
    tennisMs: tennisEnabled ? tennisMs : null,
    totalMs: totalMs,
    tennisMode: tennisEnabled ? tennisMode : null,
  });
  return { persons: persons, balls: balls, trail: trail };
}

function stopCamera() {
  camRunning = false;
  if (rafId) cancelAnimationFrame(rafId);
  rafId = 0;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  els.video.srcObject = null;
  els.camBtn.textContent = "开始摄像头";
}

async function startCamera() {
  if (camRunning) {
    stopCamera();
    setStatus("摄像头已停止");
    return;
  }
  if (!session) await loadPoseModel();

  stream = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: {
      facingMode: { ideal: "user" },
      width: { ideal: 1280 },
      height: { ideal: 720 },
      frameRate: { ideal: cfg.maxFps, max: cfg.maxFps },
    },
  });

  const v = els.video;
  v.setAttribute("playsinline", "true");
  v.setAttribute("webkit-playsinline", "true");
  v.muted = true;
  v.playsInline = true;
  v.srcObject = stream;
  await v.play();

  camRunning = true;
  els.camBtn.textContent = "停止摄像头";
  setStatus("摄像头运行中…");
  lastInferTs = 0;
  loop();
}

async function inferCameraFrame() {
  if (inferBusy) return;
  const v = els.video;
  if (v.readyState < 2) return;
  inferBusy = true;
  try {
    const vw = v.videoWidth;
    const vh = v.videoHeight;
    if (sourceCanvas.width !== vw || sourceCanvas.height !== vh) {
      sourceCanvas.width = vw;
      sourceCanvas.height = vh;
    }
    sourceCtx.drawImage(v, 0, 0);
    await runOnCanvas(sourceCanvas);
  } finally {
    inferBusy = false;
  }
}

function loop(ts) {
  if (!camRunning) return;
  rafId = requestAnimationFrame(loop);
  if (ts - lastInferTs < 1000 / cfg.maxFps) return;
  lastInferTs = ts;
  inferCameraFrame().catch((e) => {
    console.error(e);
    setStatus("推理错误: " + (e.message || e));
    stopCamera();
  });
}

function loadImageUrl(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("无法加载图片: " + url));
    img.src = url;
  });
}

async function runImageSource(img) {
  stopCamera();
  if (sourceCanvas.width !== img.naturalWidth || sourceCanvas.height !== img.naturalHeight) {
    sourceCanvas.width = img.naturalWidth;
    sourceCanvas.height = img.naturalHeight;
  }
  sourceCtx.drawImage(img, 0, 0);
  setStatus("推理中…");
  ballTracker.reset();
  await runOnCanvas(sourceCanvas);
}

els.camBtn.addEventListener("click", () => {
  startCamera().catch((e) => {
    console.error(e);
    setStatus("摄像头失败: " + (e.message || e));
  });
});

els.pickBtn.addEventListener("click", () => els.fileInput.click());

els.fileInput.addEventListener("change", () => {
  const file = els.fileInput.files && els.fileInput.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  loadImageUrl(url)
    .then((img) => runImageSource(img))
    .catch((e) => setStatus(String(e.message || e)))
    .finally(() => URL.revokeObjectURL(url));
  els.fileInput.value = "";
});

els.busBtn.addEventListener("click", () => {
  setStatus("加载测试图…");
  loadImageUrl(cfg.testImageUrl)
    .then((img) => runImageSource(img))
    .catch((e) =>
      setStatus(
        (e.message || e) + " · 请把 bus.jpg 放到 assets/bus.jpg"
      )
    );
});

els.tennisBtn.addEventListener("click", () => {
  toggleTennis().catch((e) => {
    console.error(e);
    setStatus("网球开关失败: " + (e.message || e));
  });
});

els.tennisSampleBtn.addEventListener("click", async () => {
  try {
    if (!tennisEnabled) await toggleTennis();
    setStatus("加载网球测试图…");
    const img = await loadImageUrl(cfg.tennisSampleUrl);
    await runImageSource(img);
  } catch (e) {
    setStatus(
      (e.message || e) +
        " · 可将任意图片放到 assets/tennis-sample.jpg，或用「选择图片」"
    );
  }
});

syncTennisBtn();
loadPoseModel().catch((e) => {
  console.error(e);
  setStatus(
    "姿态模型未就绪: " +
      (e.message || e) +
      " · conda activate mmpose_gpu && python export_onnx.py"
  );
});
