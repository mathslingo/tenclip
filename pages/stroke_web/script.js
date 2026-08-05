const API = "";

let detectMode = "combined";
let pollTimer = null;

const videoInput = document.getElementById("videoInput");
const fileMeta = document.getElementById("fileMeta");
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

document.querySelectorAll("#modeRow .chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#modeRow .chip").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    detectMode = btn.dataset.mode || "combined";
  });
});

motionRange.addEventListener("input", () => {
  motionVal.textContent = motionRange.value;
});

videoInput.addEventListener("change", () => {
  const f = videoInput.files?.[0];
  if (!f) {
    fileMeta.textContent = "";
    return;
  }
  fileMeta.textContent = `${f.name} · ${(f.size / (1024 * 1024)).toFixed(1)} MB`;
});

function showStatus(label, msg, pct) {
  statusCard.hidden = false;
  errorBox.hidden = true;
  summaryBox.hidden = true;
  downloadLink.hidden = true;
  statusText.textContent = label;
  statusMsg.textContent = msg || "";
  progressBar.value = pct != null ? pct : 0;
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
        submitBtn.disabled = false;
        submitBtn.textContent = "开始提取";
        if (task.summary) {
          summaryBox.hidden = false;
          summaryBox.textContent = task.summary;
        }
        downloadLink.href = `${API}/api/mobile/stroke-extract/tasks/${taskId}/download`;
        downloadLink.hidden = false;
      } else if (task.status === "failed") {
        stopPoll();
        submitBtn.disabled = false;
        submitBtn.textContent = "开始提取";
        showError(task.error || "提取失败");
      }
    } catch (err) {
      stopPoll();
      submitBtn.disabled = false;
      submitBtn.textContent = "开始提取";
      showError(err.message || "轮询失败");
    }
  }, 2000);
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

  const form = new FormData();
  form.append("video", file);
  form.append("detect_mode", detectMode);
  form.append("motion_percentile", motionRange.value);
  form.append("vlm_filter", "0");

  try {
    const res = await fetch(`${API}/api/mobile/stroke-extract/submit`, {
      method: "POST",
      body: form,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body.detail || `上传失败 (${res.status})`);
    }
    showStatus("排队中", "已提交，等待分析…", 10);
    startPoll(body.task_id);
  } catch (err) {
    submitBtn.disabled = false;
    submitBtn.textContent = "开始提取";
    showError(err.message || "提交失败");
  }
});
