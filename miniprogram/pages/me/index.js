const { APP_BUILD_TAG, FEED_USE_MOCK, API_BASE_URL, LOCAL_DEV } = require("../../utils/config");
const {
  getProfile,
  saveProfile,
  statsFromLists,
  getLikedIds,
  getBookmarkedIds,
} = require("../../utils/me_store");
const { getFeedItemById } = require("../../utils/feed_api");

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

function splitWaterfall(items) {
  var left = [];
  var right = [];
  var leftH = 0;
  var rightH = 0;
  (items || []).forEach(function (it) {
    var h = Number(it.cover_ratio) || 1;
    if (leftH <= rightH) {
      left.push(it);
      leftH += h;
    } else {
      right.push(it);
      rightH += h;
    }
  });
  return { leftList: left, rightList: right };
}

function emptyCopy(tab) {
  if (tab === "works") {
    return {
      emptyTitle: "还没有作品",
      emptySub: "上传击球视频，生成你的第一条剪辑",
      emptyCta: "去剪辑",
    };
  }
  if (tab === "likes") {
    return {
      emptyTitle: "还没有赞过",
      emptySub: "在资讯详情里点赞，会出现在这里",
      emptyCta: "去发现",
    };
  }
  return {
    emptyTitle: "还没有收藏",
    emptySub: "收藏感兴趣的网球资讯，方便回看",
    emptyCta: "去发现",
  };
}

Page({
  data: {
    profile: getProfile(),
    avatarLetter: "U",
    stats: { following: 0, followers: 0, likedCollect: 0 },
    tabs: [
      { key: "works", label: "作品", count: 0 },
      { key: "bookmarks", label: "收藏", count: 0 },
      { key: "likes", label: "赞过", count: 0 },
    ],
    activeTab: "bookmarks",
    leftList: [],
    rightList: [],
    emptyTitle: "",
    emptySub: "",
    emptyCta: "",
    showSettings: false,
    devMode: false,
    feedUseMock: !!FEED_USE_MOCK,
    buildTag: APP_BUILD_TAG,
    apiBase: API_BASE_URL,
    localDev: !!LOCAL_DEV,
    editing: false,
    editForm: { nickname: "", bio: "", tagsText: "" },
  },

  onShow() {
    this.refreshProfile();
    this.refreshMockFlag();
    this.refreshDevMode();
    this.loadTabContent(this.data.activeTab);
    const tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) {
      tabBar.updateSelected();
    }
  },

  refreshProfile() {
    var profile = getProfile();
    var stats = statsFromLists(profile);
    var letter = (profile.nickname || "U").trim().charAt(0) || "U";
    var likeN = getLikedIds().length;
    var bmN = getBookmarkedIds().length;
    this.setData({
      profile: profile,
      avatarLetter: letter,
      stats: stats,
      tabs: [
        { key: "works", label: "作品", count: 0 },
        { key: "bookmarks", label: "收藏", count: bmN },
        { key: "likes", label: "赞过", count: likeN },
      ],
    });
  },

  refreshMockFlag() {
    var stored = wx.getStorageSync(MOCK_KEY);
    var useMock;
    if (stored === "" || stored === undefined || stored === null) {
      useMock = !!FEED_USE_MOCK;
    } else {
      useMock = stored === true || stored === "1";
    }
    this.setData({ feedUseMock: !!useMock });
  },

  refreshDevMode() {
    var devMode = wx.getStorageSync("dev_mode") || false;
    this.setData({ devMode: !!devMode });
  },

  loadTabContent(tab) {
    var that = this;
    var copy = emptyCopy(tab);
    if (tab === "works") {
      this.setData(
        Object.assign(
          {
            leftList: [],
            rightList: [],
          },
          copy
        )
      );
      return;
    }
    var ids = tab === "likes" ? getLikedIds() : getBookmarkedIds();
    if (!ids.length) {
      this.setData(
        Object.assign(
          {
            leftList: [],
            rightList: [],
          },
          copy
        )
      );
      return;
    }
    var tasks = ids.slice(0, 40).map(function (id) {
      return getFeedItemById(id).then(function (item) {
        return item || null;
      });
    });
    Promise.all(tasks).then(function (items) {
      var list = items.filter(Boolean).map(function (it) {
        return Object.assign({}, it, { coverFailed: false });
      });
      var cols = splitWaterfall(list);
      that.setData(
        Object.assign(cols, {
          emptyTitle: "",
          emptySub: "",
          emptyCta: "",
        })
      );
    });
  },

  onTab(e) {
    var key = e.currentTarget.dataset.key;
    if (!key || key === this.data.activeTab) return;
    this.setData({ activeTab: key });
    this.loadTabContent(key);
  },

  onToggleSettings() {
    this.setData({ showSettings: !this.data.showSettings });
  },

  onEditProfile() {
    var p = this.data.profile;
    this.setData({
      editing: true,
      editForm: {
        nickname: p.nickname || "",
        bio: p.bio || "",
        tagsText: (p.tags || []).join("，"),
      },
    });
  },

  onCancelEdit() {
    this.setData({ editing: false });
  },

  onEditNick(e) {
    this.setData({ "editForm.nickname": (e.detail && e.detail.value) || "" });
  },

  onEditBio(e) {
    this.setData({ "editForm.bio": (e.detail && e.detail.value) || "" });
  },

  onEditTags(e) {
    this.setData({ "editForm.tagsText": (e.detail && e.detail.value) || "" });
  },

  onSaveEdit() {
    var form = this.data.editForm;
    var nick = String(form.nickname || "").trim() || "网球爱好者";
    var bio = String(form.bio || "").trim();
    var tags = String(form.tagsText || "")
      .split(/[,，\s]+/)
      .map(function (t) {
        return t.trim();
      })
      .filter(Boolean)
      .slice(0, 6);
    saveProfile({ nickname: nick, bio: bio, tags: tags });
    this.setData({ editing: false });
    this.refreshProfile();
    wx.showToast({ title: "已保存", icon: "success" });
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

  onGoStroke() {
    wx.navigateTo({ url: "/pages/stroke-extract/index" });
  },

  onGoAnalyze() {
    wx.navigateTo({ url: "/pages/action-analyze/index" });
  },

  onGoPose() {
    wx.navigateTo({ url: "/pages/pose-detect/index" });
  },

  onGoFeed() {
    wx.redirectTo({ url: "/pages/feed/index" });
  },

  onEmptyCta() {
    if (this.data.activeTab === "works") {
      this.onGoStroke();
    } else {
      this.onGoFeed();
    }
  },

  onOpenDetail(e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({
      url: "/pages/feed-detail/index?id=" + encodeURIComponent(id),
    });
  },

  onCoverError(e) {
    var id = e.currentTarget.dataset.id;
    var col = e.currentTarget.dataset.col;
    var key = col === "right" ? "rightList" : "leftList";
    var list = (this.data[key] || []).slice();
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].id) === String(id)) {
        list[i] = Object.assign({}, list[i], { coverFailed: true });
        break;
      }
    }
    var patch = {};
    patch[key] = list;
    this.setData(patch);
  },

  // ── 登录相关（供地图模块等调用） ──

  onGoLogin() {
    wx.reLaunch({ url: "/pages/login/index" });
  },

  onGetProfile() {
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
      },
    });
  },

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
          wx.reLaunch({ url: "/pages/login/index" });
        }
      },
    });
  },

  noop() {},
});
