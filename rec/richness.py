"""图文丰富度打分（基础推荐特征）。"""
from __future__ import annotations

import re

_PLACEHOLDER_TITLE_RE = re.compile(
    r"(澎湃新闻\s*[·•]?\s*文章\s*\d+)|(文章\s*\d{6,})",
    re.I,
)


def content_richness(title: str, summary: str, image_url: str | None) -> float:
    """图文丰富度：有封面、有效标题/摘要加权；无图 / 占位标题降权。"""
    score = 0.0
    img = (image_url or "").strip()
    if img.startswith("http"):
        score += 80.0  # 有真实封面：强优先
    else:
        score -= 12.0  # 无图笔记明显靠后
    title_s = (title or "").strip()
    summary_s = (summary or "").strip()
    if _PLACEHOLDER_TITLE_RE.search(title_s):
        score -= 30.0
    else:
        tlen = len(title_s)
        if tlen >= 8:
            score += min(tlen, 48) * 0.45
        elif tlen > 0:
            score += 2.0
    slen = len(summary_s)
    if slen >= 6 and summary_s != title_s:
        score += min(slen, 100) * 0.18
    elif slen >= 6:
        score += min(slen, 60) * 0.08
    return score
