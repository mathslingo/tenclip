const API_BASE = window.TENCLIP_API_BASE_URL || "";
const USER_KEY = "tenclip-news-user-id";
const TAGS_KEY = "tenclip-news-tags";

const feedGrid = document.getElementById("feedGrid");
const loading = document.getElementById("loading");
const endHint = document.getElementById("endHint");
const tagInput = document.getElementById("tagInput");
const applyBtn = document.getElementById("applyBtn");
const refreshBtn = document.getElementById("refreshBtn");
const hotTagsEl = document.getElementById("hotTags");

let offset = 0;
let pending = false;
let reachedEnd = false;

function getOrCreateUserId() {
  const old = localStorage.getItem(USER_KEY);
  if (old) return old;
  const next = `u-${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem(USER_KEY, next);
  return next;
}

function parseTags(raw) {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function currentTags() {
  return parseTags(tagInput.value || "");
}

function renderCard(item) {
  const cover = item.image_url || "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=800&q=80&auto=format&fit=crop";
  const chips = (item.tags || []).slice(0, 5).map((t) => `<span class="chip">${t}</span>`).join("");
  const el = document.createElement("article");
  el.className = "card";
  el.innerHTML = `
    <img class="cover" loading="lazy" src="${cover}" alt="news cover">
    <div class="content">
      <h3 class="title">${item.title}</h3>
      <p class="summary">${item.summary || ""}</p>
      <p class="meta">${item.source || ""} · ${new Date(item.published_at).toLocaleString()}</p>
      <div class="chips">${chips}</div>
      <div class="actions">
        <button class="action-btn primary" data-action="bookmark" type="button">收藏</button>
        <button class="action-btn" data-action="read" type="button">已读</button>
        <button class="action-btn" data-action="dislike" type="button">不感兴趣</button>
      </div>
    </div>
  `;
  el.addEventListener("click", async () => {
    await postFeedback(item.id, "click");
    window.open(item.url, "_blank", "noopener");
  });
  const actionButtons = [...el.querySelectorAll(".action-btn")];
  actionButtons.forEach((btn) => {
    btn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      const action = btn.dataset.action || "";
      if (!action) return;
      await postFeedback(item.id, action);
      if (action === "dislike") {
        el.remove();
      } else {
        btn.disabled = true;
      }
    });
  });
  return el;
}

async function postFeedback(articleId, action) {
  const userId = getOrCreateUserId();
  const body = new FormData();
  body.append("user_id", userId);
  body.append("article_id", String(articleId));
  body.append("action", action);
  try {
    await fetch(`${API_BASE}/api/news/feedback`, { method: "POST", body });
  } catch (_) {}
}

async function saveProfileTags() {
  const userId = getOrCreateUserId();
  const tags = currentTags();
  localStorage.setItem(TAGS_KEY, tags.join(","));
  const body = new FormData();
  body.append("user_id", userId);
  body.append("tags", tags.join(","));
  await fetch(`${API_BASE}/api/news/profile`, { method: "POST", body });
}

async function fetchFeed(reset = false) {
  if (pending || (reachedEnd && !reset)) return;
  pending = true;
  loading.hidden = false;
  if (reset) {
    offset = 0;
    reachedEnd = false;
    endHint.hidden = true;
    feedGrid.innerHTML = "";
  }
  const params = new URLSearchParams({
    user_id: getOrCreateUserId(),
    tags: currentTags().join(","),
    limit: "18",
    offset: String(offset),
  });
  try {
    const resp = await fetch(`${API_BASE}/api/news/feed?${params.toString()}`);
    const data = await resp.json();
    const items = data.items || [];
    items.forEach((it) => feedGrid.appendChild(renderCard(it)));
    offset = data.next_offset ?? offset + items.length;
    if (items.length === 0) {
      reachedEnd = true;
      endHint.hidden = false;
    }
  } finally {
    pending = false;
    loading.hidden = true;
  }
}

async function fetchHotTags() {
  try {
    const r = await fetch(`${API_BASE}/api/news/tags?limit=24`);
    const payload = await r.json();
    hotTagsEl.innerHTML = "";
    (payload.tags || []).forEach((tag) => {
      const b = document.createElement("button");
      b.className = "tag";
      b.textContent = tag;
      b.addEventListener("click", () => {
        const set = new Set(currentTags());
        set.add(tag);
        tagInput.value = [...set].join(", ");
      });
      hotTagsEl.appendChild(b);
    });
  } catch (_) {}
}

applyBtn.addEventListener("click", async () => {
  await saveProfileTags();
  await fetchFeed(true);
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "抓取中...";
  try {
    await fetch(`${API_BASE}/api/news/ingest`, { method: "POST" });
    await fetchHotTags();
    await fetchFeed(true);
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "抓取最新";
  }
});

window.addEventListener("scroll", async () => {
  const remain = document.documentElement.scrollHeight - window.innerHeight - window.scrollY;
  if (remain < 380) await fetchFeed(false);
});

async function bootstrap() {
  const saved = localStorage.getItem(TAGS_KEY);
  if (saved) tagInput.value = saved;
  await fetchHotTags();
  await fetch(`${API_BASE}/api/news/ingest`, { method: "POST" }).catch(() => {});
  await fetchFeed(true);
}

bootstrap();
