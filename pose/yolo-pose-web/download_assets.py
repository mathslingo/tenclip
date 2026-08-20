#!/usr/bin/env python3
"""Download sample assets for the Safari demo (bus.jpg)."""

from __future__ import annotations

import ssl
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CANDIDATES = [
    "https://github.com/ultralytics/yolov5/raw/master/data/images/bus.jpg",
    "https://raw.githubusercontent.com/ultralytics/yolov5/master/data/images/bus.jpg",
    "https://ultralytics.com/images/bus.jpg",
]


def download(url: str, dest: Path, timeout: int = 90) -> None:
    ctx = ssl.create_default_context()
    headers = {"User-Agent": "tenclip-yolo-pose-web/1.0"}
    current = url
    for _ in range(8):
        req = Request(current, headers=headers)
        try:
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                data = resp.read()
        except HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                current = exc.headers["Location"]
                if current.startswith("/"):
                    # relative redirect
                    from urllib.parse import urljoin

                    current = urljoin(exc.url, current)
                continue
            raise
        if not data:
            raise RuntimeError("empty body from " + current)
        dest.write_bytes(data)
        return
    raise RuntimeError("too many redirects for " + url)


def main() -> None:
    root = Path(__file__).resolve().parent
    dest = root / "assets" / "bus.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)

    last_err: Exception | None = None
    for url in CANDIDATES:
        try:
            print(f"Downloading {url} → {dest}")
            download(url, dest)
            print(f"OK {dest.stat().st_size / 1024:.1f} KB")
            return
        except Exception as exc:
            last_err = exc
            print(f"  failed: {exc}")

    raise SystemExit(f"全部镜像失败: {last_err}")


if __name__ == "__main__":
    main()
