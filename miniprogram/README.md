# TenniTi 微信小程序

两个底部 Tab，风格与 `pages/front_page`、`pages/video_input` 一致（浅灰底、薄荷绿 Hero、圆角白卡片）。

| Tab | 功能 | API |
|-----|------|-----|
| **击球剪辑** | 上传长视频，剪掉等待/换边，下载击球集锦 MP4 | `/api/mobile/stroke-extract/*` |
| **动作分析** | 上传视频，Qwen2-VL 生成中文动作指导 | `/api/mobile/analyze-video/submit` + 任务轮询 |

完整启动步骤见仓库根目录 **`readme.md` →「微信小程序启动」**。

## 快速步骤

1. WSL 启动主应用：`bash run-wsl.sh`（默认 `7861` 端口）。
2. 修改 `utils/config.js` 中的 `API_BASE_URL`。
3. 微信开发者工具 **导入** 本目录 `miniprogram/`。
4. 本地调试可勾选「不校验合法域名」；真机/上线须配置 HTTPS 合法域名。

## API 一览

**击球剪辑**

| 方法 | 路径 |
|------|------|
| POST | `/api/mobile/stroke-extract/submit` |
| GET | `/api/mobile/stroke-extract/tasks/{task_id}` |
| GET | `/api/mobile/stroke-extract/tasks/{task_id}/download` |

**动作分析**

| 方法 | 路径 |
|------|------|
| POST | `/api/mobile/analyze-video/submit` |
| GET | `/api/mobile/analyze-video/tasks/{task_id}` |

## 真机「选择视频失败」（开发者工具正常）

1. [微信公众平台](https://mp.weixin.qq.com) → **设置** → **基本设置** → **服务内容声明** → **用户隐私保护指引** → 更新。
2. 勾选与 **相册 / 选视频 / 相机** 相关的接口（含 `chooseMedia`）。
3. 填写隐私政策链接（可用简单说明页），提交审核/发布指引。
4. 重新上传体验版；真机首次使用需点 **同意** 隐私弹窗（点「拒绝」会无法选视频）。
5. 若点击后只出现「打开相册…」一直转圈：多为隐私弹窗被挡在后台，切到微信看是否有弹窗；或指引未发布。
5. 手机 **设置 → 微信 → 相册** 权限打开。

选视频**不要**写在 `app.json` 的 `requiredPrivateInfos`（该字段仅用于定位类 API）；在公众平台隐私指引里声明即可。选视频逻辑在 `utils/api.js`（`chooseTennisVideo`）；失败时会弹窗显示 `errMsg`。

## 提审 / 上线（必读）

开发用 `LOCAL_DEV=true` + 本机 `run-wsl.sh`；**微信审核不能连 127.0.0.1**。

1. 将 `app.py` 部署到**有公网 IP 的云服务器**，Nginx 提供 **HTTPS**（见 `scripts/deploy/`）。
2. `config.js` 改为 `LOCAL_DEV = false`，`PROD_API_BASE_URL = "https://api.你的域名"`。
3. 微信公众平台配置 `request` / `uploadFile` / `downloadFile` 合法域名。
4. 用 **真机体验版** 测通后再提审。

详见根目录 `readme.md` →「提交微信审核 / 上线」。

## 注意

- 长任务均为 **异步提交 + 2 秒轮询**；上传/下载超时默认 **10 分钟**（`utils/config.js`）。
- 本地调试：`GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh`，`LOCAL_API_HOST` 填可访问的 IP。
- 动作分析依赖 GPU；击球剪辑主要依赖 `ffmpeg`，可先用 CPU 云机过审。
- 保存集锦到相册需用户授权。
