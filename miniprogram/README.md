# TenniTi 微信小程序

两个底部 Tab，风格与 `pages/front_page`、`pages/video_input` 一致（浅灰底、薄荷绿 Hero、圆角白卡片）。

## 快速链接

- **[第一版上线检查清单](SHIP_V1.md)** - 提审前必做
- **[Tab Bar 使用指南](TABBAR_GUIDE.md)** - 小红书风格 5 项 Tab 栏 (找球场|发现|+|分析|我的)
- **[UI 重构说明](UI_REFACTOR.md)** - 开发者模式、分析页面等
- **[地图模块架构](MAP_MODULE_ARCHITECTURE.md)** - 找球场模块设计文档

## 功能模块

| Tab | 功能 | API |
|-----|------|-----|
| **击球剪辑** | 上传长视频，剪掉等待/换边，下载击球集锦 MP4 | `/api/mobile/stroke-extract/*` |
| **动作分析** | 上传视频，Qwen2-VL 生成中文动作指导 | `/api/mobile/analyze-video/submit` + 任务轮询 |
| **实时关键点** | H5 摄像头骨架预览（MediaPipe） | `/web/pose`（入口：分析页 / 我） |
| **网页版** | `web-view` 打开 H5，绕过小程序 Cronet | `/web/stroke`、`/web`、`/web/pose` |

完整启动步骤见仓库根目录 **`readme.md` →「微信小程序启动」**。

## 网页版（web-view / 复制链接）

原生 `wx.request` 失败时，用底部 **「网页版」** Tab。

### 推荐：复制链接（无需业务域名）

1. 网页版 → **复制链接 · 击球片段提取**
2. 粘贴到任意微信聊天并发送
3. 点击链接打开（你已验证此方式可访问 `api.uchance.tech`）

| 链接 | 功能 |
|------|------|
| `https://api.uchance.tech/web/stroke` | 击球片段提取 |
| `https://api.uchance.tech/web` | 动作分析 |
| `{API}/web/pose` | 实时关键点检测（MediaPipe H5） |

### 可选：小程序内 web-view（需业务域名）

在 **开发设置** 里 **「服务器域名」下方** 应有 **「业务域名」** 一块；若整页都没有，常见原因：

- **个人主体**小程序可能不展示/不支持 web-view 业务域名
- **未完成微信认证**（企业/组织认证后才会出现）
- 可试 **接口设置** 标签页里是否有相关入口

配置方式：添加 `https://api.uchance.tech` + 上传校验文件到网站根目录。

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

## 地图模块（找球场）

新增独立的「找球场」Tab（`pages/courts/index`），用于展示上海网球场信息并支持导航/预约。

### 模块架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户层（小程序前端）                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐│
│  │  courts/     │   │ court-detail/│   │ court_data.js +          ││
│  │  找球场列表   │──→│  球场详情     │   │ court_api.js             ││
│  │  （地图+列表）│   │  （预约+评价）│   │  （数据与API）            ││
│  └──────────────┘   └──────────────┘   └──────────────────────────┘│
│         ↑                                          │                │
│         │  点击标记/卡片                              │ 数据查询/缓存     │
│         │                                          ↓                │
│  ┌──────────────┐                         ┌────────────────────────┐│
│  │  wx.openLocation│  外部导航            │  本地 Mock 数据 (50+ 条) ││
│  │  wx.navigateToMiniProgram│  小程序预约   │  腾讯地图 POI（备选）   ││
│  │  wx.makePhoneCall│  电话预约            │  用户提报数据（本地存储）││
│  └──────────────┘                         └────────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│                         与其他模块的关系                              │
├─────────────────────────────────────────────────────────────────────┤
│  • 使用全局用户登录状态：app.js / pages/login/index                  │
│  • 贡献积分写入用户统计：utils/me_store.js                            │
│  • 使用底部导航组件：components/bottom-tabs/index                     │
│  • 图片预览/分享复用微信原生能力                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 页面说明

| 页面 | 文件 | 职责 |
|------|------|------|
| 找球场 | `pages/courts/index` | 地图展示、列表、搜索、筛选、提报入口 |
| 球场详情 | `pages/court-detail/index` | 大图轮播、信息、设施、导航、预约、分享 |
| 登录 | `pages/login/index` | 提报球场前校验登录状态 |

### 数据层说明

