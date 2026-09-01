const API = "";

const CHUNK_SIZE = 4 * 1024 * 1024;
const CHUNK_THRESHOLD = 16 * 1024 * 1024;
const CONCURRENCY = 2;
const CHUNK_RETRY = 3;

let detectMode = "spike";
let pollTimer = null;
let wakeLock = null;

const videoInput = document.getElementById("videoInput");
const picker = document.getElementById("picker");
const pickerEmpty = document.getElementById("pickerEmpty");
const pickerFile = document.getElementById("pickerFile");
const fileName = document.getElementById("fileName");
const fileMeta = document.getElementById("fileMeta");
const modeDesc = document.getElementById("modeDesc");
const motionRange = document.getElementById("motionRange");
const motionVal = document.getElementById("motionVal");
const submitBtn = document.getElementById("submitBtn");
const statusCard = document.getElementById("statusCard");
const statusText = document.getElementById("statusText");
const statusMsg = document.getElementById("statusMsg");
const progressBar = document.getElementById("progressBar");
const errorBox = document.getElementById("errorBox");
const summaryBox = document.getElementById("summaryBox");
const downloadLink = document.getElementById("downloadLink");

const MODE_DESC = {
  combined: "画面运动 + 击球声双重判断，回合保留更完整，但可能带入少量等待画面。",
  spike: "只抓击球瞬间的尖峰，每段约 2～4 秒，实测效果最好，默认推荐。",
  motion: "只看画面运动幅度，适合环境嘈杂、击球声不清的场地。",
  audio: "只凭击球声判断，适合机位固定、画面变化少的视频。",
};

function updateModeDesc() {
  modeDesc.textContent = MODE_DESC[detectMode] || "";
}

document.querySelectorAll("#modeRow .chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#modeRow .chip").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    detectMode = btn.dataset.mode || "combined";
    updateModeDesc();
  });
});
updateModeDesc();

motionRange.addEventListener("input", () => {
  motionVal.textContent = motionRange.value;
});

function fileSig(f) {
  return `${f.name}_${f.size}_${f.lastModified}`;
}

