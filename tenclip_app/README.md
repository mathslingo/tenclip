# TenniTi Flutter 客户端

对接现有后端 `https://clip.uchanceai.com` 的 `/api/mobile/*`，在 Mac 上用 Flutter + Xcode 真机调试并上传 TestFlight。

## 为什么用 Flutter（相对 Capacitor 套 H5）

- 原生选视频 / 进度条 / 双 Tab，体验接近小程序
- 一套代码可出 **iOS + Android**
- 仍复用现有 FastAPI，不重写算法与队列

仓库里的 `ios-shell/`（Capacitor）可作备选；主推本目录。

## Mac 环境

```bash
# 1) 安装 Flutter：https://docs.flutter.dev/get-started/install/macos
# 2) Xcode + CocoaPods
sudo gem install cocoapods   # 或 brew install cocoapods
flutter doctor
```

`flutter doctor` 里 iOS toolchain 应无红色叉。

## 首次生成平台工程（本仓库只提交了 lib/）

在 Mac：

```bash
cd tenclip/tenclip_app
flutter create . --project-name tenclip_app --org com.uchance
flutter pub get
```

若已有 `ios/`、`android/`，跳过 `flutter create`，只 `flutter pub get`。

## 真机运行

```bash
flutter devices
flutter run -d <你的iPhone>
```

或：

```bash
open ios/Runner.xcworkspace   # 用 Xcode 选 Team 签名后再 Run
```

## 相册权限

`flutter create` 后检查 `ios/Runner/Info.plist` 是否包含：

- `NSPhotoLibraryUsageDescription`
- `NSCameraUsageDescription`
- `NSPhotoLibraryAddUsageDescription`

若没有，加上中文说明（选择/拍摄网球视频用于剪辑与分析）。

## 改 API 地址

编辑 `lib/config.dart`：

```dart
const apiBaseUrl = 'https://clip.uchanceai.com';
// 本机调试可改为 http://Mac局域网IP:7861
```

## 上传 TestFlight

```bash
flutter build ipa
# 或 Xcode：Product → Archive → Distribute → App Store Connect
```

需付费 Apple Developer 账号。

## 当前原型功能

| Tab | 能力 |
|-----|------|
| 击球剪辑 | 选视频 → `stroke-extract/submit` → 轮询 → 打开下载链接 |
| 动作分析 | 选视频 → `analyze-video/submit` → 轮询 → 展示指导正文 |

大文件分片上传可后续按小程序逻辑移植；原型先走单文件 multipart（与 H5 一致）。
