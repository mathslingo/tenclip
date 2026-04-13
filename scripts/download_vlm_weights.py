"""
预下载 VLM 权重到本地缓存（不加载整模到显存）。

- 源：ModelScope（默认）或 Hugging Face（`TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface` 或 `--source huggingface`）。
- Hugging Face 慢或不可达时，可设镜像端点（须在下载前生效）：
    export HF_ENDPOINT=https://hf-mirror.com
  或本仓库别名：
    export TENCLIP_HF_ENDPOINT=https://hf-mirror.com
- 走系统代理时，可设置 HTTP_PROXY / HTTPS_PROXY / ALL_PROXY（requests / huggingface_hub 会读取）。

模型 ID 默认与 TENCLIP_VLM_MODEL 一致（未设置时为 Qwen/Qwen2-VL-2B-Instruct）。
"""

from __future__ import annotations

import argparse
import os
import sys


def _default_source() -> str:
    s = os.environ.get("TENCLIP_MODEL_DOWNLOAD_SOURCE", "modelscope").strip().lower()
    return s if s in ("modelscope", "huggingface") else "modelscope"


def _apply_hf_endpoint_from_env() -> None:
    """TENCLIP_HF_ENDPOINT 作为 HF_ENDPOINT 的别名，便于写在 .env 里。"""
    alias = os.environ.get("TENCLIP_HF_ENDPOINT", "").strip().rstrip("/")
    if alias and not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = alias


def _print_network_hints(source: str) -> None:
    hf_effective = os.environ.get("HF_ENDPOINT", "(未设置，走官方 hub)")
    print("=== 网络与镜像 ===")
    print(f"  下载源: {source}")
    if source == "huggingface":
        print(f"  HF_ENDPOINT: {hf_effective}")
        if os.environ.get("HF_ENDPOINT", "").strip() == "":
            print("  提示: 国内可尝试  export HF_ENDPOINT=https://hf-mirror.com")
    proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    found = [k for k in proxy_keys if os.environ.get(k)]
    if found:
        print(f"  检测到代理环境变量: {', '.join(found)}")
    else:
        print("  代理: 未设置（需要时可 export HTTPS_PROXY=http://127.0.0.1:7890 等）")
    print("==================\n")


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
        help="Download hub (default: env TENCLIP_MODEL_DOWNLOAD_SOURCE or modelscope)",
    )
    p.add_argument(
        "--hf-endpoint",
        default="",
        help="覆盖 HF 端点，例如 https://hf-mirror.com（等价于临时设置 HF_ENDPOINT）",
    )
    args = p.parse_args()

    if args.hf_endpoint.strip():
        os.environ["HF_ENDPOINT"] = args.hf_endpoint.strip().rstrip("/")

    _print_network_hints(args.source)

    if args.source == "huggingface":
        _apply_hf_endpoint_from_env()
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("缺少 huggingface_hub。请: pip install -r requirements-llm.txt", file=sys.stderr)
            return 1
        print(f"Hugging Face 仓库: {args.repo}")
        if os.environ.get("HF_ENDPOINT"):
            print(f"使用 HF_ENDPOINT: {os.environ['HF_ENDPOINT']}")
        cache = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
        if cache:
            print(f"缓存提示: {cache}")
        print("开始下载…")
        path = snapshot_download(repo_id=args.repo)
    else:
        try:
            from modelscope import snapshot_download as ms_download
        except ImportError:
            try:
                from modelscope.hub.snapshot_download import snapshot_download as ms_download
            except ImportError:
                print("缺少 modelscope。请: pip install -r requirements-llm.txt", file=sys.stderr)
                return 1
        print(f"ModelScope 模型: {args.repo}")
        print("若 ModelScope 很慢，可改用 Hugging Face + 镜像，例如：")
        print("  export TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface")
        print("  export HF_ENDPOINT=https://hf-mirror.com")
        print("  python scripts/download_vlm_weights.py")
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
