var slam = require("../utils/config").slamTheme;

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
        icon: "🦔",
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
