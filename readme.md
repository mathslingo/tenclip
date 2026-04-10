# TenClip - Tennis Video Clip Tool

一个最小可用的视频剪辑 Web 工具，基于 `Gradio + MoviePy`。  
启动后可在浏览器中上传视频，输入起止秒数，导出并下载剪辑片段。

## 功能说明

- 支持上传：`.mp4`、`.mov`、`.avi`
- 输入开始/结束时间（秒）进行区间剪辑
- 自动处理边界：
  - 开始时间最小为 `0`
  - 结束时间不超过视频总时长
  - 结束时间必须大于开始时间
- 输出为 `.mp4`（`libx264 + aac`）

## 环境要求

- Python `3.10+`
- 推荐系统：Windows 10/11（其他系统也可运行）

依赖见 `requirements.txt`：

- `gradio>=4.0,<6.0`
- `moviepy>=1.0.3`
- `imageio-ffmpeg>=0.4`

## 快速启动（推荐）

双击运行根目录下的 `start.bat` 即可：

- 首次运行会自动创建 `.venv` 虚拟环境
- 自动安装依赖
- 自动启动服务

启动后访问：`http://127.0.0.1:7860`

## 手动启动

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## 基本使用

1. 打开页面并上传视频
2. 输入开始时间和结束时间（秒）
3. 点击执行剪辑
4. 下载输出视频

## 本地测试脚本

- `test_trim.py`：基本裁剪验证
- `test_trim2.py`：裁剪后时长校验
- `test_file_type.py`：检查 Gradio 文件输入类型
- `test_moviepy.py`：检查 MoviePy/ffmpeg 可用性

示例：

```bash
python test_trim2.py
```

## 项目结构

```text
tenclip/
├─ app.py
├─ start.bat
├─ requirements.txt
├─ readme.md
├─ test_trim.py
├─ test_trim2.py
├─ test_file_type.py
├─ test_moviepy.py
└─ old_version/
   └─ app_v1.py
```

## GitHub 上传（命令行）

初始化并推送（已安装 GitHub CLI `gh` 的前提下）：

```bash
git init
git add .
git commit -m "Initial commit: tenclip minimal workable app"
gh repo create tenclip --public --source . --remote origin --push
```

如果 `gh` 提示未登录，先执行：

```bash
gh auth login
```

