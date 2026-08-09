const { WEB_POSE_URL, LOCAL_DEV, POSE_API_BASE } = require("../../utils/config");
const { copyPoseLink } = require("../../utils/web_link");

Page({
  data: {
    poseUrl: WEB_POSE_URL,
    poseApi: POSE_API_BASE,
  },

  onOpenLive() {
    wx.navigateTo({ url: "/pages/pose-live/index" });
  },

  onOpenWebview() {
    if (!WEB_POSE_URL) {
      wx.showToast({ title: "未配置检测地址", icon: "none" });
      return;
    }
    wx.showModal({
      title: "H5 摄像头限制",
      content:
        "微信内嵌网页（web-view）多数情况下无法调用摄像头。若仍要打开 H5，仅适合电脑浏览器；手机请用「原生摄像头检测」。",
      confirmText: "仍打开 H5",
      cancelText: "取消",
      success: (res) => {
        if (!res.confirm) return;
        wx.navigateTo({
          url: "/pages/pose-webview/index?url=" + encodeURIComponent(WEB_POSE_URL),
        });
      },
    });
  },

  onCopyLink() {
    copyPoseLink();
  },

  onGoAnalyze() {
    wx.redirectTo({ url: "/pages/action-analyze/index" });
  },
});
