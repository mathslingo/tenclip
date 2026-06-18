# TenClip VLM API 接口文档

本地 **Qwen2-VL** 推理 HTTP 服务，供动作分析、击球 VLM 过滤、批处理脚本等模块调用。实现位于 `subprojects/vlm_api/`，推理逻辑复用 `services/vlm_tennis.py`。

| 项 | 说明 |
|----|------|
| 默认地址 | `http://127.0.0.1:7862` |
| 交互文档 | `http://127.0.0.1:7862/docs`（Swagger UI） |
| 与主应用关系 | 独立于 `app.py`（7861），可单独起进程占 GPU |

---

## 启动

```bash
cd ~/code/tenclip
pip install -r requirements-vlm-api.txt
# 推理依赖（二选一或都装）：
# pip install -r requirements-llm-lf.txt
# pip install -r requirements-llm.txt

bash scripts/start_vlm_api.sh
```

等价命令：

```bash
python3 -m uvicorn subprojects.vlm_api.app:app --host 127.0.0.1 --port 7862
```

---

## 认证

| 环境变量 | 说明 |
|----------|------|
| `TENCLIP_VLM_API_KEY` | 非空时，除健康检查外的接口须在请求头携带 `X-API-Key: <值>` |

未设置该变量时，本机开发无需鉴权。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TENCLIP_VLM_API_HOST` | `127.0.0.1` | 监听地址 |
| `TENCLIP_VLM_API_PORT` | `7862` | 监听端口 |
| `TENCLIP_VLM_API_KEY` | （空） | API 密钥 |
| `TENCLIP_VLM_API_WORKERS` | `1` | 推理线程池大小；GPU 建议 `1` |
| `TENCLIP_VLM_API_DATA_ROOT` | （空） | 扩展 `/v1/analyze/video/path` 允许访问的目录根 |
| `TENCLIP_UPLOAD_DIR` | （空） | 上传目录，亦作为 path 分析白名单根之一 |
| `TENCLIP_VLM_MODEL` | 见 `model/` | 本地权重目录或远程模型 ID |
| `TENCLIP_INFER_BACKEND` | `auto` | `auto` / `llamafactory` / `transformers` |
| `TENCLIP_FORCE_CPU` | （空） | `1` 时强制 CPU |
| `TENCLIP_MAX_VIDEO_SEC` | `300` | 视频分析最长秒数（约 5 分钟） |

---

## 通用说明

### 性能模式 `perf_mode`

| 值 | 说明 |
|----|------|
| `eco` | 省显存（默认）：帧数少、分辨率低 |
| `balanced` | 平衡 |
| `quality` | 质量优先，显存占用更高 |

### 提示词档位 `prompt_profile`（仅视频分析）

| 值 | 说明 |
|----|------|
| `default` | 标准教练助手 |
| `compact` | 精简三段式 |
| `step_by_step` | 分步结构化 |
| `step_by_step_v2` | 证据驱动分步 |
| `motion_deep` | 深度动作链分析 |

可通过 `GET /v1/meta` 获取完整列表。

### HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 参数错误（如缺少图片、Base64 无效） |
| 401 | `X-API-Key` 无效或缺失 |
| 403 | `video_path` 不在允许目录下 |
| 404 | 视频文件不存在 |
| 500 | 推理异常 |
| 503 | 模型未就绪或服务未启动 |

### 超时建议

视频分析与多图对话可能耗时 **数十秒～数分钟**（首次加载权重更久）。客户端建议：

- 健康检查：`timeout=10`
- 视频分析：`timeout=600`（10 分钟）
- 多图对话：`timeout=300`（5 分钟）

---

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health` | 否 | 健康检查（同 `/v1/health`） |
| GET | `/v1/health` | 否 | 健康检查 |
| GET | `/v1/meta` | 可选 | 元信息：模式、提示词档位 |
| POST | `/v1/chat` | 可选 | 多图 + 文本 VLM 对话 |
| POST | `/v1/analyze/video` | 可选 | 上传视频，网球动作分析 |
| POST | `/v1/analyze/video/path` | 可选 | 分析服务器本地视频路径 |

---

## GET `/v1/health`

