"""无封面的笔记和资讯：用标题生成四大满贯虚化球场大字报。"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parent.parent
POSTER_DIR = _REPO / "data" / "posters"
FONT_PATH = _REPO / "assets" / "fonts" / "wqy-microhei.ttc"
WIDTH = 900
HEIGHT = 1200

SLAMS = (
    {
        "id": "wimbledon",
        "label": "温网草地",
        "a": (12, 59, 46),
        "b": (20, 92, 64),
        "line": (180, 255, 220),
        "ink": (244, 255, 249),
    },
    {
        "id": "roland",
        "label": "法网红土",
        "a": (141, 64, 48),
        "b": (196, 98, 62),
        "line": (255, 228, 196),
        "ink": (255, 246, 236),
    },
    {
        "id": "australian",
        "label": "澳网硬地",
        "a": (13, 78, 163),
        "b": (26, 111, 212),
        "line": (210, 244, 255),
        "ink": (238, 249, 255),
    },
    {
        "id": "usopen",
        "label": "美网夜场",
        "a": (7, 24, 51),
        "b": (18, 48, 95),
        "line": (215, 228, 255),
        "ink": (244, 247, 255),
    },
)


def _safe_id(raw: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_-]", "", str(raw or ""))
    return text[:48] or "item"


def _slam_for(key: str) -> dict:
    digest = hashlib.sha1(key.encode("utf-8")).digest()
    return SLAMS[digest[0] % len(SLAMS)]


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size=size, index=0)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    buf = ""
    for ch in text:
        if ch == "\n":
            if buf:
                lines.append(buf)
            buf = ""
            continue
        trial = buf + ch
        if font.getlength(trial) <= max_width:
            buf = trial
        else:
            if buf:
                lines.append(buf)
            buf = ch
    if buf:
        lines.append(buf)
    return lines or [""]


def _fit_lines(title: str, max_width: int, max_height: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    text = re.sub(r"\s+", " ", (title or "").strip()) or "网球"
    font = _font(72)
    lines = _wrap(text, font, max_width)
    for size in range(86, 35, -4):
        font = _font(size)
        lines = _wrap(text, font, max_width)
        line_h = int(size * 1.28)
        if len(lines) <= 7 and line_h * len(lines) <= max_height:
            return font, lines
    font = _font(36)
    lines = _wrap(text, font, max_width)[:7]
    if len(_wrap(text, font, max_width)) > 7 and lines:
        lines[-1] = lines[-1][:-1] + "…"
    return font, lines


def _paint_court(slam: dict) -> Image.Image:
    im = Image.new("RGB", (WIDTH, HEIGHT), slam["a"])
    draw = ImageDraw.Draw(im)
    stripe = 42
    for i, x in enumerate(range(0, WIDTH, stripe)):
        color = slam["a"] if i % 2 == 0 else slam["b"]
        draw.rectangle((x, 0, x + stripe, HEIGHT), fill=color)
    line = slam["line"]
    draw.rectangle((0, int(HEIGHT * 0.58), WIDTH, int(HEIGHT * 0.58) + 10), fill=line)
    draw.rectangle((int(WIDTH * 0.16), int(HEIGHT * 0.34), int(WIDTH * 0.84), int(HEIGHT * 0.34) + 8), fill=line)
    draw.rectangle((int(WIDTH * 0.5) - 4, int(HEIGHT * 0.34), int(WIDTH * 0.5) + 4, int(HEIGHT * 0.58)), fill=line)
    im = im.filter(ImageFilter.GaussianBlur(radius=22))
    shade = Image.new("L", (1, HEIGHT))
    for y in range(HEIGHT):
        shade.putpixel((0, y), int(50 + 110 * (y / HEIGHT)))
    shade = shade.resize((WIDTH, HEIGHT))
    im = Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, shade)
    return im


def render_poster(title: str, slam_key: str) -> Image.Image:
    slam = _slam_for(slam_key)
    im = _paint_court(slam)
    draw = ImageDraw.Draw(im)
    max_width = WIDTH - 120
    font, lines = _fit_lines(title, max_width, int(HEIGHT * 0.62))
    line_h = int(font.size * 1.28)
    block_h = line_h * len(lines)
    y = max(140, (HEIGHT - block_h) // 2 - 40)
    ink = slam["ink"]
    for line in lines:
        width = font.getlength(line)
        x = (WIDTH - width) / 2
        draw.text((x + 2, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=ink)
        y += line_h
    label_font = _font(28)
    label = slam["label"]
    lw = label_font.getlength(label)
    draw.text(((WIDTH - lw) / 2, HEIGHT - 110), label, font=label_font, fill=slam["line"])
    return im


def poster_url(kind: str, item_id: str, title: str) -> str:
    """生成（或复用）大字报，返回小程序可拼到 API 域名上的路径。失败返回空串。"""
    if not FONT_PATH.is_file():
        logger.warning("poster font missing: %s", FONT_PATH)
        return ""
    safe = _safe_id(item_id)
    kind_s = "note" if kind == "note" else "news"
    title_key = re.sub(r"\s+", " ", (title or "").strip()) or "网球"
    digest = hashlib.sha1(f"{kind_s}|{safe}|{title_key}".encode("utf-8")).hexdigest()[:10]
    name = f"{WIDTH}x{HEIGHT}_{kind_s}_{safe}_{digest}.jpg"
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    dest = POSTER_DIR / name
    if not dest.is_file():
        try:
            im = render_poster(title_key, f"{kind_s}:{safe}")
            im.save(dest, format="JPEG", quality=86, optimize=True)
        except Exception:
            logger.exception("poster render failed %s %s", kind_s, safe)
            return ""
    return f"/static/posters/{name}"


def attach_poster(item: dict, *, kind: str, item_id: str, title: str) -> dict:
    if (item.get("image_url") or "").strip():
        return item
    url = poster_url(kind, item_id, title)
    if not url:
        return item
    item["image_url"] = url
    images = item.get("images") or []
    if not images:
        item["images"] = [url]
    return item
