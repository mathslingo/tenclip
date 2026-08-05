#!/usr/bin/env python3
"""检查 Cookie 加载并抓取四条首页 Demo 笔记（使用 data/xhs_cookie.txt，除非 TENCLIP_XHS_NO_COOKIE=1）。"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# 本脚本默认使用 Cookie（与 fetch_xhs_notes_to_db 相反）
os.environ.pop("TENCLIP_XHS_NO_COOKIE", None)

import importlib.util

_xhs_path = _REPO / "subprojects" / "core_api" / "xhs_preview.py"
_spec = importlib.util.spec_from_file_location("xhs_preview", _xhs_path)
assert _spec and _spec.loader
_xhs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_xhs)

_merged_cookie_dict = _xhs._merged_cookie_dict
_repo_root = _xhs._repo_root
fetch_xhs_note_preview = _xhs.fetch_xhs_note_preview

NOTE_IDS = [
    "6912f396000000000700aca9",
    "69dd7f1d000000001b022940",
    "696e4c6c0000000021029806",
    "697f00b6000000000e00cb66",
]


def check_cookie() -> None:
    path = _repo_root() / "data" / "xhs_cookie.txt"
    print("=== Cookie 机制检查 ===")
    print(f"默认文件: {path}")
    print(f"文件存在: {path.is_file()}")
    if path.is_file():
        print(f"文件大小: {path.stat().st_size} 字节")
    print(f"TENCLIP_XHS_COOKIE_FILE: {os.environ.get('TENCLIP_XHS_COOKIE_FILE', '(未设置)')}")
    print(f"TENCLIP_XHS_COOKIE: {'(已设置)' if os.environ.get('TENCLIP_XHS_COOKIE') else '(未设置)'}")
    print(f"TENCLIP_XHS_NO_COOKIE: {os.environ.get('TENCLIP_XHS_NO_COOKIE', '(未设置)')}")
    merged = _merged_cookie_dict()
    if not merged:
        print("合并结果: 无 Cookie（将匿名请求，易被壳页拦截）")
        return
    print(f"合并结果: {len(merged)} 个键")
    for k in ("a1", "web_session", "webId", "gid", "xsec_token"):
        print(f"  {k}: {'有' if k in merged else '无'}")
    print("（不打印 Cookie 值，避免泄露）")


async def fetch_all() -> int:
    print("\n=== 按 note_id 抓取（Core API xhs_preview + Cookie）===\n")
    ok = 0
    for nid in NOTE_IDS:
        url = f"https://www.xiaohongshu.com/explore/{nid}"
        print(f"--- {nid} ---")
        try:
            m = await fetch_xhs_note_preview(url)
            title = (m.get("title") or "").strip()
            image = (m.get("image") or "")[:100]
            body = (m.get("body") or m.get("description") or "")[:120]
            tags = m.get("tags") or []
            print(f"title: {title[:100]}")
            print(f"image: {image}")
            print(f"body:  {body}")
            print(f"tags:  {tags[:8]}")
            if title:
                ok += 1
            else:
                print("(警告: 标题为空)")
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {e}")
        print()
    print(f"有标题: {ok}/{len(NOTE_IDS)}")
    return 0 if ok == len(NOTE_IDS) else 1


def main() -> int:
    check_cookie()
    return asyncio.run(fetch_all())


if __name__ == "__main__":
    raise SystemExit(main())
