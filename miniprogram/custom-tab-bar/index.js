Component({
  data: {
    selected: 1,
    list: [
      { pagePath: "/pages/courts/index", text: "找球场", icon: "🎾", type: "normal" },
      { pagePath: "/pages/feed/index", text: "发现", icon: "▣", type: "normal" },
      { pagePath: "", text: "", icon: "+", type: "action" },
      { pagePath: "/pages/analyze/index", text: "分析", icon: "◎", type: "normal" },
      { pagePath: "/pages/profile/index", text: "我的", icon: "👤", type: "normal" },
    ],
  },

  attached() {
    this.updateSelected();
  },

  methods: {
    updateSelected() {
      var pages = getCurrentPages();
      var current = pages[pages.length - 1];
      var route = current ? current.route : "";
      var list = this.data.list;
      var selected = 1;
      list.forEach(function (item, index) {
        if (item.type === "action") {
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

      if (index === this.data.selected) return;
      wx.switchTab({ url: path });
    },

    handleAction() {
      var auth = require("../utils/auth_api");
      wx.showActionSheet({
        itemList: ["发笔记", "击球剪辑", "动作分析", "实时关键点"],
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
            wx.navigateTo({ url: "/pages/action-analyze/index" });
          } else if (tapIndex === 3) {
            wx.navigateTo({ url: "/pages/pose-live/index" });
          }
        },
      });
    },
  },
});
