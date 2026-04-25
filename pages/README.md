# pages

本目录存放各类**独立页面**源码（静态 H5、Gradio 子应用等），与根目录 `app.py` 通过路由挂载对接。

| 目录 | 说明 | 访问路径（服务启动后） |
|------|------|------------------------|
| `front_page/` | 响应式球局列表 + 上传视频（调用 `/api/mobile/*`） | `/web`、`/mobile`（兼容） |
| `video_input/` | Gradio 极简上传页，同一套视频理解逻辑 | `/video_input` |
| `news_page/` | 网坛新闻双列下滑 H5（标签偏好 + 推荐流） | `/news` |

主 TenClip Gradio 界面挂在 **`/gradio`**（根路径 **`/`** 会 **302 跳转到 `/gradio/`**），避免与 `/video_input`、`/web` 等子路径冲突。

静态资源通过 `/web-assets/*`、`/news-assets/*` 提供（见 `app.py`）。
