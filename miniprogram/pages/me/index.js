const { APP_BUILD_TAG, FEED_USE_MOCK, API_BASE_URL, LOCAL_DEV } = require("../../utils/config");

const MOCK_KEY = "tenclip_feed_use_mock";

Page({
  data: {
    feedUseMock: !!FEED_USE_MOCK,
    buildTag: APP_BUILD_TAG,
    apiBase: API_BASE_URL,
    localDev: !!LOCAL_DEV,
  },

  onShow() {
    var stored = wx.getStorageSync(MOCK_KEY);
    var useMock;
    if (stored === "" || stored === undefined || stored === null) {
      useMock = !!FEED_USE_MOCK;
    } else {
      useMock = stored === true || stored === "1";
    }
    this.setData({ feedUseMock: !!useMock });
  },

  onMockChange(e) {
    var on = !!(e.detail && e.detail.value);
    wx.setStorageSync(MOCK_KEY, on ? "1" : "0");
    this.setData({ feedUseMock: on });
    wx.showToast({
      title: on ? "已开 Mock（需重进发现页）" : "已关 Mock（需重进发现页）",
      icon: "none",
    });
  },

  onGoStroke() {
    wx.redirectTo({ url: "/pages/stroke-extract/index" });
  },

  onGoAnalyze() {
    wx.redirectTo({ url: "/pages/action-analyze/index" });
  },

  onGoFeed() {
    wx.redirectTo({ url: "/pages/feed/index" });
  },
});
