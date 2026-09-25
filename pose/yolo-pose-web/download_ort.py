#!/usr/bin/env python3
"""Download onnxruntime-web 1.20.1 dist files next to infer.worker.js.

Usage:
  python download_ort.py
"""

from __future__ import annotations

import ssl
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

VERSION = "1.20.1"
BASE = f"https://cdn.jsdelivr.net/npm/onnxruntime-web@{VERSION}/dist/"
FILES = [
    "ort.wasm.min.js",
    "ort.webgpu.min.js",
    "ort-wasm-simd-threaded.jsep.wasm",
    "ort-wasm-simd-threaded.jsep.mjs",
    "ort-wasm-simd-threaded.wasm",
    "ort-wasm-simd-threaded.mjs",
]


def fetch(url: str) -> bytes:
    ctx = ssl.create_default_context()
    req = Request(url, headers={"User-Agent": "tenclip-yolo-pose-web/1.0"})
    with urlopen(req, timeout=120, context=ctx) as resp:
        data = resp.read()
    if not data:
        raise RuntimeError("empty " + url)
    return data


def main() -> None:
    dest = Path(__file__).resolve().parent / "lib" / "ort"
    dest.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        url = BASE + name
        path = dest / name
        print(f"GET {url}")
        path.write_bytes(fetch(url))
        print(f"  → {path} ({path.stat().st_size / 1e6:.2f} MB)")
    print("ORT dist ready. wasmPaths = ./lib/ort/")


if __name__ == "__main__":
    main()
