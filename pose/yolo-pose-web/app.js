/**
 * YOLO Pose + Tennis · UI / camera / HUD
 * Inference: Worker (lib/infer.worker.js) with main-thread fallback.
 */

const COCO_EDGES = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12], [11, 13], [13, 15],
  [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4], [0, 5], [0, 6],
];

const qs = new URLSearchParams(location.search);
const cfg = {
  modelUrl: qs.get("model") || "./models/yolo11n-pose.onnx",
  tennisModelUrl: qs.get("tennisModel") || "./models/yolo11n-tennis.onnx",
  tennisRoiModelUrl: qs.get("tennisRoiModel") || "./models/yolo11n-tennis-roi.onnx",
  imgsz: Number(qs.get("imgsz") || 640),
  tennisRoiImgsz: Number(qs.get("tennisImgsz") || 320),
  tennisFullImgsz: Number(qs.get("tennisFullImgsz") || qs.get("imgsz") || 640),
  tennisRoiMin: 256,
  tennisRoiMax: 384,
  tennisRoiMissMax: 2,
  tennisRoi: qs.get("roi") !== "0",
  useWorker: false,
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
  tennisRoiIdbKey: "yolo11n-tennis-roi.onnx",
  backendKey: "tenclip-yolo-backend",
  facingKey: "tenclip-yolo-facing",
  camWidth: 960,
};

function preferWorker() {
  var q = qs.get("worker");
  if (q === "0") return false;
  if (q === "1") return true;
  var ua = navigator.userAgent || "";
  // Safari / iOS：Dedicated Worker + ORT WebGPU/pthread 易失败，回退主线程（P0 前可用的路径）
  if (/iPhone|iPad|iPod/i.test(ua)) return false;
  if (/Safari/i.test(ua) && !/Chrome|Chromium|Android|Edg|OPR/i.test(ua)) return false;
  return true;
}
cfg.useWorker = preferWorker();

function engineCfg() {
  return {
    imgsz: cfg.imgsz,
    tennisRoiImgsz: cfg.tennisRoiImgsz,
    tennisFullImgsz: cfg.tennisFullImgsz,
    tennisRoiMin: cfg.tennisRoiMin,
    tennisRoiMax: cfg.tennisRoiMax,
    tennisRoiMissMax: cfg.tennisRoiMissMax,
    tennisRoi: cfg.tennisRoi,
    confThresh: cfg.confThresh,
    tennisConf: cfg.tennisConf,
    iouThresh: cfg.iouThresh,
    maxDet: cfg.maxDet,
    maxTennis: cfg.maxTennis,
  };
}

function readBackendPref() {
  const q = qs.get("webgpu");
  if (q === "0") return "cpu";
  if (q === "1") return "gpu";
  try {
    const v = localStorage.getItem(cfg.backendKey);
    if (v === "cpu" || v === "gpu") return v;
  } catch (_) {}
  return "gpu";
}

function readFacing() {
  const q = qs.get("facing");
  if (q === "user" || q === "environment") return q;
  try {
    const v = localStorage.getItem(cfg.facingKey);
    if (v === "user" || v === "environment") return v;
  } catch (_) {}
  return "environment";
}

const els = {
  video: document.getElementById("video"),
  canvas: document.getElementById("canvas"),
  camBtn: document.getElementById("camBtn"),
  pickBtn: document.getElementById("pickBtn"),
  busBtn: document.getElementById("busBtn"),
  tennisBtn: document.getElementById("tennisBtn"),
  gpuBtn: document.getElementById("gpuBtn"),
  faceBtn: document.getElementById("faceBtn"),
  tennisSampleBtn: document.getElementById("tennisSampleBtn"),
  fileInput: document.getElementById("fileInput"),
  status: document.getElementById("status"),
  metrics: document.getElementById("metrics"),
};

let inferWorker = null;
let localEngine = null;
let poseBuf = null;
let tennisBuf = null;
let tennisRoiBuf = null;
let tennisEnabled = false;
let tennisMode = "off";
let backendPref = readBackendPref();
let backendName = "wasm";
let gpuNote = "";
let facingMode = readFacing();
let camRunning = false;
let stream = null;
let rafId = 0;
let lastInferTs = 0;
let inferBusy = false;
let roiHint = { miss: 99 };
let workerRpc = new Map();
let workerRpcSeq = 1;
let initPromise = null;

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
  if (info.poseMs != null) parts.push("推理 " + Math.round(info.poseMs) + "ms");
  if (info.usedRoi) parts.push("网球ROI");
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
  if (info.viaWorker) parts.push("[worker]");
  parts.push("[" + backendName + "]");
  els.metrics.textContent = parts.join(" | ");
}

