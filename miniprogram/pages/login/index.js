const USER_KEY = "tenclip_user_profile";
const AUTH_KEY = "tenclip_auth_done";

Page({
  data: {
    avatarUrl: "",
    nickName: "",
    hasUserInfo: false,
  },

  onLoad() {
    // 如果已完成授权，直接进入
    var app = getApp();
    if (app.isAuthDone && app.isAuthDone()) {
      wx.reLaunch({ url: "/pages/courts/index" });
      return;
    }

    // 检查已缓存的信息
    var profile = this._loadProfile();
    if (profile && profile.avatarUrl && profile.nickName) {
      this.setData({
        avatarUrl: profile.avatarUrl,
        nickName: profile.nickName,
        hasUserInfo: true,
      });
    }
  },

  _loadProfile() {
    try {
      var raw = wx.getStorageSync(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  },

  _saveProfile(profile) {
    wx.setStorageSync(USER_KEY, JSON.stringify(profile));
    wx.setStorageSync(AUTH_KEY, true);
  },

  // ── 微信授权 ──

  onGetUserInfo() {
    var that = this;
    wx.getUserProfile({
      desc: "用于展示您的个人资料与网球数据",
      success: function (res) {
        var info = res.userInfo || {};
        var profile = that._loadProfile() || {};
        profile.avatarUrl = info.avatarUrl || "";
        profile.nickName = info.nickName || "网球爱好者";
        if (!profile.userId) {
          profile.userId = "UC" + Date.now().toString(36).toUpperCase();
        }
        that._saveProfile(profile);
        that.setData({
          avatarUrl: profile.avatarUrl,
          nickName: profile.nickName,
          hasUserInfo: true,
        });
        wx.showToast({ title: "授权成功", icon: "success" });
      },
      fail: function () {
        // 用户取消或拒绝，静默处理
      },
    });
  },

  // ── 进入应用 ──

  onEnter() {
    // 未授权直接进入：清除可能残留的登录状态
    if (!this.data.hasUserInfo) {
      var app = getApp();
      if (app.clearAuth) app.clearAuth();
    }
    wx.reLaunch({ url: "/pages/courts/index" });
  },
});
