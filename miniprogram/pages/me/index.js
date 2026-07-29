const { APP_BUILD_TAG, FEED_USE_MOCK } = require("../../utils/config");

const MOCK_KEY = "tenclip_feed_use_mock";
const USER_KEY = "tenclip_user_profile";
const STATS_KEY = "tenclip_user_stats";

function loadUserProfile() {
  try {
    var raw = wx.getStorageSync(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
}

function saveUserProfile(profile) {
  wx.setStorageSync(USER_KEY, JSON.stringify(profile));
}

function loadStats() {
  try {
    var raw = wx.getStorageSync(STATS_KEY);
    return raw ? JSON.parse(raw) : { clipCount: 0, analyzeCount: 0, points: 0 };
  } catch (e) { return { clipCount: 0, analyzeCount: 0, points: 0 }; }
}

Page({
  data: {
    feedUseMock: !!FEED_USE_MOCK,
    buildTag: APP_BUILD_TAG,

    // 登录状态
    isLoggedIn: false,

    // 用户信息
    hasProfile: false,
    avatarUrl: "",
    nickName: "",
    userId: "",

    // 统计
    points: 0,
    clipCount: 0,
    analyzeCount: 0,
  },

  onShow() {
    var app = getApp();
    var loggedIn = !!(app.isAuthDone && app.isAuthDone());

    var stored = wx.getStorageSync(MOCK_KEY);
    var useMock;
    if (stored === "" || stored === undefined || stored === null) {
      useMock = !!FEED_USE_MOCK;
    } else {
      useMock = stored === true || stored === "1";
    }

    if (loggedIn) {
      var profile = loadUserProfile();
      var stats = loadStats();
      this.setData({
        isLoggedIn: true,
        feedUseMock: !!useMock,
        hasProfile: !!profile,
        avatarUrl: (profile && profile.avatarUrl) || "",
        nickName: (profile && profile.nickName) || "网球爱好者",
        userId: (profile && profile.userId) || "",
        points: stats.points || 0,
        clipCount: stats.clipCount || 0,
        analyzeCount: stats.analyzeCount || 0,
      });
    } else {
      this.setData({
        isLoggedIn: false,
        feedUseMock: !!useMock,
        hasProfile: false,
        avatarUrl: "",
        nickName: "",
        userId: "",
        points: 0,
        clipCount: 0,
        analyzeCount: 0,
      });
    }
  },

  // ── 去登录 ──

  onGoLogin() {
    wx.reLaunch({ url: "/pages/login/index" });
  },

  // ── 获取用户信息 ──

  onGetProfile() {
    if (!this.data.isLoggedIn) return;
    var that = this;
    wx.getUserProfile({
      desc: "用于展示您的个人资料",
      success: function (res) {
        var info = res.userInfo || {};
        var profile = {
          avatarUrl: info.avatarUrl || "",
          nickName: info.nickName || "网球爱好者",
          userId: "UC" + Date.now().toString(36).toUpperCase(),
        };
        var existing = loadUserProfile();
        if (existing && existing.userId) {
          profile.userId = existing.userId;
        }
        saveUserProfile(profile);
        that.setData({
          hasProfile: true,
          avatarUrl: profile.avatarUrl,
          nickName: profile.nickName,
          userId: profile.userId,
        });
        wx.showToast({ title: "已更新资料", icon: "success" });
      },
      fail: function () {
        var profile = {
          avatarUrl: "",
          nickName: "网球爱好者",
          userId: "UC" + Date.now().toString(36).toUpperCase(),
        };
        var existing = loadUserProfile();
        if (existing && existing.userId) {
          profile.userId = existing.userId;
          profile.avatarUrl = existing.avatarUrl;
          profile.nickName = existing.nickName;
        }
        saveUserProfile(profile);
        that.setData({
          hasProfile: true,
          avatarUrl: profile.avatarUrl,
          nickName: profile.nickName,
          userId: profile.userId,
        });
      },
    });
  },

  // ── 编辑昵称 ──

  onEditNickname() {
    if (!this.data.isLoggedIn) return;
    var that = this;
    wx.showModal({
      title: "修改昵称",
      editable: true,
      placeholderText: "请输入新昵称",
      content: that.data.nickName,
      success: function (res) {
        if (res.confirm && res.content) {
          var profile = loadUserProfile() || {};
          profile.nickName = res.content.trim() || "网球爱好者";
          saveUserProfile(profile);
          that.setData({ nickName: profile.nickName });
        }
      },
    });
  },

  // ── 退出登录 ──

  onLogout() {
    var that = this;
    wx.showModal({
      title: "退出登录",
      content: "退出后将返回登录页，积分和统计数据不会丢失。",
      confirmText: "退出",
      confirmColor: "#b42318",
      success: function (res) {
        if (res.confirm) {
          var app = getApp();
          if (app.clearAuth) app.clearAuth();
          that.setData({
            isLoggedIn: false,
            hasProfile: false,
            avatarUrl: "",
            nickName: "",
            userId: "",
            points: 0,
            clipCount: 0,
            analyzeCount: 0,
          });
          wx.reLaunch({ url: "/pages/login/index" });
        }
      },
    });
  },

  // ── Mock 开关 ──

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
