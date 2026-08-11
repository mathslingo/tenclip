# Tab Bar 使用指南

## 布局说明

参考小红书 UI 风格，采用 5 项 Tab 栏布局：

```
找球场 | 发现 | + | 分析 | 我的
```

- **找球场** (🎾): 地图搜索附近网球场
- **发现** (▣): 默认首页，网球资讯瀑布流
- **+** (中央操作按钮): 快捷操作入口
- **分析** (◎): 击球剪辑、动作分析等工具
- **我的** (👤): 个人资料、收藏、设置

## 中央操作按钮 (+)

点击中央绿色圆形按钮，弹出快捷操作菜单：
- 发布动态 (开发中)
- 上传视频 (开发中)
- 击球剪辑 → `/pages/stroke-extract/index`
- 动作分析 → `/pages/action-analyze/index`

## 技术实现

### 1. 自定义 Tab Bar

位置：`custom-tab-bar/`

**核心特性：**
- 5 项布局，中央按钮突出显示
- 渐变背景 + 阴影效果
- 响应式高亮状态
- 操作按钮弹出菜单

**关键代码：**

```javascript
// custom-tab-bar/index.js
data: {
  selected: 1, // 默认选中"发现"
  list: [
    { pagePath: "/pages/courts/index", text: "找球场", icon: "🎾", type: "normal" },
    { pagePath: "/pages/feed/index", text: "发现", icon: "▣", type: "normal" },
    { pagePath: "", text: "", icon: "+", type: "action" }, // 中央按钮
    { pagePath: "/pages/analyze/index", text: "分析", icon: "◎", type: "normal" },
    { pagePath: "/pages/me/index", text: "我的", icon: "👤", type: "normal" },
  ],
}
```

### 2. app.json 配置

```json
{
  "tabBar": {
    "custom": true,
    "list": [
      { "pagePath": "pages/courts/index", "text": "找球场" },
      { "pagePath": "pages/feed/index", "text": "发现" },
      { "pagePath": "pages/analyze/index", "text": "分析" },
      { "pagePath": "pages/me/index", "text": "我的" }
    ]
  }
}
```

**注意：** `app.json` 的 `tabBar.list` 需要 4 项（不包括中央操作按钮），但 `custom-tab-bar/index.js` 包含 5 项（含操作按钮）。

### 3. 页面同步 Tab 状态

每个 Tab 页面的 `onShow()` 中调用：

```javascript
onShow() {
  if (this.getTabBar) {
    this.getTabBar().updateSelected();
  }
}
```

**当前已配置：**
- `pages/courts/index.js`
- `pages/feed/index.js`
- `pages/analyze/index.js`
- `pages/me/index.js`

## 样式说明

### 普通 Tab 项

```css
.tab-item {
  flex: 1;
  color: #8a8a8a; /* 未选中 */
}

.tab-item.active {
  color: #13d8a8; /* 选中高亮 */
}
```

### 中央操作按钮

```css
.tab-action {
  position: relative;
  margin-top: -20rpx; /* 上浮效果 */
}

.action-icon {
  width: 100rpx;
  height: 100rpx;
  background: linear-gradient(135deg, #13d8a8 0%, #10b894 100%);
  border-radius: 50%;
  box-shadow: 0 6rpx 20rpx rgba(19, 216, 168, 0.3);
}
```

## 开发者模式

在「我的」页面开启「开发者模式」开关后：
- 「分析」页面显示实时关键点检测入口
- 显示后端服务状态 (API + Pose)
- 显示详细调试信息

## 常见问题

### Q: 为什么 `getTabBar()` 返回 `null`？

**A:** 检查以下几点：
1. `app.json` 的 `tabBar.list` 与 `custom-tab-bar/index.js` 的 `list` 顺序是否一致（忽略操作按钮）
2. 页面是否在 `app.json` 的 `tabBar.list` 中
3. 是否在 `onShow()` 中添加 `if (this.getTabBar)` 判断

### Q: 如何自定义操作菜单？

**A:** 编辑 `custom-tab-bar/index.js` 的 `handleAction()` 方法：

```javascript
handleAction() {
  wx.showActionSheet({
    itemList: ["你的选项1", "你的选项2"],
    success: (res) => {
      if (res.tapIndex === 0) {
        // 处理选项1
      }
    }
  });
}
```

### Q: 如何修改 Tab 图标？

**A:** 修改 `custom-tab-bar/index.js` 的 `data.list` 中的 `icon` 字段，支持：
- Emoji: `"🎾"`, `"▣"`, `"◎"`, `"👤"`
- 图片路径: `"/images/icon.png"`

## 相关文件

- `miniprogram/app.json` - Tab Bar 配置
- `miniprogram/custom-tab-bar/index.js` - Tab Bar 逻辑
- `miniprogram/custom-tab-bar/index.wxml` - Tab Bar 模板
- `miniprogram/custom-tab-bar/index.wxss` - Tab Bar 样式
- `miniprogram/UI_REFACTOR.md` - 整体 UI 重构说明

## 版本历史

- **2026-08-11**: 实现小红书风格 5 项 Tab 栏 + 中央操作按钮
- **2026-08-10**: 初始自定义 Tab Bar (3 项)
