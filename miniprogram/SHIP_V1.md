# 第一版上线检查清单

## 代码侧（已完成）

- [x] `LOCAL_DEV = false`，`PROD_API_BASE_URL = https://api.uchance.tech`
- [x] 中心「+」：发笔记 / 击球剪辑 / 动作分析 / 实时关键点（无「开发中」）
- [x] 发笔记写入服务端 **SQLite**（`data/social.db`），图片在 `data/note_uploads/`
- [x] 笔记出现在「发现」推荐流 + 「我的 · 作品」
- [x] 关注 / 粉丝：关注、取消关注、列表页
- [x] 生产隐藏资讯 Mock 开关与数据源调试文案
- [x] 去掉未使用的定位 permission；关键点入口保留

## 你需要在公众平台完成

1. **服务器域名**（不带 `https://`）  
   `api.uchance.tech` → request / uploadFile / downloadFile

2. **用户隐私保护指引**（必须发布）  
   - 选相册 / 选视频（`chooseMedia`）— 剪辑、分析、发笔记  
   - 摄像头 — 实时关键点  

3. 上传代码 → 体验版真机测：  
   - 发现页加载（含用户笔记）  
   - 发笔记 → 我的作品 / 发现流  
   - 关注与粉丝列表  
   - 击球剪辑 / 动作分析上传  
   - 实时关键点骨架  

4. **服务器**：`git pull` 后重启 `tenclip-api`（新表会在启动时 `init_social_db` 自动建）

5. 提审 → 通过后发布正式版  

## 笔记存储（1.0）

| 项 | 说明 |
|----|------|
| 库 | `data/social.db`（SQLite，与 `news_feed.db` 分开） |
| 表 | `users` / `notes` / `follows` |
| 图片 | `POST /api/social/uploads` → `/static/notes/{key}/n.jpg` |
| 发布 | `POST /api/social/notes` |
| 发现 | `GET /api/news/feed` 在 offset=0 时把最近笔记混入推荐 |

用户 ID v1 存在小程序本地（`tenclip_user_id`），发笔记/关注前会 `upsert` 到服务器。未接微信 `code2session`，换设备会变成新用户。

## 关注 / 粉丝（1.0）

- 「我的」数字点进 `pages/follow-list`（关注 / 粉丝 Tab）
- 他人笔记详情可关注作者
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

1. **对方 AppID**（在微信搜「韵动吧」→ 右上角 ··· → 更多资料 / 或问对方运营）  
2. **可选 path**（没有官方文档时 `path` 留空，只进首页）  
3. **跳转白名单**已添加该 AppID  

配置好后写入 [`utils/court_data.js`](utils/court_data.js) 的 `bookingOptions[].appId`。  
大众点评 / 小红书已有示例 AppID（`getExtSourceJump`），**仍须加入跳转白名单**才可能成功。

未配置 AppID 时，详情页会走电话预约或提示到对应 App 内搜索，避免半成品跳转。

## 已知限制（v1.1）

- 未接微信登录会话（`wx.login` / code2session），用户 ID 随本机存储  
- 预约小程序 AppID 多数仍为空，需运营收集后填入 `court_data.js` 并加白名单  
- 笔记未做审核/举报流  