function syncGpuBtn() {
  if (!els.gpuBtn) return;
  if (backendPref !== "gpu") {
    els.gpuBtn.textContent = "GPU：关(CPU)";
    els.gpuBtn.className = "gpu-off";
    els.gpuBtn.title = "点按尝试 WebGPU";
    return;
  }
  if (backendName === "webgpu") {
    els.gpuBtn.textContent = "GPU：WebGPU";
    els.gpuBtn.className = "gpu-on";
    els.gpuBtn.title = "点按切回 CPU(WASM)";
  } else {
    els.gpuBtn.textContent = "GPU：不可用";
    els.gpuBtn.className = "gpu-warn";
    els.gpuBtn.title = gpuNote || "已回退 CPU(WASM)";
  }
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

function syncFaceBtn() {
  if (!els.faceBtn) return;
  els.faceBtn.textContent = facingMode === "user" ? "镜头：前" : "镜头：后";
  els.faceBtn.title = "切换前置 / 后置";
}

function applyMeta(meta) {
  if (!meta) return;
  if (meta.backendName) backendName = meta.backendName;
  if (meta.gpuNote != null) gpuNote = meta.gpuNote;
  if (meta.tennisMode) tennisMode = meta.tennisMode;
  syncGpuBtn();
  syncTennisBtn();
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

function wasmPaths() {
  return new URL("./lib/ort/", location.href).href;
}

async function loadOrtScript() {
  if (window.ort) return;
  await new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "./lib/ort/ort.webgpu.min.js";
    s.onload = resolve;
    s.onerror = () => reject(new Error("无法加载本地 onnxruntime-web"));
    document.head.appendChild(s);
  });
  ort.env.wasm = ort.env.wasm || {};
  ort.env.wasm.wasmPaths = wasmPaths();
}

function workerPost(payload, transfer) {
  return new Promise((resolve, reject) => {
    if (!inferWorker) {
      reject(new Error("no worker"));
      return;
    }
    const id = workerRpcSeq++;
    payload.id = id;
    const timer = setTimeout(() => {
      if (!workerRpc.has(id)) return;
      workerRpc.delete(id);
      reject(new Error("Worker 超时（模型加载或推理）"));
    }, 45000);
    workerRpc.set(id, {
      resolve: (msg) => {
        clearTimeout(timer);
        resolve(msg);
      },
      reject: (err) => {
        clearTimeout(timer);
        reject(err);
      },
    });
    inferWorker.postMessage(payload, transfer || []);
  });
}

function rejectAllWorker(err) {
  workerRpc.forEach((p) => p.reject(err));
  workerRpc.clear();
}

function attachWorker(w) {
  w.onmessage = (ev) => {
    const msg = ev.data || {};
    const pending = msg.id != null ? workerRpc.get(msg.id) : null;
    if (msg.type === "error") {
      const err = new Error(msg.message || "worker error");
      if (pending) {
        workerRpc.delete(msg.id);
        pending.reject(err);
      } else {
        setStatus("推理错误: " + (msg.message || ""));
      }
      return;
    }
    applyMeta(msg);
    if (pending) {
      workerRpc.delete(msg.id);
      pending.resolve(msg);
    }
  };
  w.onerror = (ev) => {
    rejectAllWorker(ev.error || new Error(ev.message || "worker error"));
  };
}

async function startLocalEngine() {
  await loadOrtScript();
  localEngine = window.createYoloEngine(window.ort, engineCfg(), {
    wasmPaths: wasmPaths(),
    inWorker: false,
  });
  await localEngine.loadPose(poseBuf, backendPref);
  applyMeta({
    backendName: localEngine.backendName,
    gpuNote: localEngine.gpuNote,
    tennisMode: localEngine.tennisMode || "off",
  });
}

async function initInference() {
  poseBuf = await fetchModelBuffer(cfg.modelUrl, cfg.idbKey);
  setStatus("创建推理会话…");
  if (cfg.useWorker && typeof Worker !== "undefined") {
    try {
      inferWorker = new Worker("./lib/infer.worker.js?v=20260918a");
      attachWorker(inferWorker);
      await workerPost({
        type: "init",
        cfg: engineCfg(),
        backendPref: backendPref,
        poseBuf: poseBuf,
      });
      setStatus(
        "姿态模型就绪（" +
          backendName +
          (gpuNote ? " · " + gpuNote : "") +
          " · worker）。可开摄像头；点「网球」加载球检测"
      );
      return;
    } catch (e) {
      console.warn("Worker 不可用，回退主线程", e);
      rejectAllWorker(e);
      if (inferWorker) {
        try {
          inferWorker.terminate();
        } catch (_) {}
        inferWorker = null;
      }
    }
  }
  await startLocalEngine();
  setStatus(
    "姿态模型就绪（" +
      backendName +
      (gpuNote ? " · " + gpuNote : "") +
      "）。可开摄像头；点「网球」加载球检测"
  );
}

