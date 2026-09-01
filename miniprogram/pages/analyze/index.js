const cfg = require("../../utils/config");

Page({
  data: {
    devMode: false,
    backendStatus: "检查中...",
    poseStatus: "检查中...",
  },

  onLoad() {
    const devMode = wx.getStorageSync("dev_mode") || false;
    this.setData({ devMode });
    if (devMode) {
      this.checkBackendStatus();
    }
  },

  onShow() {
    const devMode = wx.getStorageSync("dev_mode") || false;
    this.setData({ devMode });
    const tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) {
      tabBar.updateSelected();
    }
  },

  onGoStroke() {
    wx.navigateTo({ url: "/pages/stroke-extract/index" });
  },

  // 暂时下线：动作分析
  // onGoAnalyze() {
  //   wx.navigateTo({ url: "/pages/action-analyze/index" });
  // },

  /** 实时关键点：引导页（内嵌 + 浏览器） */
  onGoPoseLive() {
    wx.navigateTo({ url: "/pages/pose-realtime/index" });
  },

  // 暂时下线：姿态骨架回放（云端 pose-live）
  // onGoPoseClip() {
  //   wx.navigateTo({ url: "/pages/pose-live/index" });
  // },

  checkBackendStatus() {
    wx.request({
      url: cfg.API_BASE_URL + "/api/mobile/health",
      timeout: 5000,
      success: (res) => {
        this.setData({
          backendStatus: res.statusCode === 200 ? "✓ 正常" : `✗ 错误 ${res.statusCode}`,
        });
      },
      fail: () => {
        this.setData({ backendStatus: "✗ 无法连接" });
      },
    });

    wx.request({
      url: cfg.WEB_POSE_URL,
      method: "HEAD",
      timeout: 5000,
      success: (res) => {
        const ok = res.statusCode >= 200 && res.statusCode < 400;
        this.setData({
          poseStatus: ok ? "✓ YOLO H5 可达" : `✗ HTTP ${res.statusCode}`,
        });
      },
      fail: () => {
        this.setData({ poseStatus: "✗ YOLO H5 无法连接" });
      },
    });
  },

  onTestBackend() {
    wx.showLoading({ title: "测试中..." });
    this.checkBackendStatus();
    setTimeout(() => {
      wx.hideLoading();
      wx.showToast({
        title: "测试完成",
        icon: "success",
        duration: 1500,
      });
    }, 1000);
  },
});
