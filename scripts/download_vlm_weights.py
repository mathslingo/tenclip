"""
预下载 VLM 权重到本地缓存（不加载整模到显存）。

默认使用 ModelScope（国内网络更友好）。若需 Hugging Face：
  set TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface
  python scripts/download_vlm_weights.py

模型 ID 默认与 TENCLIP_VLM_MODEL 一致（未设置时为 Qwen/Qwen2-VL-2B-Instruct）。
"""

from __future__ import annotations

import argparse
import os
import sys


def _default_source() -> str:
    s = os.environ.get("TENCLIP_MODEL_DOWNLOAD_SOURCE", "modelscope").strip().lower()
    return s if s in ("modelscope", "huggingface") else "modelscope"


def main() -> int:
    p = argparse.ArgumentParser(description="Download VLM weights (ModelScope or Hugging Face).")
    p.add_argument(
        "--repo",
        default=os.environ.get("TENCLIP_VLM_MODEL", "Qwen/Qwen2-VL-2B-Instruct"),
        help="Model id on ModelScope / Hugging Face",
    )
    p.add_argument(
        "--source",
        choices=("modelscope", "huggingface"),
        default=_default_source(),
        help="Download hub (default: modelscope, or env TENCLIP_MODEL_DOWNLOAD_SOURCE)",
    )
    args = p.parse_args()

    if args.source == "huggingface":
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("缺少 huggingface_hub。请: pip install -r requirements-llm.txt", file=sys.stderr)
            return 1
        print(f"Hugging Face 仓库: {args.repo}")
        cache = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
        if cache:
            print(f"缓存提示: {cache}")
        print("开始下载…")
        path = snapshot_download(repo_id=args.repo)
    else:
        try:
            from modelscope import snapshot_download as ms_download
        except ImportError:
            print("缺少 modelscope。请: pip install -r requirements-llm.txt", file=sys.stderr)
            return 1
        print(f"ModelScope 模型: {args.repo}")
        cdir = os.environ.get("MODELSCOPE_CACHE")
        if cdir:
            print(f"MODELSCOPE_CACHE: {cdir}")
        print("开始下载…")
        if cdir:
            path = ms_download(model_id=args.repo, cache_dir=cdir)
        else:
            path = ms_download(model_id=args.repo)

    print(f"完成。本地目录: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
