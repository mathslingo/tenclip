# TenClip iOS 壳（Capacitor → Xcode）

用现有 H5（`https://clip.uchanceai.com/web/stroke`）套一层原生壳，在 Mac 上用 Xcode 真机调试并上传 TestFlight。

## 前置条件（仅 Mac）

- macOS + [Xcode](https://developer.apple.com/xcode/)（App Store 安装）
- Node.js 20+（`brew install node`）
- Apple ID；要上传 TestFlight / App Store 需 [Apple Developer Program](https://developer.apple.com/programs/)（年费）
- 用数据线连接 iPhone，信任此电脑

## 1. 把仓库弄到 Mac

在 **Windows / 当前机器** 先推送未提交改动（含本目录）：

```bash
cd ~/code/tenclip
git status
git add ios-shell miniprogram app.py services/mobile_chunk_upload.py
# 按需再 add 其它文件，然后 commit / push
git push -u origin HEAD
```

在 **Mac**：

```bash
git clone https://github.com/mathslingo/tenclip.git
cd tenclip
git checkout <你的分支名>   # 例如 feature/v3 或 main
```

也可用 U 盘 / AirDrop 拷整个仓库，但以后仍建议走 git。

## 2. 生成 iOS 工程并打开 Xcode

```bash
cd ios-shell
npm install
npx cap add ios          # 首次；会生成 ios/ 目录
npx cap sync ios
npx cap open ios         # 打开 Xcode
```

若已有 `ios/`，只需：

```bash
npm install && npx cap sync ios && npx cap open ios
```

## 3. Xcode 真机调试

1. 左侧选中 **App** → **Signing & Capabilities**
2. **Team** 选你的 Apple ID / 开发者团队
3. **Bundle Identifier** 保持 `com.uchance.tenclip`（若冲突可改成 `com.你的名字.tenclip`，并同步改 `capacitor.config.json` 的 `appId`）
4. 顶部设备选你的 **iPhone**（不要选模拟器若要测相册上传）
5. 点 Run（▶）

首次真机：iPhone → 设置 → 通用 → VPN与设备管理 → 信任开发者证书。

## 4. 改加载地址（可选）

编辑 `capacitor.config.json`：

| 场景 | `server.url` |
|------|----------------|
| 击球剪辑（默认） | `https://clip.uchanceai.com/web/stroke` |
| 动作分析 | `https://clip.uchanceai.com/web` |
| 本机后端（Mac 与手机同网） | `http://你的Mac局域网IP:7861/web/stroke`（需允许明文，见下） |

改完后：

```bash
npx cap sync ios && npx cap open ios
```

本地 HTTP 需在 Xcode 的 `Info.plist` 增加 ATS 例外，或 Capacitor 配置 `server.cleartext: true`（仅调试）。

## 5. 相册 / 相机权限（上传视频必需）

在 Xcode 打开 `ios/App/App/Info.plist`，增加（若还没有）：

- `NSPhotoLibraryUsageDescription`：选择网球视频用于击球剪辑与动作分析
- `NSCameraUsageDescription`：拍摄网球视频用于分析
- `NSPhotoLibraryAddUsageDescription`：保存剪辑结果到相册

改完重新 Run。

## 6. 上传 TestFlight（「上传」）

1. [App Store Connect](https://appstoreconnect.apple.com) 新建 App（Bundle ID 与 Xcode 一致）
2. Xcode 菜单：**Product → Archive**
3. Organizer → **Distribute App → App Store Connect → Upload**
4. 稍等处理完成后，在 TestFlight 加内部测试员，用 iPhone 安装

免费个人 Apple ID **不能** 上 TestFlight，只能真机调试约 7 天；正式分发需要付费开发者账号。

## 目录说明

```
ios-shell/
  capacitor.config.json   # appId、线上 H5 地址
  www/                    # 离线占位；正式跑线上 URL
  package.json
  ios/                    # 由 `npx cap add ios` 生成（建议提交，或在 Mac 生成）
```

后端与小程序仍在仓库其它目录；本壳只负责「可安装的 iOS 客户端」。服务器部署、分片上传 API 等仍按原 `scripts/deploy/` 流程。
