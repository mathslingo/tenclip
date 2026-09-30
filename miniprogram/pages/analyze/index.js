const { WEB_POSE_URL, slamTheme } = require("../../utils/config");

function embedUrl() {
  var base = WEB_POSE_URL || "";
  if (!base) return "";
  return slamTheme.withCourt(base);
}

Page({
  onShow() {
    var tabBar = this.getTabBar && this.getTabBar();
    if (tabBar) {
      if (tabBar.applyTheme) tabBar.applyTheme();
      if (tabBar.updateSelected) tabBar.updateSelected();
    }
    if (this._skipOpen) {
      this._skipOpen = false;
      return;
    }
    this.openPose();
  },

  openPose() {
    var url = embedUrl();
    if (!url) return;
    var that = this;
    this._skipOpen = true;
    wx.navigateTo({
      url: "/pages/pose-webview/index?url=" + encodeURIComponent(url),
      fail: function () {
        that._skipOpen = false;
        wx.showToast({ title: "无法打开检测页", icon: "none" });
      },
    });
  },
});
