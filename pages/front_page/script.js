const API_BASE_URL = window.TENCLIP_API_BASE_URL || "";
const EVENTS_ENDPOINT = "/api/mobile/events";
const LOCAL_MOCK_ENDPOINT = "/web-assets/mock/events.json";

const searchInput = document.getElementById("searchInput");
const eventList = document.getElementById("eventList");
const nearbyCount = document.getElementById("nearbyCount");
const errorBox = document.getElementById("errorBox");
const chips = [...document.querySelectorAll(".chip")];
const videoInput = document.getElementById("videoInput");
const perfMode = document.getElementById("perfMode");
const analyzeBtn = document.getElementById("analyzeBtn");
const guidanceBody = document.getElementById("guidanceBody");
const promptProfileRow = document.getElementById("promptProfileRow");
const promptChips = promptProfileRow ? [...promptProfileRow.querySelectorAll(".prompt-chip")] : [];

let state = { events: [], sort: "smart", keyword: "" };
let selectedPromptProfile = "default";

function getSelectedPromptProfile() {
  return selectedPromptProfile;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** 与后端 `format_guidance_markdown` 一致：元信息 + --- + 正文 */
function splitGuidanceRaw(raw) {
  const sep = "\n\n---\n\n";
  const idx = raw.indexOf(sep);
  if (idx === -1) return { meta: "", body: raw.trim() };
  return { meta: raw.slice(0, idx).trim(), body: raw.slice(idx + sep.length).trim() };
}

function setGuidancePlain(message) {
  if (!guidanceBody) return;
  guidanceBody.textContent = message;
}

function renderGuidance(raw) {
  if (!guidanceBody) return;
  const text = String(raw || "").trim();
  if (!text) {
    guidanceBody.innerHTML = "";
    return;
  }
  const { meta, body } = splitGuidanceRaw(text);
  const displayBody = body || "（模型未返回正文）";
  const md = typeof marked !== "undefined" && typeof marked.parse === "function";
  const articleHtml = md
    ? `<article class="guidance-md">${marked.parse(displayBody, { breaks: true })}</article>`
    : `<pre class="guidance-plain">${escapeHtml(displayBody)}</pre>`;
  const runinfo = meta
    ? `<details class="guidance-runinfo"><summary>运行环境与参数</summary><pre class="guidance-runinfo-pre">${escapeHtml(
        meta
      )}</pre></details>`
    : "";
  guidanceBody.innerHTML = `<h2 class="guidance-heading">指导意见</h2>${articleHtml}${runinfo}`;
}

function cardTemplate(item) {
  return `
    <article class="card">
      <h3>${item.title}</h3>
      <p class="meta">${item.timeText}</p>
      <p class="meta">${item.locationText}</p>
      <div class="tags">
        <span class="tag">已加入 ${item.joined}/${item.capacity}</span>
        <span class="tag">NTRP ${item.levelMin} - ${item.levelMax}</span>
        <span class="tag">${item.playType}</span>
      </div>
    </article>
  `;
}

function sortEvents(events, sortBy) {
  const cloned = [...events];
  if (sortBy === "distance") return cloned.sort((a, b) => a.distanceKm - b.distanceKm);
  if (sortBy === "time") return cloned.sort((a, b) => a.startTimestamp - b.startTimestamp);
  return cloned.sort((a, b) => b.hotScore - a.hotScore);
}

function render() {
  const filtered = sortEvents(state.events, state.sort).filter((item) => {
    if (!state.keyword) return true;
    return `${item.title} ${item.locationText}`.includes(state.keyword);
  });
  nearbyCount.textContent = `附近 ${filtered.length} 场球局`;
  eventList.innerHTML = filtered.map(cardTemplate).join("") || '<article class="card"><p class="meta">暂无匹配球局</p></article>';
}

function showError(message) {
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

async function fetchEvents() {
  const apiUrl = `${API_BASE_URL}${EVENTS_ENDPOINT}`;
  try {
    const response = await fetch(apiUrl, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`API ${response.status}`);
    const payload = await response.json();
    if (!Array.isArray(payload?.events)) throw new Error("Bad payload");
    return payload.events;
  } catch (_) {
    showError("后端 API 暂不可用，已自动切换到本地 mock 数据。");
    const localResp = await fetch(LOCAL_MOCK_ENDPOINT);
    const localPayload = await localResp.json();
    return localPayload.events || [];
  }
}

async function pollAnalyzeTask(taskId) {
  const deadline = Date.now() + 20 * 60 * 1000;
  while (Date.now() < deadline) {
    const response = await fetch(
      `${API_BASE_URL}/api/mobile/analyze-video/tasks/${encodeURIComponent(taskId)}`,
      { headers: { Accept: "application/json" } }
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `查询失败 (${response.status})`);
    }
    if (payload.progress_message) {
      setGuidancePlain(payload.progress_message);
    }
    if (payload.status === "succeeded") return payload;
    if (payload.status === "failed") {
      throw new Error(payload.error || "分析失败");
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("分析超时（超过 20 分钟），请稍后重试或换更短视频。");
}

async function analyzeVideo() {
  const file = videoInput.files?.[0];
  if (!file) {
    setGuidancePlain("请先选择一个视频文件。");
    return;
  }

  clearError();
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "上传中...";
  setGuidancePlain("正在上传视频…");

  const formData = new FormData();
  formData.append("video", file);
  formData.append("perf_mode", perfMode.value);
  formData.append("prompt_profile", getSelectedPromptProfile());

  try {
    const response = await fetch(`${API_BASE_URL}/api/mobile/analyze-video/submit`, {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `提交失败 (${response.status})`);
    }
    analyzeBtn.textContent = "分析中...";
    setGuidancePlain("已上传，等待 GPU 分析…");
    const result = await pollAnalyzeTask(payload.task_id);
    let text = result.guidance || "分析完成，但没有返回文本。";
    if (result.prompt_profile_effective) {
      text += `\n\n*本次提示词档位：\`${result.prompt_profile_effective}\`。*`;
    }
    renderGuidance(text);
  } catch (error) {
    setGuidancePlain("");
    showError(`视频分析失败：${error.message}`);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "开始分析";
  }
}

async function bootstrap() {
  state.events = await fetchEvents();
  render();
}

searchInput.addEventListener("input", (event) => {
  state.keyword = event.target.value.trim();
  render();
});

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    chips.forEach((v) => v.classList.remove("active"));
    chip.classList.add("active");
    state.sort = chip.dataset.sort;
    render();
  });
});

promptChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    promptChips.forEach((v) => v.classList.remove("active"));
    chip.classList.add("active");
    selectedPromptProfile = chip.dataset.profile || "default";
  });
});

analyzeBtn.addEventListener("click", analyzeVideo);

bootstrap();
