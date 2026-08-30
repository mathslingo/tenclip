# 第一版上线检查清单

## 代码侧（已完成）

- [x] `LOCAL_DEV = false`，`PROD_API_BASE_URL = https://api.uchance.tech`
- [x] 中心「+」：发笔记 / 击球剪辑 / 动作分析 / 实时关键点（无「开发中」）
- [x] 发笔记写入服务端 **SQLite**（`data/social.db`），图片在 `data/note_uploads/`
- [x] 笔记出现在「发现」推荐流 + 「我的 · 作品」
- [x] 关注 / 粉丝：关注、取消关注、列表页
- [x] 生产隐藏资讯 Mock 开关与数据源调试文案
- [x] 去掉未使用的定位 permission；关键点入口保留
- [x] **微信一键登录** + **游客昵称/密码注册登录**（8 位 user_id、昵称唯一）+ 完善资料（网球风格）+ Bearer 会话

## 你需要在公众平台完成

1. **服务器域名**（不带 `https://`）  
   `api.uchance.tech` → request / uploadFile / downloadFile

2. **用户隐私保护指引**（必须发布）  
   - 选相册 / 选视频（`chooseMedia`）— 剪辑、分析、发笔记  
   - 摄像头 — 实时关键点  
   - 头像 / 昵称（完善资料页 `chooseAvatar` / `nickname`）

3. 上传代码 → 体验版真机测：  
   - 微信一键登录 → 首次进完善资料 → 发现页  
   - 发笔记 → 我的作品 / 发现流  
   - 关注与粉丝列表  
   - 击球剪辑 / 动作分析上传  
   - 实时关键点骨架  

4. **服务器**：`git pull` 后配置环境变量并重启 `tenclip-api`（新列/会话表在启动时自动建）

5. 提审 → 通过后发布正式版  

## 微信登录 / 游客登录（1.0）

| 项 | 说明 |
|----|------|
| 库 | `data/social.db`：`users` 含 openid、`password_hash`、网球风格字段、`create_id`；`sessions` 会话 |
| user_id | **8 位数字**（10000000–99999999），微信与**游客注册**均分配 |
| 昵称 | **全局唯一**（大小写不敏感）；注册/改资料强制校验 |
| 微信登录 | `POST /api/auth/wechat/login` body `{ code }` → `{ token, user, is_new }` |
| 游客注册 | `POST /api/auth/guest/register` `{ nickname, password }`（密码 **6 位数字**）→ 建号 + token |
| 游客登录 | `POST /api/auth/guest/login` `{ nickname, password }` → 同一 `user_id` 可重复登录 |
| 昵称检查 | `GET /api/auth/nickname/check?nickname=` |
| 我的 | `GET /api/auth/me` Header `Authorization: Bearer <token>` |
| 完善资料 | `POST /api/auth/profile`（含 `tennis_hand` / `tennis_level` / `tennis_style` / `preferred_surface`） |
| 登出 | `POST /api/auth/logout`（删当前 session；游客可用昵称密码再登） |
| 写操作 | 发笔记 / 关注 / 上传 / 删笔记需 Bearer（以 token 内 user_id 为准） |

「先逛逛」= 无账号浏览态（无 user_id）；发笔记/关注/编辑资料需微信或游客登录。

### 服务器环境变量（推荐 EnvironmentFile）

密钥放 `/etc/tenclip/env`，**不要**写进 systemd unit、不要提交 git：

```bash
sudo mkdir -p /etc/tenclip
sudo cp /root/code/tenclip/scripts/deploy/tenclip.env.example /etc/tenclip/env
sudo nano /etc/tenclip/env   # 填入真实 AppID / Secret（及可选 ADMIN_TOKEN）
sudo chmod 600 /etc/tenclip/env
```

文件内容示例：

```bash
TENCLIP_WECHAT_APPID=wx你的AppID
TENCLIP_WECHAT_SECRET=你的AppSecret
# TENCLIP_ADMIN_TOKEN=随机长串
```

确认 unit 含 `EnvironmentFile=-/etc/tenclip/env`（仓库 `scripts/deploy/tenclip-*.service` 已如此），然后：

```bash
sudo systemctl daemon-reload
sudo systemctl restart tenclip-api
```

本地无真机 code 时可设 `TENCLIP_WECHAT_MOCK=1`（**生产禁止**）。
### 管理接口（运维）

Header：`X-Admin-Token: <TENCLIP_ADMIN_TOKEN>`（或 Bearer 同值）

- `GET /api/admin/users?limit=50` — 用户列表（openid 脱敏）
- `POST /api/admin/users/{user_id}/revoke` — 踢下线（删 sessions）

### 小程序前端

- 登录页：`pages/login` → 微信登录 / **游客注册** / **游客登录** / 先逛逛
- 完善资料：`pages/profile-edit?from=register`（昵称去重 + 网球风格）
- 发笔记、关注、编辑资料：未登录跳登录页；已登录游客可编辑资料


