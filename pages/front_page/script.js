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
const guidanceBox = document.getElementById("guidanceBox");

let state = { events: [], sort: "smart", keyword: "" };

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

async function analyzeVideo() {
  const file = videoInput.files?.[0];
  if (!file) {
    guidanceBox.value = "请先选择一个视频文件。";
    return;
  }

  clearError();
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "分析中...";
  guidanceBox.value = "正在上传并分析，请稍候...";

  const formData = new FormData();
  formData.append("video", file);
  formData.append("perf_mode", perfMode.value);

  try {
    const response = await fetch(`${API_BASE_URL}/api/mobile/analyze-video`, {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `分析失败 (${response.status})`);
    }
    guidanceBox.value = payload.guidance || "分析完成，但没有返回文本。";
  } catch (error) {
    guidanceBox.value = "";
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

analyzeBtn.addEventListener("click", analyzeVideo);

bootstrap();
