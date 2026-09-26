const slamBehavior = require("../../behaviors/slam");
const { WEB_POSE_URL } = require("../../utils/config");
const { copyPoseLink } = require("../../utils/web_link");
const slam = require("../../utils/slam_theme");

function themedPoseUrl() {
  return slam.withCourt(WEB_POSE_URL || "");
}

Page({
  behaviors: [slamBehavior],
  data: {
    poseUrl: themedPoseUrl(),
  },

  onShow() {
    this.setData({ poseUrl: themedPoseUrl() });
  },

  onOpenNative() {
    wx.navigateTo({ url: "/pages/pose-yolo/index" });
  },

  onOpenEmbed() {
    var url = themedPoseUrl();
    if (!url) {
      wx.showToast({ title: "未配置地址", icon: "none" });
      return;
    }
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
