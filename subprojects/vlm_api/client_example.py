"""调用本地 VLM API 的示例（需先 bash scripts/start_vlm_api.sh）。"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import requests

BASE = os.environ.get("TENCLIP_VLM_API_BASE", "http://127.0.0.1:7862").rstrip("/")
API_KEY = os.environ.get("TENCLIP_VLM_API_KEY", "").strip()
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


def health() -> dict:
    r = requests.get(f"{BASE}/v1/health", timeout=10)
    r.raise_for_status()
    return r.json()


def analyze_video_file(path: str, perf_mode: str = "eco", prompt_profile: str = "default") -> dict:
    with open(path, "rb") as f:
        files = {"video": (Path(path).name, f, "video/mp4")}
        data = {"perf_mode": perf_mode, "prompt_profile": prompt_profile}
        r = requests.post(
            f"{BASE}/v1/analyze/video",
            files=files,
            data=data,
            headers=HEADERS,
            timeout=600,
        )
    r.raise_for_status()
    return r.json()


def chat_with_image(image_path: str, prompt: str, perf_mode: str = "eco") -> dict:
    raw = Path(image_path).read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    payload = {
        "prompt": prompt,
        "images_base64": [b64],
        "perf_mode": perf_mode,
    }
    r = requests.post(f"{BASE}/v1/chat", json=payload, headers=HEADERS, timeout=300)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    print("health:", health())
    if len(sys.argv) < 2:
        print("用法: python -m subprojects.vlm_api.client_example /path/to/video.mp4")
        sys.exit(0)
    result = analyze_video_file(sys.argv[1])
    print("guidance (前 500 字):", (result.get("guidance") or "")[:500])
