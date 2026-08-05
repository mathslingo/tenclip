from __future__ import annotations

import argparse
import os
from pathlib import Path


DEFAULT_REPO = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
DEFAULT_SOURCE = "modelscope"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download an LLM checkpoint for local LLaMA-Factory inference."
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("TENCLIP_LLM_MODEL", DEFAULT_REPO),
        help=f"Remote model id. Default: {DEFAULT_REPO}",
    )
    parser.add_argument(
        "--source",
        choices=("huggingface", "modelscope"),
        default=os.environ.get("TENCLIP_LLM_MODEL_DOWNLOAD_SOURCE", DEFAULT_SOURCE),
        help=f"Model source. Default: {DEFAULT_SOURCE}",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.environ.get("TENCLIP_LLM_CACHE_DIR", "").strip() or None,
        help="Optional cache directory for the downloaded model.",
    )
    parser.add_argument(
        "--target-dir",
        default=os.environ.get("TENCLIP_LLM_TARGET_DIR", "").strip() or None,
        help="Optional directory to copy/snapshot the model into.",
    )
    return parser.parse_args()


def download_from_huggingface(repo: str, cache_dir: str | None) -> str:
    from huggingface_hub import snapshot_download

    kwargs = {"repo_id": repo}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    return snapshot_download(**kwargs)


def download_from_modelscope(repo: str, cache_dir: str | None) -> str:
    try:
        from modelscope import snapshot_download as ms_snapshot_download
    except ImportError:
        from modelscope.hub.snapshot_download import snapshot_download as ms_snapshot_download

    kwargs = {"model_id": repo}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    return ms_snapshot_download(**kwargs)


def main() -> None:
    args = parse_args()
    source = args.source.lower()

    if source == "huggingface":
        local_path = download_from_huggingface(args.repo, args.cache_dir)
    else:
        local_path = download_from_modelscope(args.repo, args.cache_dir)

    resolved_path = Path(local_path).resolve()
    print(f"[OK] Downloaded model: {args.repo}")
    print(f"[OK] Source: {source}")
    print(f"[OK] Local path: {resolved_path}")

    if args.target_dir:
        target_dir = Path(args.target_dir).resolve()
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        print(
            "[INFO] target-dir is set. Reuse the printed local snapshot path directly in "
            "LLaMA-Factory, or copy files manually if you need a separate fixed directory."
        )
        print(f"[INFO] Requested target-dir: {target_dir}")


if __name__ == "__main__":
    main()
