const { APP_BUILD_TAG, FEED_USE_MOCK, API_BASE_URL, LOCAL_DEV } = require("../../utils/config");
const { getProfile } = require("../../utils/me_store");
const { isLoggedIn, requireLogin, logout, enterGuest } = require("../../utils/auth_api");

const MOCK_KEY = "tenclip_feed_use_mock";

Page({
  data: {
    loggedIn: false,
    uid: "",
    nickname: "",
    devMode: false,
    feedUseMock: !!FEED_USE_MOCK,
    buildTag: APP_BUILD_TAG,
    apiBase: API_BASE_URL,
    localDev: !!LOCAL_DEV,
  },

  onShow() {
    this.refresh();
  },

  refresh() {
    var profile = getProfile();
    var stored = wx.getStorageSync(MOCK_KEY);
    var useMock =
      stored === "" || stored === undefined || stored === null
        ? !!FEED_USE_MOCK
        : stored === true || stored === "1";
    this.setData({
      loggedIn: isLoggedIn(),
      uid: profile.uid || "",
      nickname: profile.nickname || "",
      devMode: !!(wx.getStorageSync("dev_mode") || false),
      feedUseMock: !!useMock,
    });
  },

  onGoLogin() {
    requireLogin("settings");
  },

  onLogout() {
    var that = this;
    wx.showModal({
      title: "退出登录",
      content: "退出后可用昵称+密码重新登录同一游客账号；也可先逛逛",
      confirmText: "退出",
      confirmColor: "#b42318",
      success: function (res) {
        if (!res.confirm) return;
        logout()
          .catch(function () {})
          .then(function () {
            enterGuest();
            that.refresh();
            wx.showToast({ title: "已退出", icon: "success" });
          });
      },
    });
  },

  onDevModeChange(e) {
    var on = !!(e.detail && e.detail.value);
    wx.setStorageSync("dev_mode", on);
    this.setData({ devMode: on });
    wx.showToast({
      title: on ? "已开启开发者模式" : "已关闭开发者模式",
      icon: "success",
      duration: 1500,
    });
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
});