| 文件 | 职责 | 调用关系 |
|------|------|----------|
| `utils/court_data.js` | 50+ 条上海网球场 Mock 数据；规范化、缓存、距离计算、评分星星 | 被 `courts/index` 和 `court-detail/index` 直接引用 |
| `utils/court_api.js` | 腾讯地图 POI 搜索；失败时降级到 `court_data.js` | 导出 `searchCourts` 供业务调用，当前 `courts/index` 未使用，可后续接入 |
| 本地 Storage | 用户提报球场（`tenclip_user_courts`）和用户积分（`tenclip_user_stats`） | 由 `courts/index.js` 读写 |

### 核心交互逻辑

1. **球场列表加载**：`courts/index` 的 `_loadCourts` 合并本地 Mock 数据 + 用户提报数据，按距离/价格筛选，生成地图 markers。
2. **标记点击**：`onMarkerTap` 高亮列表卡片并移动地图到目标位置。
3. **卡片点击**：`onCourtTap` 跳转到 `court-detail` 并传入 `id`。
4. **提报球场**：`onShowForm` 先检查登录，未登录则跳转 `login` 页；提交后奖励 100 积分。
5. **预定渠道**：详情页根据 `bookingOptions` 类型分发到电话、小程序或 Web 提示。
6. **外部评价**：`onExtSource` 跳转大众点评/小红书小程序搜索关键词。

### 跳转第三方订场小程序（韵动吧 / 勾勾运动）

实现位置：`pages/court-detail/index.js` 的 `_doBooking`。当前约定：

- 主按钮统一 `bindtap` → `_doBooking`（**不要**混用 `button open-type="navigateToMiniProgram"` 与 API，两套路径行为不一致，难排查）。
- 有 `shortLink` 时**优先** `wx.navigateToMiniProgram({ shortLink })`，失败再降级 `appId`。
- 仅有 `appId` 时走 `wx.navigateToMiniProgram({ appId, envVersion: "release" })`；空 `path` 不要传该字段；`path` 去掉前导 `/`。
- 已知 AppID：韵动吧 `wxd0286fb3b0e39384`（已用对方「更多资料」核对）；勾勾运动用 shortLink `#小程序://勾勾运动/...`。

#### 之前不行、后来能跳的原因（排查结论）

| 现象 | 真实原因 | 误判点 |
|------|----------|--------|
| 开发者工具报 `navigateToMiniProgram:fail appid missing` | **模拟器不会真实打开**其他小程序，常误报；日志里 `platform: "devtools"` 时不能当真 | 以为业务没传 AppID；其实 `callArgs.appId` 已是正确值 |
| 真机一度「没反应」/ 勾勾也挂 | 主按钮改成 `open-type` 后，有 shortLink 的渠道（勾勾）丢了 API 兜底；跳转路径分裂 | 以为是「全局 AppID 配置坏了」 |
| 真机报 `fail cancel`，AppID 却正确 | 微信会先弹「即将打开 xxx」确认框；点取消 / 弹窗被盖住 / 真机调试分心 → `cancel`。韵动吧官方 AppID 已核对无误 | 以为 AppID 写错或小程序下架 |
| 韵动吧最终能进主页 | 统一走与勾勾相同的 **tap → `wx.navigateToMiniProgram`（appId）**；用**预览扫码**测，在确认框点「允许」 | — |

**调试建议**：跳转类问题只用「预览 / 体验版」真机测；看 `[book-jump]` 日志时先看 `platform` 与 `errMsg`（`appid missing` vs `cancel` vs `invalid appId` 含义完全不同）。若某渠道只有 appId 仍不稳，到对方小程序「··· → 复制链接」配 `shortLink`。

### 配置要点

- 地图能力：需在 `app.json` 中声明 `permission` 字段（如使用 `getLocation`），并配置腾讯地图 Key 到 `utils/config.js` 的 `TENCENT_MAP_KEY`。
- 当前 `courts/index` 直接读取本地 Mock，未调用 `court_api.js`；如想启用真实 POI，将 `_loadCourts` 中的 `courtData.fetchNearbyCourts` 替换为 `courtApi.searchCourts` 即可。
- `app.json` 的 `navigateToMiniProgramAppIdList` 可保留目标 AppID（2020 后官方已不强制校验，但留着无害）。

## 注意

- 长任务均为 **异步提交 + 2 秒轮询**；上传/下载超时默认 **10 分钟**（`utils/config.js`）。
- 本地调试：`GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh`，`LOCAL_API_HOST` 填可访问的 IP。
- 动作分析依赖 GPU；击球剪辑主要依赖 `ffmpeg`，可先用 CPU 云机过审。
- 保存集锦到相册需用户授权。