function ensureInit() {
  if (!initPromise) {
    initPromise = initInference().catch((e) => {
      initPromise = null;
      throw e;
    });
  }
  return initPromise;
}

async function loadTennisModel() {
  if (tennisMode === "onnx") return true;
  try {
    const t0 = performance.now();
    setStatus("加载网球检测模型…");
    tennisBuf = await fetchModelBuffer(cfg.tennisModelUrl, cfg.tennisIdbKey);
    try {
      tennisRoiBuf = await fetchModelBuffer(
        cfg.tennisRoiModelUrl,
        cfg.tennisRoiIdbKey
      );
    } catch (_) {
      tennisRoiBuf = null;
    }
    if (inferWorker) {
      const msg = await workerPost({
        type: "load-tennis",
        tennisBuf: tennisBuf,
        tennisRoiBuf: tennisRoiBuf,
      });
      tennisMode = msg.onnx ? "onnx" : "hsv";
    } else {
      const ok = await localEngine.loadTennis(tennisBuf, tennisRoiBuf);
      tennisMode = ok ? "onnx" : "hsv";
      applyMeta({
        backendName: localEngine.backendName,
        gpuNote: localEngine.gpuNote,
        tennisMode: tennisMode,
      });
    }
    setStatus(
      tennisMode === "onnx"
        ? "网球模型就绪（" + ((performance.now() - t0) / 1000).toFixed(1) + "s）。再点一次可关闭。"
        : "网球 ONNX 失败，已用 HSV 黄绿兜底。"
    );
    return tennisMode === "onnx";
  } catch (e) {
    console.warn("tennis onnx unavailable, HSV fallback", e);
    tennisBuf = null;
    if (inferWorker) {
      await workerPost({ type: "load-tennis", tennisBuf: null });
    } else if (localEngine) {
      await localEngine.loadTennis(null);
    }
    tennisMode = "hsv";
    setStatus(
      "未找到网球 ONNX（" + (e.message || e) + "），已用 HSV 黄绿兜底。"
    );
    return false;
  }
}

async function toggleTennis() {
  if (tennisEnabled) {
    tennisEnabled = false;
    tennisMode = "off";
    roiHint = { miss: 99 };
    ballTracker.reset();
    if (inferWorker) {
      workerPost({ type: "drop-tennis" }).catch(function () {});
    } else if (localEngine) {
      localEngine.dropTennis();
    }
    syncTennisBtn();
    setStatus("网球检测已关闭");
    return;
  }
  tennisEnabled = true;
  syncTennisBtn();
  await loadTennisModel();
  syncTennisBtn();
  syncGpuBtn();
}

