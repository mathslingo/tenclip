# UChance 微信小程序

网球社区小程序：找球场、发现资讯/笔记、发场地约球、动作分析 H5、跳转「有场」等。

底栏为自定义 Tab：`找球场 | 发现 | + | 有场 | 我的`（见 `custom-tab-bar/`）。

## 快速链接

- **[第一版上线检查清单](SHIP_V1.md)** — 提审前必做
- **[Tab Bar 使用指南](TABBAR_GUIDE.md)** — 自定义底栏说明
- **[地图模块架构](MAP_MODULE_ARCHITECTURE.md)** — 找球场设计文档
- 仓库根目录 **`readme.md`** — 后端启动与部署

## 当前能力一览

| 模块 | 说明 |
|------|------|
| **发现** | 推荐 / 赛事 / 附近；附近按模糊定位距离排序 |
| **找球场** | 地图 + 列表，本地球场数据；导航/第三方订场 |
| **发布（+）** | 发笔记 / 发场地 / 收场地（场地类必填地点与时间段） |
| **有场** | 跳转合作小程序 `wx915ecf6c01bea4ec` |
| **我的** | 资料、作品/赞/收藏、设置入口 |
| **球场风格** | 温网/法网/澳网/美网四套主题（设置页切换，顶栏/底栏/页面背景同步） |
| **动作分析** | 底栏中间或我的入口进 H5（`/yolo-pose/` 等），主题可带 `theme=` |
| **开发者模式** | 仅 `config/app_config.json` 白名单小程序号可见 |

## 底部 Tab

| 项 | 路径 / 行为 |
|----|-------------|
| 找球场 | `pages/courts/index` |
| 发现 | `pages/feed/index` |
| + | ActionSheet：发笔记 / 发场地 / 收场地 → `pages/note-compose` |
| 有场 | `wx.navigateToMiniProgram`（真机图标暂用 🦔，避免 png 缓存空白） |
| 我的 | `pages/profile/index` |

## 配置

| 文件 | 用途 |
|------|------|
| `utils/config.js` | `LOCAL_DEV`、`API_BASE_URL`、上传阈值、球场主题 `slamTheme` |
| `config/app_config.json` | 前端全局配置：`devModeWhitelist`、`enableFuzzyLocation` |
| `config/publish_limits.json` | 发笔记图片数 / 每日篇数（服务端也读） |
| `app.json` | 页面路由、自定义 tabBar、隐私相关声明 |

**API 基址**：开发 `LOCAL_DEV=true` + `LOCAL_API_HOST`；上线 `LOCAL_DEV=false` + `PROD_API_BASE_URL`（当前多为 `https://api.uchance.tech`）。

## 定位与隐私（重要）

| 能力 | 状态 |
|------|------|
| `wx.getFuzzyLocation` | **使用中** — 找球场、发现「附近」按距离排序；已在 `requiredPrivateInfos` |
| `wx.chooseLocation` | **使用中** — 发笔记 / 发场地地图选点 |
| `wx.getLocation` | **未使用** — 精准定位对「附近推荐」难过审，勿再接入 |

隐私指引需勾选：**收集你的位置信息**（模糊定位）、**收集你选择的位置信息**（选点），以及实际用到的相册/摄像头等项。用途写清「附近球场与内容距离排序」「发布时选择打球地点」。

用户拒绝模糊定位时：找球场回落默认城市；附近仍展示带地点内容（不强制反复弹窗）。

## 快速启动

1. WSL 启动后端：`GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh`（默认 `7861`）  
2. 改 `utils/config.js` 中 `LOCAL_DEV` / `LOCAL_API_HOST`  
3. 微信开发者工具导入本目录 `miniprogram/`  
4. 本地可勾选「不校验合法域名」；真机/上线须配置 HTTPS 合法域名  

## 网页版 / H5

原生请求失败或需浏览器能力时，用 H5：

| 链接 | 功能 |
|------|------|
| `https://api.uchance.tech/web/stroke` | 击球片段提取 |
| `https://api.uchance.tech/web` | 动作分析 |
| `{API}/yolo-pose/` | 姿态 / 球速相关 H5（可带 `mp=1&theme=`） |

小程序内 `web-view` 需配置**业务域名**（个人主体可能不可用）。也可「复制链接」到聊天打开。

## 击球剪辑 / 动作分析 API

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

长任务均为异步提交 + 轮询；大视频自动压缩 / 分片，超时见 `utils/config.js`。

## 真机「选择视频失败」

1. 公众平台 → 用户隐私保护指引 → 勾选相册/选视频/相机相关项并发布  
2. 重新上传体验版；真机首次需同意隐私弹窗  
3. 手机系统允许微信访问相册  

逻辑在 `utils/api.js`（`chooseTennisVideo`）。

## 提审 / 上线

1. 云服务器 HTTPS 部署后端（见 `scripts/deploy/`）  
2. `LOCAL_DEV = false`，填好 `PROD_API_BASE_URL`  
3. 配置 `request` / `uploadFile` / `downloadFile` 合法域名  
4. **真机体验版**测通再提审（审核连不上本机）  

## 找球场

- 页面：`pages/courts/index`、`pages/court-detail/index`  
- 数据：`utils/court_data.js`（Mock + 本地提报）；`utils/court_api.js` 为腾讯地图 POI 备选  
- 订场：详情页 `_doBooking` → `wx.navigateToMiniProgram`（韵动吧 / 勾勾等）；跳转问题用真机预览测，勿信开发者工具 `appid missing`  
- 已知 AppID 见 `app.json` → `navigateToMiniProgramAppIdList`  

更细架构见 [MAP_MODULE_ARCHITECTURE.md](MAP_MODULE_ARCHITECTURE.md)。

## 社交与发布

- 笔记 / 场地：`POST /api/social/notes`；发场地、收场地会在正文打标签，并要求地点 + 起止时间  
- 限额：`config/publish_limits.json`；`GET /api/config/publish-limits`  
- 默认：单篇最多 10 图，每日最多 10 篇（`Asia/Shanghai`）  

## 球场风格（slam）

- 定义与存储：`utils/config.js` → `slamTheme`（`tenclip_slam_theme`）  
- 页面：`slamBehavior` + `page-meta`（`pageStyle` / `slamBg`）  
- 底栏：`custom-tab-bar` 的 `applyTheme`；切换风格后各 Tab `onShow` 会刷新  

## 开发者模式

- 白名单：`config/app_config.json` → `devModeWhitelist`（小程序号）  
- 非白名单账号：设置页 / 我的 不展示开发者开关  

## 注意

- 上传/下载超时默认约 30 分钟；超长视频请用 WiFi 并留在本页  
- Nginx 建议 `client_body_timeout` / `proxy_read_timeout` **1800s**  
- 保存集锦到相册需用户授权  
- 体验版上传版本描述可简写功能点；接口权限未开通时勿把定位 API 打进包  