检查服务与模型是否可用。

### 响应示例

```json
{
  "ok": true,
  "service": "tenclip-vlm-api",
  "model_ready": true,
  "backend": "llamafactory",
  "model_path": "/home/user/code/tenclip/model/Qwen2-VL-2B-Instruct",
  "error": ""
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ok` | boolean | 与 `model_ready` 一致 |
| `model_ready` | boolean | 依赖与权重是否就绪 |
| `backend` | string | `llamafactory` 或 `transformers` |
| `model_path` | string | 实际使用的权重路径 |
| `error` | string | 未就绪时的原因 |

### curl

```bash
curl -s http://127.0.0.1:7862/v1/health | jq .
```

---

## GET `/v1/meta`

返回支持的性能模式、提示词档位与视频时长上限。

### 响应示例

```json
{
  "perf_modes": ["eco", "balanced", "quality"],
  "prompt_profiles": [
    "default",
    "compact",
    "step_by_step",
    "step_by_step_v2",
    "motion_deep"
  ],
  "max_video_duration_sec": 300.0,
  "default_perf_mode": "eco"
}
```

### curl

```bash
curl -s http://127.0.0.1:7862/v1/meta
```

---

## POST `/v1/chat`

通用 **多图视觉对话**。输入一张或多张图片（Base64）与用户提示，返回模型生成文本。不包含网球教练专用元信息头，适合自定义 prompt 的模块（如片段分类、OCR 辅助等）。

### 请求头

```
Content-Type: application/json
X-API-Key: <可选，配置了 TENCLIP_VLM_API_KEY 时必填>
```

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | 是 | 用户文本提示 |
| `system_prompt` | string | 否 | 系统提示 |
| `images_base64` | string[] | 是 | 至少 1 张；支持纯 Base64 或 `data:image/png;base64,...` |
| `perf_mode` | string | 否 | `eco` / `balanced` / `quality`，默认 `eco` |
| `max_new_tokens` | integer | 否 | 128～8192；不设则用模式默认 |

### 请求示例

```json
{
  "prompt": "描述图中运动员的挥拍动作，用中文分条回答。",
  "system_prompt": "你是网球教练助手。",
  "images_base64": ["<base64-encoded-image>"],
  "perf_mode": "eco",
  "max_new_tokens": 1024
}
```

### 响应示例

```json
{
  "text": "1. 引拍较充分…\n2. 击球点偏后…",
  "perf_mode": "eco",
  "image_count": 1
}
```

### curl

```bash
IMG_B64=$(base64 -w0 frame.jpg)
curl -s -X POST http://127.0.0.1:7862/v1/chat \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"描述画面中的网球动作\",\"images_base64\":[\"$IMG_B64\"],\"perf_mode\":\"eco\"}"
```

### Python

```python
import base64
import requests

with open("frame.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("ascii")

r = requests.post(
    "http://127.0.0.1:7862/v1/chat",
    json={
        "prompt": "这是网球练习的关键帧，请判断是否在击球。",
        "images_base64": [b64],
        "perf_mode": "eco",
    },
    timeout=300,
)
r.raise_for_status()
print(r.json()["text"])
```

---

## POST `/v1/analyze/video`

上传网球视频，抽帧后由 VLM 生成**动作指导意见**（与小程序「动作分析」、Gradio 同一套 `analyze_tennis_video` 逻辑）。

### 请求头

```
Content-Type: multipart/form-data
X-API-Key: <可选>
```

### 表单字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video` | file | 是 | 视频文件（如 `.mp4`、`.mov`） |
| `perf_mode` | string | 否 | 默认 `eco` |
| `prompt_profile` | string | 否 | 默认 `default` |

### 响应示例

```json
{
  "guidance": "推理后端: LLaMA-Factory …\n\n---\n\n### 动作观察\n…",
  "perf_mode": "eco",
  "prompt_profile": "default"
}
```

`guidance` 格式为：**运行元信息** + `\n\n---\n\n` + **Markdown 正文**（与主应用一致）。

### curl

```bash
curl -s -X POST http://127.0.0.1:7862/v1/analyze/video \
  -F "video=@/path/to/tennis.mp4" \
  -F "perf_mode=eco" \
  -F "prompt_profile=compact"
```

