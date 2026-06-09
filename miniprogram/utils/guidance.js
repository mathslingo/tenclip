/** 与 H5 `pages/front_page/script.js` 一致：拆分元信息与正文 */

function splitGuidance(raw) {
  const text = String(raw || "").trim();
  const sep = "\n\n---\n\n";
  const idx = text.indexOf(sep);
  if (idx === -1) return { meta: "", body: text };
  return {
    meta: text.slice(0, idx).trim(),
    body: text.slice(idx + sep.length).trim(),
  };
}

/** 小程序内以纯文本展示，去掉常见 Markdown 符号 */
function plainBody(body) {
  return String(body || "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^[-*]\s+/gm, "• ")
    .trim();
}

function formatGuidance(raw) {
  const { meta, body } = splitGuidance(raw);
  const displayBody = plainBody(body || raw);
  return {
    meta,
    body: displayBody || "（模型未返回正文）",
    hasMeta: !!meta,
  };
}

module.exports = {
  splitGuidance,
  formatGuidance,
};
