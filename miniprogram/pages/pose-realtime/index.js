const { WEB_POSE_URL } = require("../../utils/config");
const { copyPoseLink } = require("../../utils/web_link");

Page({
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
    wx.navigateTo({
      url:
        "/pages/pose-webview/index?url=" +
        encodeURIComponent(WEB_POSE_URL),
    });
  },

  onOpenBrowser() {
    copyPoseLink();
  },

  onCopyOnly() {
    copyPoseLink();
  },
});