### Python

```python
import requests

with open("tennis.mp4", "rb") as f:
    r = requests.post(
        "http://127.0.0.1:7862/v1/analyze/video",
        files={"video": ("tennis.mp4", f, "video/mp4")},
        data={"perf_mode": "eco", "prompt_profile": "default"},
        timeout=600,
    )
r.raise_for_status()
print(r.json()["guidance"])
```

---

## POST `/v1/analyze/video/path`

分析**服务器上已有**的视频文件（免上传，适合主应用已落盘到 `data/uploads/` 的场景）。

### 安全限制

`video_path` 必须位于以下目录之一（解析后的绝对路径）：

- 仓库 `data/`
- 仓库 `data/uploads/`
- 环境变量 `TENCLIP_UPLOAD_DIR` 指定目录
- 环境变量 `TENCLIP_VLM_API_DATA_ROOT` 指定目录

否则返回 **403**。

### 请求头

```
Content-Type: application/json
X-API-Key: <可选>
```

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video_path` | string | 是 | 服务器本地绝对路径 |
| `perf_mode` | string | 否 | 默认 `eco` |
| `prompt_profile` | string | 否 | 默认 `default` |

### 请求示例

```json
{
  "video_path": "/home/user/code/tenclip/data/uploads/abc123.mp4",
  "perf_mode": "balanced",
  "prompt_profile": "step_by_step"
}
```

### 响应

与 `POST /v1/analyze/video` 相同（`AnalyzeVideoResponse`）。

### curl

```bash
curl -s -X POST http://127.0.0.1:7862/v1/analyze/video/path \
  -H "Content-Type: application/json" \
  -d '{"video_path":"/home/user/code/tenclip/data/uploads/demo.mp4","perf_mode":"eco"}'
```

---

## 错误响应

FastAPI 标准格式：

```json
{
  "detail": "images_base64 至少一张图片"
}
```

常见 `detail`：

| 场景 | detail 示例 |
|------|-------------|
| 未配置密钥却未带头 | `Invalid or missing X-API-Key` |
| chat 无图 | `images_base64 至少一张图片` |
| 路径越权 | `video_path 须在 data/ 或 uploads/ 下…` |
| 文件不存在 | `视频不存在: /path/...` |
| 模型未装 | `未安装推理依赖。至少执行：pip install -r requirements-llm.txt` |
| 推理失败 | `分析失败: <具体异常>` |

---

## 调用示例（仓库内）

```bash
# 健康检查 + 上传分析
python -m subprojects.vlm_api.client_example /path/to/video.mp4
```

环境变量：

```bash
export TENCLIP_VLM_API_BASE=http://127.0.0.1:7862
export TENCLIP_VLM_API_KEY=your-secret   # 若已配置
```

---

## 与主应用接口对比

| 能力 | VLM API `7862` | 主应用 `app.py` `/api/mobile/*` |
|------|----------------|----------------------------------|
| 视频分析（同步） | `POST /v1/analyze/video` | `POST /api/mobile/analyze-video` |
| 视频分析（异步） | 暂无（可后续扩展） | `POST /api/mobile/analyze-video/submit` + 轮询 |
| 多图对话 | `POST /v1/chat` | 暂无 |
| 服务器 path 分析 | `POST /v1/analyze/video/path` | 暂无 |
| 击球剪辑 / 新闻等 | 无 | 有 |

后续可将主应用 `analysis_worker` 改为 HTTP 调用本服务，实现 **Web 与 GPU 推理进程分离**。

---

## 相关文件

| 路径 | 说明 |
|------|------|
| `subprojects/vlm_api/app.py` | FastAPI 路由 |
| `subprojects/vlm_api/schemas.py` | 请求/响应模型 |
| `subprojects/vlm_api/infer.py` | 推理封装 |
| `subprojects/vlm_api/client_example.py` | Python 示例 |
| `scripts/start_vlm_api.sh` | 启动脚本 |
| `services/vlm_tennis.py` | 核心 VLM 逻辑 |
| `subprojects/README.md` | 子项目总览 |
