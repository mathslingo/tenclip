const {
  getProfile,
  saveProfile,
  statsFromLists,
  getLikedIds,
  getBookmarkedIds,
} = require("../../utils/me_store");
const { listNotes, upsertMe, fetchUser } = require("../../utils/social_api");
const { getUserId } = require("../../utils/user_id");
const { isLoggedIn, requireLogin, fetchMe } = require("../../utils/auth_api");

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
      emptySub: "发一条网球笔记，记录训练与球场瞬间",
      emptyCta: "去发笔记",
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
    activeTab: "works",
    leftList: [],
    rightList: [],
    emptyTitle: "",
    emptySub: "",
    emptyCta: "",
    loggedIn: false,
    tennisLine: "",
  },

  onShow() {
    try {
      if (wx.getStorageSync("tenclip_me_open_works") === "1") {
        wx.removeStorageSync("tenclip_me_open_works");
        this.setData({ activeTab: "works" });
      }
    } catch (e) {}

    this.setData({ loggedIn: isLoggedIn() });

    var that = this;
    if (isLoggedIn()) {
      fetchMe()
        .then(function (u) {
          if (!u) return;
          saveProfile({
            uid: u.user_id,
            nickname: u.nickname,
            avatarUrl: u.avatar_url || "",
            bio: u.bio != null ? u.bio : "",
            tags: Array.isArray(u.tags) ? u.tags : [],
            tennisHand: u.tennis_hand || "",
            tennisLevel: u.tennis_level || "",
            tennisStyle: u.tennis_style || "",
            preferredSurface: u.preferred_surface || "",
            accountType: u.account_type || "",
          });
          that.refreshProfile();
        })
        .catch(function () {});
      upsertMe()
        .then(function (u) {
          if (u) {
            that.setData({
              "stats.following": u.following || 0,
              "stats.followers": u.followers || 0,
            });
          }
        })
        .catch(function () {});
    }

    this.refreshProfile();
    this.loadTabContent(this.data.activeTab);

    const tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) {
      tabBar.updateSelected();
    }
  },

  refreshProfile() {
    var profile = getProfile();
    var uid = getUserId();
    if (uid && (!profile.uid || profile.uid === "10086")) {
      profile = saveProfile({ uid: uid });
    }
    var stats = statsFromLists(profile);
    var letter = (profile.nickname || "U").trim().charAt(0) || "U";
    var likeN = getLikedIds().length;
    var bmN = getBookmarkedIds().length;
    var that = this;
    var tennisBits = [
      profile.tennisHand,
      profile.tennisLevel,
      profile.tennisStyle,
      profile.preferredSurface,
    ].filter(Boolean);
    var tennisLine = tennisBits.length ? tennisBits.join(" · ") : "";

    this.setData({
      profile: profile,
      avatarLetter: letter,
      stats: stats,
      tennisLine: tennisLine,
      tabs: [
        { key: "works", label: "作品", count: 0 },
        { key: "bookmarks", label: "收藏", count: bmN },
        { key: "likes", label: "赞过", count: likeN },
      ],
    });

    if (!uid) return;

    listNotes(uid)
      .then(function (notes) {
        var tabs = that.data.tabs.slice();
        tabs[0] = { key: "works", label: "作品", count: (notes || []).length };
        that.setData({ tabs: tabs });
      })
      .catch(function () {});

    fetchUser(uid)
      .then(function (u) {
        if (!u) return;
        that.setData({
          stats: Object.assign({}, that.data.stats, {
            following: u.following || 0,
            followers: u.followers || 0,
          }),
        });
      })
      .catch(function () {});
  },

  loadTabContent(tab) {
    var that = this;
    var copy = emptyCopy(tab);

    if (tab === "works") {
      var uid = getUserId();
      if (!uid) {
        that.setData(
          Object.assign(
            { leftList: [], rightList: [] },
            {
              emptyTitle: "登录后查看作品",
              emptySub: "微信一键登录后即可发笔记",
              emptyCta: "去登录",
            }
          )
        );
        return;
      }
      listNotes(uid)
        .then(function (notes) {
          if (!notes.length) {
            that.setData(Object.assign({ leftList: [], rightList: [] }, copy));
            return;
          }
          var cols = splitWaterfall(notes);
          that.setData(Object.assign(cols, {
            emptyTitle: "",
            emptySub: "",
            emptyCta: "",
          }));
        })
        .catch(function () {
          that.setData(Object.assign({ leftList: [], rightList: [] }, copy));
        });
      return;
    }

    // bookmarks / likes 暂时使用本地 storage，后续可接服务端
    var ids = tab === "likes" ? getLikedIds() : getBookmarkedIds();
    if (!ids.length) {
      this.setData(Object.assign({ leftList: [], rightList: [] }, copy));
      return;
    }

    var mockItems = ids.map(function (id, i) {
      return {
        id: id,
        title: tab === "likes" ? "赞过的内容" : "收藏的内容",
        cover: "",
        cover_ratio: 1,
        author_initial: "球",
      };
    });
    var cols = splitWaterfall(mockItems);
    this.setData(Object.assign(cols, { emptyTitle: "", emptySub: "", emptyCta: "" }));
  },

  onTab(e) {
    var tab = e.currentTarget.dataset.key;
    if (!tab || tab === this.data.activeTab) return;
    this.setData({ activeTab: tab });
    this.loadTabContent(tab);
  },

  onOpenDetail(e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    var url = String(id).indexOf("note-") === 0
      ? "/pages/note-detail/index?id=" + encodeURIComponent(id)
      : "/pages/feed-detail/index?id=" + encodeURIComponent(id);
    wx.navigateTo({ url: url });
  },

  onCoverError(e) {
    var id = e.currentTarget.dataset.id;
    var col = e.currentTarget.dataset.col;
    var key = col === "right" ? "rightList" : "leftList";
    var list = (this.data[key] || []).map(function (it) {
      if (String(it.id) !== String(id)) return it;
      return Object.assign({}, it, { coverFailed: true });
    });
    var patch = {};
    patch[key] = list;
    this.setData(patch);
  },

  onOpenSettings() {
    wx.navigateTo({ url: "/pages/settings/index" });
  },

  onEditProfile() {
    if (!isLoggedIn()) {
      requireLogin("profile-edit");
      return;
    }
    wx.navigateTo({ url: "/pages/profile-edit/index" });
  },

  onGoStroke() {
    wx.navigateTo({ url: "/pages/stroke-extract/index" });
  },

  // 暂时下线：动作分析
  // onGoAnalyze() {
  //   wx.navigateTo({ url: "/pages/action-analyze/index" });
  // },

  onGoPose() {
    wx.navigateTo({ url: "/pages/pose-realtime/index" });
  },

  onGoFeed() {
    wx.switchTab({ url: "/pages/feed/index" });
  },

  onTapFollowing() {
    wx.navigateTo({
      url: "/pages/follow-list/index?kind=following&user_id=" + encodeURIComponent(getUserId()),
    });
  },

  onTapFollowers() {
    wx.navigateTo({
      url: "/pages/follow-list/index?kind=followers&user_id=" + encodeURIComponent(getUserId()),
    });
  },

  onEmptyCta() {
    if (!isLoggedIn()) {
      requireLogin("profile");
      return;
    }
    wx.switchTab({ url: "/pages/feed/index" });
  },
});
