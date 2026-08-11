const app = getApp();
const cfg = require("../../utils/config");

Page({
  data: {
    devMode: false,
    backendStatus: "检查中...",
    poseStatus: "检查中...",
  },

  onLoad(options) {
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

  onGoAnalyze() {
    wx.navigateTo({ url: "/pages/action-analyze/index" });
  },

  onGoPose() {
    wx.navigateTo({ url: "/pages/pose-live/index" });
  },

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
      url: cfg.POSE_HEALTH_URL,
      timeout: 5000,
      success: (res) => {
        const ok =
          res.statusCode === 200 &&
          res.data &&
          (res.data.status === "ok" || res.data.ok === true);
        this.setData({
          poseStatus: ok ? "✓ 正常" : `✗ 异常 ${res.statusCode}`,
        });
      },
      fail: () => {
        this.setData({ poseStatus: "✗ 无法连接" });
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
