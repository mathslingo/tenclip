"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PerfMode = Literal["eco", "balanced", "quality"]


class HealthResponse(BaseModel):
    ok: bool
    service: str = "tenclip-vlm-api"
    model_ready: bool
    backend: str = ""
    model_path: str = ""
    error: str = ""


class MetaResponse(BaseModel):
    perf_modes: list[str]
    prompt_profiles: list[str]
    max_video_duration_sec: float
    default_perf_mode: str = "eco"


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="用户文本提示")
    system_prompt: str | None = Field(None, description="可选系统提示")
    images_base64: list[str] = Field(
        default_factory=list,
        description="Base64 图片（可带 data:image/...;base64, 前缀）",
    )
    perf_mode: PerfMode = "eco"
    max_new_tokens: int | None = Field(None, ge=128, le=8192)


class ChatResponse(BaseModel):
    text: str
    perf_mode: str
    image_count: int


class AnalyzeVideoPathRequest(BaseModel):
    video_path: str = Field(..., description="服务器本地视频绝对路径（须在 data/ 目录下）")
    perf_mode: PerfMode = "eco"
    prompt_profile: str = "default"


class AnalyzeVideoResponse(BaseModel):
    guidance: str
    perf_mode: str
    prompt_profile: str
