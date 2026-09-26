const slamBehavior = require("../../utils/config").slamBehavior;

Page({
  behaviors: [slamBehavior],

  onShow() {
    var tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) tabBar.updateSelected();
    if (this._skipOpen) {
      this._skipOpen = false;
      return;
    }
    this.openPose();
  },

  openPose() {
    var that = this;
    this._skipOpen = true;
    wx.navigateTo({
      url: "/pages/pose-webview/index",
      fail: function () {
        that._skipOpen = false;
        wx.showToast({ title: "无法打开检测页", icon: "none" });
      },
    });
  },

  onGoHome() {
    wx.switchTab({ url: "/pages/feed/index" });
  },
});
