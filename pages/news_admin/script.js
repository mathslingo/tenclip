const API = "";

function $(id) {
  return document.getElementById(id);
}

function toast(msg) {
  const el = $("toast");
  el.hidden = false;
  el.textContent = msg;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    el.hidden = true;
  }, 3200);
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderBars(el, rows, nameKey, countKey, total) {
  if (!rows.length) {
    el.innerHTML = "<p class='hint'>暂无数据</p>";
    return;
  }
  el.innerHTML = rows
    .map((r) => {
      const name = r[nameKey];
      const count = r[countKey] || 0;
      const pct = total > 0 ? Math.round((1000 * count) / total) / 10 : r.pct || 0;
      return `<div class="bar-row">
        <span>${escapeHtml(name)}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.min(100, pct)}%"></div></div>
        <span>${count} · ${pct}%</span>
      </div>`;
    })
    .join("");
}

function renderOverview(data, queues) {
  $("statTotal").textContent = data.article_total ?? 0;
  $("statImage").textContent = data.with_image ?? 0;
  $("statNoImage").textContent = data.without_image ?? 0;
  $("statFeedback").textContent = data.feedback_total ?? 0;
  $("dbPath").textContent = `DB: ${data.db_path || ""}`;

  const total = data.article_total || 0;
  const catMock = !!data.categories_is_mock;
  const catBadge = document.querySelectorAll(".panel h2 .badge")[0];
  if (catBadge) {
    catBadge.textContent = catMock ? "Mock" : "真实";
    catBadge.className = catMock ? "badge" : "badge real";
  }
  renderBars($("catBars"), data.categories || [], "name", "count", total);
  renderBars($("sourceBars"), data.by_source || [], "source", "count", total);

  const kv = [
    ["分析队列", queues.analysis_queue_size ?? "—"],
    ["剪辑队列", queues.stroke_queue_size ?? "—"],
    ["用户偏好数", data.profile_total ?? 0],
    ["最新发布时间", data.latest_published_at || "—"],
  ];
  $("taskKv").innerHTML = kv
    .map(([k, v]) => `<li><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></li>`)
    .join("");

  const runs = data.recent_ingest_runs || [];
  if (!runs.length) {
    $("ingestRuns").innerHTML = "<p class='hint'>尚无抓取记录。可点「立即抓取入库」。</p>";
  } else {
    $("ingestRuns").innerHTML = `<table>
      <thead><tr><th>ID</th><th>状态</th><th>写入</th><th>开始</th><th>失败源</th></tr></thead>
      <tbody>
      ${runs
        .map((r) => {
          const failed = (r.sources_failed || []).length;
          return `<tr>
            <td>${r.id}</td>
            <td class="status-${escapeHtml(r.status)}">${escapeHtml(r.status)}</td>
            <td>${r.inserted_or_updated}</td>
            <td>${escapeHtml(String(r.started_at || "").replace("T", " ").slice(0, 19))}</td>
            <td>${failed}</td>
          </tr>`;
        })
        .join("")}
      </tbody></table>`;
  }

  const cfg = data.configured_sources || [];
  $("cfgSources").innerHTML = cfg.length
    ? `<table><thead><tr><th>名称</th><th>类型</th><th>tier</th></tr></thead><tbody>
      ${cfg
        .map(
          (s) =>
            `<tr><td>${escapeHtml(s.name)}</td><td>${escapeHtml(s.kind)}</td><td>${s.tier}</td></tr>`
        )
        .join("")}
      </tbody></table>`
    : "<p class='hint'>无配置来源</p>";

  const recent = data.recent_articles || [];
  $("recentArticles").innerHTML = recent.length
    ? `<table><thead><tr><th>标题</th><th>来源</th><th>封面</th><th>入库</th></tr></thead><tbody>
      ${recent
        .map(
          (a) => `<tr>
            <td><a href="${escapeHtml(a.url)}" target="_blank" rel="noopener">${escapeHtml(a.title)}</a></td>
            <td>${escapeHtml(a.source)}</td>
            <td>${a.has_image ? "有" : "无"}</td>
            <td>${escapeHtml(String(a.ingested_at || "").replace("T", " ").slice(0, 19))}</td>
          </tr>`
        )
        .join("")}
      </tbody></table>`
    : "<p class='hint'>库为空</p>";
}

async function loadAll() {
  const [overviewRes, healthRes] = await Promise.all([
    fetch(`${API}/api/news/admin/overview`),
    fetch(`${API}/api/mobile/health`).catch(() => null),
  ]);
  if (!overviewRes.ok) throw new Error(`overview HTTP ${overviewRes.status}`);
  const overview = await overviewRes.json();
  let queues = {};
  if (healthRes && healthRes.ok) {
    const h = await healthRes.json();
    queues.analysis_queue_size = h.analysis_queue_size;
  }
  try {
    const q = await fetch(`${API}/api/news/admin/queues`);
    if (q.ok) queues = { ...queues, ...(await q.json()) };
  } catch (_) {}
  renderOverview(overview, queues);
}

async function runIngest() {
  const btn = $("ingestBtn");
  btn.disabled = true;
  btn.textContent = "抓取中…";
  try {
    const res = await fetch(`${API}/api/news/ingest?limit_per_source=20`, { method: "POST" });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
    toast(
      `完成：写入 ${body.inserted_or_updated ?? 0}，成功源 ${(body.sources || []).length}，失败 ${(body.failed || []).length}`
    );
    await loadAll();
  } catch (e) {
    toast(`抓取失败：${e.message || e}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "立即抓取入库";
  }
}

$("refreshBtn").addEventListener("click", () => {
  loadAll().then(() => toast("已刷新")).catch((e) => toast(String(e.message || e)));
});
$("ingestBtn").addEventListener("click", () => {
  runIngest();
});

loadAll().catch((e) => toast(String(e.message || e)));
