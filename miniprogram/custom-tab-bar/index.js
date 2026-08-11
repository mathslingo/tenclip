Component({
  data: {
    selected: 1, // Default to "发现" (index 1)
    list: [
      { pagePath: "/pages/courts/index", text: "找球场", icon: "🎾", type: "normal" },
      { pagePath: "/pages/feed/index", text: "发现", icon: "▣", type: "normal" },
      { pagePath: "", text: "", icon: "+", type: "action" }, // Central action button
      { pagePath: "/pages/analyze/index", text: "分析", icon: "◎", type: "normal" },
      { pagePath: "/pages/me/index", text: "我的", icon: "👤", type: "normal" },
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
      var selected = 1; // Default to "发现"
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

      // Handle action button (central + button)
      if (type === "action") {
        this.handleAction();
        return;
      }

      if (index === this.data.selected) return;
      wx.switchTab({ url: path });
    },

    handleAction() {
      // Show action sheet for quick actions
      wx.showActionSheet({
        itemList: ["发布动态", "上传视频", "击球剪辑", "动作分析"],
        success: (res) => {
          var tapIndex = res.tapIndex;
          if (tapIndex === 0) {
            wx.showToast({ title: "发布动态功能开发中", icon: "none" });
          } else if (tapIndex === 1) {
            wx.showToast({ title: "上传视频功能开发中", icon: "none" });
          } else if (tapIndex === 2) {
            wx.navigateTo({ url: "/pages/stroke-extract/index" });
          } else if (tapIndex === 3) {
            wx.navigateTo({ url: "/pages/action-analyze/index" });
          }
        },
      });
    },
  },
});