## 找球场 / 场馆库（1.0）

统一库：`data/courts.db`（gitignore；部署时由种子导入）。

| 项 | 说明 |
|----|------|
| 种子 | `data/shanghai_tennis_data.json`（仅导入 `SportsType` 含「网球」且有坐标的记录） |
| 导入 | 启动空库自动导入；或 `python scripts/import_shanghai_courts.py` / `POST /api/courts/import/shanghai` |
| 搜索 | `GET /api/courts/search?lat=&lng=&keyword=&type=&price=&limit=`（包围盒预筛 + 距离排序） |
| 详情 | `GET /api/courts/{id}` |
| 统计 | `GET /api/courts/stats` |
| 小程序 | `court_api.searchCourts` 优先打服务端；失败降级本地 Mock；用户提报仍存本地 Storage |

低延迟要点：SQLite WAL、`lat/lng` 索引、半径包围盒再算距离、默认 `limit≤80`。

## 笔记存储（1.0）

| 项 | 说明 |
|----|------|
| 库 | `data/social.db`（SQLite，与 `news_feed.db` 分开） |
| 表 | `users` / `notes` / `follows` / `sessions` |
| 图片 | `POST /api/social/uploads` → `/static/notes/{key}/n.jpg` |
| 发布 | `POST /api/social/notes`（需登录） |
| 发现 | `GET /api/news/feed` 在 offset=0 时把最近笔记混入推荐 |

## 关注 / 粉丝（1.0）

- 「我的」数字点进 `pages/follow-list`（关注 / 粉丝 Tab）
- 他人笔记详情可关注作者（需登录）
- API：`POST /api/social/follow`、`/unfollow`，`GET /api/social/users/{id}/following|followers`

## 跳转其他小程序（球场预约 / 点评）

球场详情里的「韵动吧 / 久事体育 / 大众点评」**不是 HTTP deep link**，而是微信 **小程序跳小程序**。

### 正确能力：`wx.navigateToMiniProgram`

```js
wx.navigateToMiniProgram({
  appId: "wxXXXXXXXXXXXXXXXX",  // 对方小程序 AppID
  path: "pages/xxx/index?id=1", // 可空：打开对方首页
  extraData: { from: "uchance" },
  envVersion: "release",
});
```

对方 `App.onLaunch` / `onShow` 里用 `options.referrerInfo.extraData` 接收。

### 必须先在公众平台配置

1. 登录 [微信公众平台](https://mp.weixin.qq.com/) → 本小程序  
2. **设置 → 第三方设置 → 跳转其他小程序**（有的账号在「关联设置」）  
3. 把目标 AppID **加入白名单**（有数量上限，需运营号）  
4. 保存后重新上传/发布体验版再测；未配置会失败或弹「未绑定」

对方也可以限制「允许被谁跳入」。两边都开才稳定。

### 和 URL Scheme / URL Link 的区别

| 方式 | 用途 |
|------|------|
| `wx.navigateToMiniProgram` | **小程序内**跳到**另一个小程序**（预约、点评） |
| URL Scheme / URL Link / Short Link | 从短信、浏览器、聊天打开**自己的**小程序 |
| `wx.openEmbeddedMiniProgram` | 半屏嵌入对方小程序（同样要 AppID + 白名单） |

球场预约缺的不是「deep link 字符串」，而是：

1. **对方 AppID**（已知：**韵动吧** `wxd0286fb3b0e39384`；勾勾运动 / 大众点评见 `app.json` 白名单）  
2. **可选 path**（没有官方文档时 `path` 留空，只进首页）  
3. **跳转白名单**已添加该 AppID  

本仓库：`app.json` → `navigateToMiniProgramAppIdList` 已含韵动吧；`court_data.js` / 详情页补丁会填入 `bookingOptions[].appId`。  
公众平台仍须：**设置 → 第三方设置 → 跳转其他小程序** 添加 `wxd0286fb3b0e39384` 后，体验版/正式版才能跳。

配置好后写入 [`utils/court_data.js`](utils/court_data.js) 的 `bookingOptions[].appId`。  
大众点评 / 小红书已有示例 AppID（`getExtSourceJump`），**仍须加入跳转白名单**才可能成功。

未配置 AppID 时，详情页会走电话预约或提示到对应 App 内搜索，避免半成品跳转。

## 已知限制（v1.1）

- 登录前本机生成的旧 `UCxxx` 笔记不会自动合并到微信 openid 账号  
- 预约小程序 AppID 多数仍为空，需运营收集后填入 `court_data.js` 并加白名单  
- 笔记未做审核/举报流  
- 未配 `TENCLIP_WECHAT_APPID/SECRET` 时生产登录不可用  
