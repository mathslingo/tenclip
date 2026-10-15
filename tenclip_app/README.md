# TenniTi iOS App（Flutter）

由 `miniprogram/`（微信小程序）原样移植的 Flutter 客户端，一套代码出 **iOS + Android**，复用线上 FastAPI 后端 `https://api.uchance.tech`，零后端改动。

## 页面清单（21 页，与小程序一一对应）

| 模块 | 页面 | 小程序来源 |
|------|------|-----------|
| 骨架 | 4 Tab 底栏（找球场/发现/有场/我的）+ 中间网球球发笔记弹层 | app.json tabBar |
| 账户 | login / me / profile-edit / settings / legal | pages/login、me、profile-edit、settings、legal |
| 个人主页 | profile | pages/profile |
| 场地 | courts / court-detail | pages/courts、court-detail |
| 信息流 | feed / feed-search / feed-detail | pages/feed、feed-search、feed-detail |
| 笔记 | note-detail / note-compose | pages/note-detail、note-compose |
| 社交 | user / follow-list / messages | pages/user、follow-list、messages |
| 视频 | stroke-extract / action-analyze | pages/stroke-extract、action-analyze |
| 姿态检测 | pose-tab / pose-webview | 「有场」Tab 内嵌 `$apiBaseUrl/yolo-pose/`（小程序原跳第三方小程序） |

## 目录结构

```
lib/
  config.dart          # API 地址、上传阈值、web 姿态地址
  main.dart            # 路由表、HomeShell 四 Tab、requireLogin()
  theme/slam_theme.dart# 四大满贯主题渐变（温网/法网/澳网/美网）+ 球场水印
  core/                # storage、session、api_client（dio、2MB 分片上传）、video_picker、url_util
  models/models.dart   # FeedItem/Court/SocialUser/NoteComment/AppNotification 等
  api/                 # auth、social、court（含上海 Mock）、feed（含资讯 Mock）、mobile（剪辑/分析轮询）
  state/app_state.dart # 登录态/未读数/定位
  widgets/             # app_tab_bar、common（Avatar/CoverImage/NoteCard/瀑布流/toast 等）
  pages/               # 21 个页面
assets/pic0.png        # 兜底封面
```

## 与小程序的差异（有意为之）

- 登录：`wx.login` → 后端已有昵称+密码体系（`/api/auth/guest/register|login`）
- 「小程序号」改称「用户号」；微信专属能力替换为 iOS 等价物（预约小程序→toast、chooseLocation→geolocator+手动输入、地图→maps.apple.com、分享→share_plus）
- 姿态检测仅 webview 版（跳过原生 pose-detect/pose-live/pose-rtmpose 等 5 页）
- 球场列表/资讯在后端无接口时降级为内置 Mock（与小程序一致）

## Mac 环境

```bash
# 1) 安装 Flutter：https://docs.flutter.dev/get-started/install/macos
# 2) Xcode + CocoaPods
flutter doctor
```

## 首次生成平台工程（本仓库只提交了 lib/）

```bash
cd tenclip/tenclip_app
flutter create . --project-name tenclip_app --org com.uchance
flutter pub get
```

## 真机运行

```bash
flutter devices
flutter run -d <你的iPhone>
# 或 open ios/Runner.xcworkspace 用 Xcode 签名后 Run
```

## 权限（flutter create 后检查 ios/Runner/Info.plist）

- `NSPhotoLibraryUsageDescription` / `NSCameraUsageDescription` / `NSMicrophoneUsageDescription`（选择/拍摄网球视频）
- `NSPhotoLibraryAddUsageDescription`（保存剪辑结果到相册）
- `NSLocationWhenInUseUsageDescription`（附近球场/同城频道）

## 改 API 地址

编辑 `lib/config.dart` 的 `apiBaseUrl`（默认 `https://api.uchance.tech`，本机调试可改为局域网 IP）。

## 上传 TestFlight

```bash
flutter build ipa
# 或 Xcode：Product → Archive → Distribute → App Store Connect
```

需付费 Apple Developer 账号。