function fmtDuration(sec) {
  if (!isFinite(sec) || sec <= 0) return "";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`;
}

picker.addEventListener("click", () => videoInput.click());

videoInput.addEventListener("change", () => {
  const f = videoInput.files?.[0];
  if (!f) {
    pickerFile.hidden = true;
    pickerEmpty.hidden = false;
    return;
  }
  pickerEmpty.hidden = true;
  pickerFile.hidden = false;
  fileName.textContent = f.name;

  let meta = `${(f.size / (1024 * 1024)).toFixed(1)} MB`;
  if (localStorage.getItem("stroke_upload_" + fileSig(f))) {
    meta += " · 有未完成的上传，可断点续传";
  }
  fileMeta.textContent = meta;

  const url = URL.createObjectURL(f);
  const probe = document.createElement("video");
  probe.preload = "metadata";
  probe.src = url;
  probe.onloadedmetadata = () => {
    URL.revokeObjectURL(url);
    const dur = fmtDuration(probe.duration);
    if (dur) fileMeta.textContent = `时长 ${dur} · ` + fileMeta.textContent;
  };
});

function showStatus(label, msg, pct) {
  statusCard.hidden = false;
  errorBox.hidden = true;
  summaryBox.hidden = true;
  downloadLink.hidden = true;
  statusText.textContent = label;
  statusMsg.textContent = msg || "";
  if (pct != null) progressBar.value = pct;
}

function showError(msg) {
  statusCard.hidden = false;
  statusText.textContent = "失败";
  errorBox.hidden = false;
  errorBox.textContent = msg;
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function acquireWakeLock() {
  try {
    if (navigator.wakeLock?.request) {
      wakeLock = await navigator.wakeLock.request("screen");
    }
  } catch (e) {
    wakeLock = null;
  }
}

function releaseWakeLock() {
  try {
    wakeLock?.release();
  } catch (e) {}
  wakeLock = null;
}

async function pollTask(taskId) {
  const res = await fetch(`${API}/api/mobile/stroke-extract/tasks/${taskId}`);
  if (!res.ok) throw new Error(`查询失败 (${res.status})`);
  return res.json();
}

function startPoll(taskId) {
  stopPoll();
  pollTimer = setInterval(async () => {
    try {
      const task = await pollTask(taskId);
      const pct = Math.round((task.progress_frac || 0) * 100);
      const labels = { queued: "排队中", running: "分析中", succeeded: "完成", failed: "失败" };
      showStatus(labels[task.status] || task.status, task.progress_message || "", pct);
      if (task.status === "succeeded") {
        stopPoll();
        resetSubmitBtn();
        if (task.summary) {
          summaryBox.hidden = false;
          summaryBox.textContent = task.summary;
        }
        downloadLink.href = `${API}/api/mobile/stroke-extract/tasks/${taskId}/download`;
        downloadLink.hidden = false;
      } else if (task.status === "failed") {
        stopPoll();
        resetSubmitBtn();
        showError(task.error || "提取失败");
      }
    } catch (err) {
      stopPoll();
      resetSubmitBtn();
      showError(err.message || "轮询失败");
    }
  }, 2000);
}

function resetSubmitBtn() {
  submitBtn.disabled = false;
  submitBtn.textContent = "开始提取";
}

// ---------- 分片上传 ----------

async function createSession(file) {
  const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
  const form = new FormData();
  form.append("purpose", "stroke");
  form.append("file_size", String(file.size));
  form.append("filename", file.name || "video.mp4");
  form.append("total_chunks", String(totalChunks));
  form.append("chunk_size", String(CHUNK_SIZE));
  form.append("detect_mode", detectMode);
  form.append("motion_percentile", motionRange.value);
  form.append("vlm_filter", "0");
  const res = await fetch(`${API}/api/mobile/upload-sessions`, { method: "POST", body: form });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `创建上传会话失败 (${res.status})`);
  return body;
}

async function querySession(sessionId) {
  const res = await fetch(`${API}/api/mobile/upload-sessions/${sessionId}`);
  if (!res.ok) return null;
  return res.json();
}

async function putChunk(sessionId, index, blob) {
  const res = await fetch(`${API}/api/mobile/upload-sessions/${sessionId}/chunks/${index}`, {
    method: "PUT",
    body: blob,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `分片 ${index} 上传失败 (${res.status})`);
  }
}

async function completeSession(sessionId) {
  const res = await fetch(`${API}/api/mobile/upload-sessions/${sessionId}/complete`, { method: "POST" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `合并失败 (${res.status})`);
  return body;
}

function fmtEta(sec) {
  if (!isFinite(sec) || sec < 0) return "";
  if (sec < 60) return `约 ${Math.ceil(sec)} 秒`;
  return `约 ${Math.floor(sec / 60)} 分 ${Math.ceil(sec % 60)} 秒`;
}

async function uploadChunked(file) {
  const sig = fileSig(file);
  const storeKey = "stroke_upload_" + sig;
  const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));

  let sessionId = null;
  let uploaded = new Set();

  const saved = localStorage.getItem(storeKey);
  if (saved) {
    try {
      const rec = JSON.parse(saved);
      const st = await querySession(rec.session_id);
      if (st && st.total_chunks === totalChunks) {
        sessionId = st.session_id;
        uploaded = new Set(st.uploaded || []);
        showStatus("上传中", `断点续传：已完成 ${uploaded.size}/${totalChunks} 片`, 5);
      }
    } catch (e) {}
  }

  if (!sessionId) {
    const sess = await createSession(file);
    sessionId = sess.session_id;
    localStorage.setItem(storeKey, JSON.stringify({ session_id: sessionId }));
  }

  const pending = [];
  for (let i = 0; i < totalChunks; i++) {
    if (!uploaded.has(i)) pending.push(i);
  }

  let doneBytes = uploaded.size * CHUNK_SIZE;
  const startedAt = Date.now();
  let cursor = 0;

  async function worker() {
    while (cursor < pending.length) {
      const idx = pending[cursor++];
      const blob = file.slice(idx * CHUNK_SIZE, Math.min(file.size, (idx + 1) * CHUNK_SIZE));
      let lastErr = null;
      for (let attempt = 0; attempt <= CHUNK_RETRY; attempt++) {
        try {
          await putChunk(sessionId, idx, blob);
          lastErr = null;
          break;
        } catch (err) {
          lastErr = err;
          await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
        }
      }
      if (lastErr) throw lastErr;
      doneBytes += blob.size;
      const elapsed = (Date.now() - startedAt) / 1000;
      const speed = elapsed > 0.5 ? doneBytes / elapsed : 0;
      const remain = (file.size - doneBytes) / (speed || 1);
      const pct = 5 + Math.round((doneBytes / file.size) * 90);
      showStatus(
        "上传中",
        `${(doneBytes / 1048576).toFixed(0)}/${(file.size / 1048576).toFixed(0)} MB` +
          (speed ? ` · ${(speed / 1048576).toFixed(1)} MB/s · ${fmtEta(remain)}` : "") +
          " · 请勿切出浏览器",
        pct
      );
    }
  }

  const workers = [];
  for (let i = 0; i < CONCURRENCY; i++) workers.push(worker());
  await Promise.all(workers);

  showStatus("合并中", "服务器正在合并分片并提交分析…", 97);
  const task = await completeSession(sessionId);
  localStorage.removeItem(storeKey);
  return task;
}

async function uploadDirect(file) {
  const form = new FormData();
  form.append("video", file);
  form.append("detect_mode", detectMode);
  form.append("motion_percentile", motionRange.value);
  form.append("vlm_filter", "0");
  const res = await fetch(`${API}/api/mobile/stroke-extract/submit`, { method: "POST", body: form });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `上传失败 (${res.status})`);
  return body;
}

submitBtn.addEventListener("click", async () => {
  const file = videoInput.files?.[0];
  if (!file) {
    showError("请先选择视频");
    return;
  }
  stopPoll();
  submitBtn.disabled = true;
  submitBtn.textContent = "上传中…";
  showStatus("上传中", "正在提交视频…", 5);
  await acquireWakeLock();

  try {
    const task = file.size > CHUNK_THRESHOLD ? await uploadChunked(file) : await uploadDirect(file);
    showStatus("排队中", "已提交，等待分析…", 10);
    startPoll(task.task_id);
  } catch (err) {
    showError((err.message || "上传失败") + "。网络恢复后重新点「开始提取」可断点续传。");
    resetSubmitBtn();
  } finally {
    releaseWakeLock();
  }
});
