const slamBehavior = require("../../utils/config").slamBehavior;
const { WEB_POSE_URL } = require("../../utils/config");
const { copyPoseLink } = require("../../utils/web_link");

Page({
  behaviors: [slamBehavior],
  data: {
    poseUrl: WEB_POSE_URL || "",
  },

  onOpenNative() {
    wx.navigateTo({ url: "/pages/pose-yolo/index" });
  },

  onOpenEmbed() {
    if (!WEB_POSE_URL) {
      wx.showToast({ title: "未配置地址", icon: "none" });
      return;
    }
    var theme = "wimbledon";
    try {
      var slam = require("../../utils/config").slamTheme;
      theme = (slam.current() && slam.current().id) || theme;
    } catch (e) {}
    var join = WEB_POSE_URL.indexOf("?") >= 0 ? "&" : "?";
    var url = WEB_POSE_URL + join + "theme=" + encodeURIComponent(theme);
    wx.navigateTo({
      url: "/pages/pose-webview/index?url=" + encodeURIComponent(url),
    });
  },

  onOpenBrowser() {
    copyPoseLink();
  },

  onCopyOnly() {
    copyPoseLink();
  },
});
