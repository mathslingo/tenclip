/**
 * YOLO Pose · ONNX Runtime Web
 * 布局对齐参考：摄像头 / 选图 / bus.jpg + IndexedDB 缓存
 * 输出：[1, 56, N] = xywh + score + 17×(x,y,conf)
 */

const COCO_EDGES = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12], [11, 13], [13, 15],
  [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4], [0, 5], [0, 6],
];

const qs = new URLSearchParams(location.search);
const cfg = {
  modelUrl: qs.get("model") || "./models/yolo11n-pose.onnx",
  imgsz: Number(qs.get("imgsz") || 640),
  confThresh: Number(qs.get("conf") || 0.25),
  kptThresh: 0.3,
  iouThresh: 0.45,
  maxFps: 30,
  maxDet: 20,
  testImageUrl: "./assets/bus.jpg",
  idbName: "tenclip-yolo-pose",
  idbStore: "models",
  idbKey: "yolo11n-pose.onnx",
};

const els = {
  video: document.getElementById("video"),
  canvas: document.getElementById("canvas"),
  camBtn: document.getElementById("camBtn"),
  pickBtn: document.getElementById("pickBtn"),
  busBtn: document.getElementById("busBtn"),
  fileInput: document.getElementById("fileInput"),
  status: document.getElementById("status"),
  metrics: document.getElementById("metrics"),
  imgszTip: document.getElementById("imgszTip"),
};

els.imgszTip.textContent = cfg.imgsz + "×" + cfg.imgsz;

let session = null;
let inputName = "images";
let camRunning = false;
let stream = null;
let rafId = 0;
let lastInferTs = 0;
let inferBusy = false;
const letterboxCanvas = document.createElement("canvas");
const letterboxCtx = letterboxCanvas.getContext("2d", { willReadFrequently: true });
const sourceCanvas = document.createElement("canvas");
const sourceCtx = sourceCanvas.getContext("2d", { willReadFrequently: true });

function setStatus(msg) {
  els.status.textContent = msg;
}

function setMetrics(persons, ms) {
  if (persons == null) {
    els.metrics.textContent = "";
    return;
  }
  els.metrics.textContent =
    "persons: " + persons + " | 推理 " + Math.round(ms) + "ms";
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

async function fetchModelBuffer() {
  const cacheKey = cfg.idbKey + "@" + cfg.modelUrl + "@" + cfg.imgsz;
  try {
    const cached = await idbGet(cacheKey);
    if (cached instanceof ArrayBuffer && cached.byteLength > 1000) {
      setStatus("模型缓存命中（IndexedDB）…");
      return cached;
    }
  } catch (_) {}

  setStatus("下载模型 " + cfg.modelUrl + " …");
  const res = await fetch(cfg.modelUrl);
  if (!res.ok) throw new Error("模型 HTTP " + res.status);
  const buf = await res.arrayBuffer();
  try {
    await idbPut(cacheKey, buf);
    setStatus("模型已缓存到 IndexedDB");
  } catch (_) {}
  return buf;
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
  const float = new Float32Array(3 * imgsz * imgsz);
  const plane = imgsz * imgsz;
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

function nms(dets) {
  dets.sort((a, b) => b.score - a.score);
  const keep = [];
  for (const d of dets) {
    if (keep.every((k) => iou(d, k) <= cfg.iouThresh)) keep.push(d);
    if (keep.length >= cfg.maxDet) break;
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
    throw new Error("意外输出形状: " + dims.join("x"));
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

function draw(source, dets) {
  const canvas = els.canvas;
  const w = source.width;
  const h = source.height;
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.drawImage(source, 0, 0);

  for (const d of dets) {
    const bw = d.x2 - d.x1;
    const bh = d.y2 - d.y1;
    ctx.strokeStyle = "#00ff00";
    ctx.lineWidth = Math.max(2, Math.round(Math.min(w, h) / 320));
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
}

async function loadModel() {
  if (session) return;
  if (!window.ort) throw new Error("onnxruntime-web 未加载");

  ort.env.wasm = ort.env.wasm || {};
  ort.env.wasm.wasmPaths =
    "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.simd = true;

  const buf = await fetchModelBuffer();
  setStatus("创建推理会话…");
  session = await ort.InferenceSession.create(buf, {
    executionProviders: ["wasm"],
    graphOptimizationLevel: "all",
  });
  inputName = session.inputNames[0] || "images";
  setStatus("模型就绪，可选摄像头 / 图片 / 测试图");
  setMetrics(null);
}

async function runOnCanvas(src) {
  if (!session) await loadModel();
  const { tensor, meta } = letterbox(src, cfg.imgsz);
  const feeds = {};
  feeds[inputName] = new ort.Tensor("float32", tensor, [
    1,
    3,
    cfg.imgsz,
    cfg.imgsz,
  ]);
  const t0 = performance.now();
  const outMap = await session.run(feeds);
  const ms = performance.now() - t0;
  const dets = decodePose(outMap[session.outputNames[0]], meta);
  draw(src, dets);
  setStatus("检测完成：" + dets.length + " 个人");
  setMetrics(dets.length, ms);
  return dets;
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
  if (!session) await loadModel();

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
        (e.message || e) +
          " · 请把 Ultralytics bus.jpg 放到 assets/bus.jpg"
      )
    );
});

loadModel().catch((e) => {
  console.error(e);
  setStatus(
    "模型未就绪: " +
      (e.message || e) +
      " · 先 python export_onnx.py --imgsz 640"
  );
});