async function toggleGpu() {
  backendPref = backendPref === "gpu" ? "cpu" : "gpu";
  try {
    localStorage.setItem(cfg.backendKey, backendPref);
  } catch (_) {}
  for (let i = 0; i < 40 && inferBusy; i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  inferBusy = true;
  if (els.gpuBtn) els.gpuBtn.disabled = true;
  try {
    setStatus("切换推理后端…");
    if (inferWorker) {
      await workerPost({
        type: "rebuild",
        backendPref: backendPref,
        poseBuf: poseBuf,
        tennisBuf: tennisEnabled ? tennisBuf : null,
        tennisRoiBuf: tennisEnabled ? tennisRoiBuf : null,
      });
    } else if (localEngine) {
      await localEngine.rebuild(
        backendPref,
        poseBuf,
        tennisEnabled ? tennisBuf : null,
        tennisEnabled ? tennisRoiBuf : null
      );
      applyMeta({
        backendName: localEngine.backendName,
        gpuNote: localEngine.gpuNote,
        tennisMode: localEngine.tennisMode,
      });
    }
    setStatus("当前后端：" + backendName + (gpuNote ? "（" + gpuNote + "）" : ""));
  } finally {
    if (els.gpuBtn) els.gpuBtn.disabled = false;
    inferBusy = false;
    syncGpuBtn();
  }
}

function pickPrimaryBall(balls) {
  if (!balls || !balls.length) return null;
  var snap = ballTracker.snapshot();
  if (snap && snap.active) {
    var best = null;
    var bestD = Infinity;
    for (var i = 0; i < balls.length; i++) {
      var d = balls[i];
      var cx = (d.x1 + d.x2) / 2;
      var cy = (d.y1 + d.y2) / 2;
      var dist = Math.hypot(cx - snap.cx, cy - snap.cy);
      if (dist < bestD) {
        bestD = dist;
        best = d;
      }
    }
    return best;
  }
  return balls.slice().sort(function (a, b) {
    return b.score - a.score;
  })[0];
}

function updateRoiHint(primary) {
  if (!primary) {
    roiHint = {
      cx: roiHint.cx,
      cy: roiHint.cy,
      boxW: roiHint.boxW,
      boxH: roiHint.boxH,
      miss: (roiHint.miss || 0) + 1,
    };
    return;
  }
  roiHint = {
    cx: (primary.x1 + primary.x2) / 2,
    cy: (primary.y1 + primary.y2) / 2,
    boxW: primary.x2 - primary.x1,
    boxH: primary.y2 - primary.y1,
    miss: 0,
  };
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

async function runOnCanvas(src) {
  await ensureInit();
  if (!inferWorker && !localEngine) throw new Error("姿态模型未就绪");
  const tAll = performance.now();
  let result;
  let viaWorker = false;
  if (inferWorker) {
    viaWorker = true;
    const bmp = await createImageBitmap(src);
    const msg = await workerPost(
      {
        type: "frame",
        bitmap: bmp,
        tennisEnabled: tennisEnabled,
        roiHint: tennisEnabled ? roiHint : { miss: 99 },
      },
      [bmp]
    );
    result = msg.result;
  } else {
    result = await localEngine.runFrame(
      src,
      tennisEnabled,
      tennisEnabled ? roiHint : { miss: 99 }
    );
  }

  const persons = result.persons || [];
  const balls = result.balls || [];
  if (result.backendName) backendName = result.backendName;
  if (result.gpuNote != null) gpuNote = result.gpuNote;
  if (result.tennisMode) tennisMode = result.tennisMode;

  const primary = pickPrimaryBall(balls);
  if (tennisEnabled) updateRoiHint(primary);
  else roiHint = { miss: 99 };

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
    poseMs: result.poseMs,
    tennisMs: tennisEnabled ? result.tennisMs : null,
    totalMs: totalMs,
    tennisMode: tennisEnabled ? tennisMode : null,
    usedRoi: !!result.usedRoi,
    viaWorker: viaWorker,
  });
  syncGpuBtn();
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

async function openCameraStream() {
  const tries = [
    {
      facingMode: { ideal: facingMode },
      width: { ideal: cfg.camWidth },
      height: { ideal: 540 },
    },
    { facingMode: { ideal: facingMode } },
    { facingMode: facingMode },
    { facingMode: { ideal: "user" } },
    true,
  ];
  let last = null;
  for (let i = 0; i < tries.length; i++) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: tries[i],
      });
      if (i >= 3 && facingMode !== "user") {
        facingMode = "user";
        try {
          localStorage.setItem(cfg.facingKey, facingMode);
        } catch (_) {}
        syncFaceBtn();
      }
      return stream;
    } catch (e) {
      last = e;
    }
  }
  throw last || new Error("getUserMedia 失败");
}

async function startCamera() {
  if (camRunning) {
    stopCamera();
    setStatus("摄像头已停止");
    return;
  }
  setStatus("准备摄像头与模型…");
  await ensureInit();
  if (!inferWorker && !localEngine) {
    throw new Error("姿态模型未就绪");
  }

  stream = await openCameraStream();

  const v = els.video;
  v.setAttribute("playsinline", "true");
  v.setAttribute("webkit-playsinline", "true");
  v.muted = true;
  v.playsInline = true;
  v.srcObject = stream;
  await v.play();

  camRunning = true;
  els.camBtn.textContent = "停止摄像头";
  setStatus("摄像头运行中（" + (facingMode === "user" ? "前置" : "后置") + "）…");
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
  roiHint = { miss: 99 };
  await runOnCanvas(sourceCanvas);
}

async function toggleFacing() {
  facingMode = facingMode === "user" ? "environment" : "user";
  try {
    localStorage.setItem(cfg.facingKey, facingMode);
  } catch (_) {}
  syncFaceBtn();
  if (camRunning) {
    stopCamera();
    await startCamera();
  }
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
      setStatus((e.message || e) + " · 请把 bus.jpg 放到 assets/bus.jpg")
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

els.gpuBtn.addEventListener("click", () => {
  toggleGpu().catch((e) => {
    console.error(e);
    setStatus("切换后端失败: " + (e.message || e));
  });
});

if (els.faceBtn) {
  els.faceBtn.addEventListener("click", () => {
    toggleFacing().catch((e) => setStatus("切换镜头失败: " + (e.message || e)));
  });
}

syncTennisBtn();
syncGpuBtn();
syncFaceBtn();
ensureInit()
  .then(syncGpuBtn)
  .catch((e) => {
    console.error(e);
    setStatus(
      "姿态模型未就绪: " +
        (e.message || e) +
        " · 请硬刷新；仍失败则试 ?webgpu=0"
    );
  });
