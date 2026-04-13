"""
Resolve VLM weights to a local directory: prefer ModelScope (国内镜像友好)，可选 Hugging Face。
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 与 ModelScope / HF 上常见的 Qwen2-VL-2B-Instruct 模型 ID 一致（若拉取失败可改环境变量）
_DEFAULT_REMOTE_ID = "Qwen/Qwen2-VL-2B-Instruct"

_RESOLVED_DIR: Optional[str] = None
_RESOLVED_KEY: Optional[Tuple[str, str]] = None


def default_remote_model_id() -> str:
    return os.environ.get("TENCLIP_VLM_MODEL", _DEFAULT_REMOTE_ID).strip() or _DEFAULT_REMOTE_ID


def download_source() -> str:
    """modelscope | huggingface"""
    s = os.environ.get("TENCLIP_MODEL_DOWNLOAD_SOURCE", "modelscope").strip().lower()
    return s if s in ("modelscope", "huggingface") else "modelscope"


def _apply_hf_endpoint_alias() -> None:
    """与 download_vlm_weights.py 一致：TENCLIP_HF_ENDPOINT 写入 HF_ENDPOINT。"""
    alias = os.environ.get("TENCLIP_HF_ENDPOINT", "").strip().rstrip("/")
    if alias and not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = alias


def get_local_model_dir() -> str:
    """
    若 TENCLIP_VLM_MODEL 指向已存在目录，直接使用；
    否则视为远程模型 ID，用 ModelScope 或 HuggingFace snapshot_download 拉到本地缓存并返回目录。
    """
    global _RESOLVED_DIR, _RESOLVED_KEY

    raw = os.environ.get("TENCLIP_VLM_MODEL", "").strip()
    if raw and os.path.isdir(raw):
        return os.path.abspath(raw)

    model_id = raw or _DEFAULT_REMOTE_ID
    src = download_source()
    key = (model_id, src)
    if _RESOLVED_DIR and _RESOLVED_KEY == key:
        return _RESOLVED_DIR

    if src == "huggingface":
        _apply_hf_endpoint_alias()
        from huggingface_hub import snapshot_download

        logger.info(
            "Downloading model from Hugging Face Hub: %s (HF_ENDPOINT=%s)",
            model_id,
            os.environ.get("HF_ENDPOINT", "(default)"),
        )
        path = snapshot_download(repo_id=model_id)
    else:
        try:
            from modelscope import snapshot_download as ms_snapshot_download
        except ImportError:
            from modelscope.hub.snapshot_download import snapshot_download as ms_snapshot_download

        logger.info("Downloading model from ModelScope: %s", model_id)
        cache_dir = os.environ.get("MODELSCOPE_CACHE")
        if cache_dir:
            path = ms_snapshot_download(model_id=model_id, cache_dir=cache_dir)
        else:
            path = ms_snapshot_download(model_id=model_id)

    _RESOLVED_DIR = path
    _RESOLVED_KEY = key
    return path
