var slam = require("../utils/config").slamTheme;

// 内联 data URI（源文件 assets/tabbar/uchance-badge.png）：不依赖分包路径和图片缓存
var UCHANCE_BADGE = "data:image/png;base64,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";

function themeData(theme) {
  theme = theme || slam.current();
  return {
    barBg: theme.nav,
    accent: theme.accent,
    accentInk: theme.accentInk,
    actionStyle: "background:" + theme.accent + ";color:" + theme.accentInk + ";",
    activeStyle: "color:" + theme.accent + ";",
  };
}

Component({
  data: Object.assign(
    {
      selected: 1,
    list: [
      { pagePath: "/pages/courts/index", text: "找球场", icon: "📍", type: "normal" },
      { pagePath: "/pages/feed/index", text: "发现", icon: "▣", type: "normal" },
      { pagePath: "", text: "", icon: "", type: "action" },
      {
        pagePath: "",
        text: "有场",
        icon: "◎",
        image: UCHANCE_BADGE,
        type: "mini",
        appId: "wx915ecf6c01bea4ec",
      },
      { pagePath: "/pages/profile/index", text: "我的", icon: "👤", type: "normal" },
    ],
    },
    themeData()
  ),

  lifetimes: {
    attached() {
      this.applyTheme();
      this.updateSelected();
    },
  },

  pageLifetimes: {
    show() {
      this.applyTheme();
      this.updateSelected();
    },
  },

  methods: {
    applyTheme() {
      this.setData(themeData());
    },

    updateSelected() {
      var pages = getCurrentPages();
      var current = pages[pages.length - 1];
      var route = current ? current.route : "";
      var list = this.data.list;
      var selected = 1;
      list.forEach(function (item, index) {
        if (item.type === "action" || item.type === "mini") {
          item.active = false;
          return;
        }
        var itemPath = item.pagePath.replace(/^\//, "");
        item.active = route === itemPath;
        if (item.active) selected = index;
      });
      this.setData({ selected: selected, list: list });
    },

    onTap(e) {
      var index = e.currentTarget.dataset.index;
      var path = e.currentTarget.dataset.path;
      var type = e.currentTarget.dataset.type;

      if (type === "action") {
        this.handleAction();
        return;
      }

      if (type === "mini") {
        wx.navigateToMiniProgram({
          appId: e.currentTarget.dataset.appid,
          envVersion: "release",
          fail: function (err) {
            var msg = (err && err.errMsg) || "";
            if (msg.indexOf("cancel") === -1) {
              wx.showToast({ title: "无法打开有场", icon: "none" });
            }
          },
        });
        return;
      }

      if (index === this.data.selected) return;
      wx.switchTab({ url: path });
    },

    handleAction() {
      var auth = require("../utils/auth_api");
      wx.showActionSheet({
        itemList: ["发笔记", "剪辑视频", "测测球速"],
        success: function (res) {
          var tapIndex = res.tapIndex;
          if (tapIndex === 0) {
            if (!auth.isLoggedIn()) {
              wx.navigateTo({ url: "/pages/login/index" });
              return;
            }
            wx.navigateTo({ url: "/pages/note-compose/index" });
          } else if (tapIndex === 1) {
            wx.navigateTo({ url: "/pages/stroke-extract/index" });
          } else if (tapIndex === 2) {
            require("../utils/config").openPoseTest();
          }
          // 暂时下线：动作分析 → /pages/action-analyze/index
        },
      });
    },
  },
});
