const { LOCAL_DEV, POSE_API_BASE } = require("../../utils/config");

Page({
  data: {
    poseApi: POSE_API_BASE,
    localDev: LOCAL_DEV,
  },

  onOpenLive() {
    wx.navigateTo({ url: "/pages/pose-live/index" });
  },

  onGoAnalyze() {
    wx.redirectTo({ url: "/pages/action-analyze/index" });
  },
});
