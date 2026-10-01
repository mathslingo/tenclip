const slamBehavior = require("../../utils/config").slamBehavior;
const { getFeedItemById } = require("../../utils/feed_api");
const { isLiked, isBookmarked, toggleLike, toggleBookmark } = require("../../utils/me_store");
const { API_BASE_URL } = require("../../utils/config");
const { authHeaders, isLoggedIn, requireLogin } = require("../../utils/auth_api");
const { FALLBACK_COVER } = require("../../utils/feed_mock");
const {
  isNoteKind,
  sendNewsFeedback,
  toggleNoteLikeRemote,
} = require("../../utils/social_api");
const { nestComments } = require("../../utils/comment_util");

function normalizeNoteId(id) {
  var nid = (id || "").trim();
  if (nid.startsWith("note-")) {
    return nid.substring(5);
  }
  return nid;
}

function formatCommentTime(ts) {
  if (!ts) return "";
  var d = new Date(ts * 1000);
  if (isNaN(d.getTime())) return "";
  var now = new Date();
  var diffMs = now - d;
  var diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return diffMin + "分钟前";
  var diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return diffHour + "小时前";
  var diffDay = Math.floor(diffHour / 24);
  if (diffDay < 30) return diffDay + "天前";
  return String(ts).slice(0, 10);
}

Page({
  behaviors: [slamBehavior],
  data: {
    item: null,
    coverFailed: false,
    publishedText: "",
    errorText: "",
    liked: false,
    bookmarked: false,
    comments: [],
    commentTotal: 0,
    commentText: "",
    replyTo: null,
    commentPlaceholder: "说说你的想法... (最多140字)",
    submitting: false,
    loggedIn: false,
  },

  onLoad(query) {
    var id = (query && query.id) || "";
    if (!id) {
      this.setData({ errorText: "缺少内容 id" });
      return;
    }
    this._itemId = id;
    this.setData({ loggedIn: isLoggedIn() });
    var that = this;
    getFeedItemById(id).then(function (item) {
      if (!item) {
        that.setData({ errorText: "内容不存在或已下线" });
        return;
      }
      var publishedText = "";
      if (item.published_at) {
        try {
          publishedText = String(item.published_at).slice(0, 10);
        } catch (e) {
          publishedText = "";
        }
      }
      that.setData({
        item: item,
        publishedText: publishedText,
        liked: isLiked(item.id),
        bookmarked: isBookmarked(item.id),
      });
      wx.setNavigationBarTitle({
        title: item.title ? item.title.slice(0, 12) : "笔记详情",
      });
      return that.loadComments().catch(function () {});
    }).catch(function () {
      that.setData({ errorText: "加载失败" });
    });
  },

  onShow() {
    this.setData({ loggedIn: isLoggedIn() });
  },

  loadComments() {
    var that = this;
    var itemId = normalizeNoteId(this._itemId);
    if (!itemId) return Promise.resolve();
    
    return new Promise(function (resolve, reject) {
      wx.request({
        url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(itemId) + "/comments?limit=100",
        header: authHeaders(),
        success: function (res) {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            var items = (res.data && res.data.items) || [];
            var nested = nestComments(items, formatCommentTime);
            that.setData({
              comments: nested.comments,
              commentTotal: nested.commentTotal,
            });
            resolve();
            return;
          }
          reject();
        },
        fail: reject,
      });
    });
  },

  onCoverError() {
    var item = this.data.item || {};
    // 先退本地打包图，再退字母块
    if (item.cover && item.cover !== FALLBACK_COVER) {
      this.setData({ "item.cover": FALLBACK_COVER });
      return;
    }
    this.setData({ coverFailed: true });
  },

  onToggleLike() {
    var item = this.data.item;
    if (!item) return;
    if (!isLoggedIn()) {
      requireLogin("like");
      return;
    }
    var that = this;
    var wasLiked = !!this.data.liked;
    var base = Math.max(0, Number(item.like_count) || 0);
    var nextLiked = !wasLiked;
    var nextCount = nextLiked ? base + 1 : Math.max(0, base - 1);
    // 乐观更新展示数
    this.setData({
      liked: nextLiked,
      "item.like_count": nextCount,
    });
    toggleLike(item.id);

    if (isNoteKind(item)) {
      toggleNoteLikeRemote(item.id)
        .then(function (body) {
          var patch = { liked: !!(body && body.liked) };
          if (body && body.like_count != null) {
            patch["item.like_count"] = Math.max(0, Number(body.like_count) || 0);
          }
          that.setData(patch);
        })
        .catch(function () {
          that.setData({
            liked: wasLiked,
            "item.like_count": base,
          });
          wx.showToast({ title: "点赞失败", icon: "none" });
        });
      return;
    }

    sendNewsFeedback(item.id, nextLiked ? "like" : "dislike").catch(function () {
      // 反馈失败不回滚展示，本地状态已更新；列表刷新后会与服务端对齐
    });
  },

  onShareAppMessage() {
    var item = this.data.item || {};
    var id = item.id || this._itemId || "";
    var title = item.title || "UChance 网球笔记";
    return {
      title: title,
      path: "/pages/feed-detail/index?id=" + encodeURIComponent(id),
      imageUrl: item.cover || "",
    };
  },

  onShareTimeline() {
    var item = this.data.item || {};
    return {
      title: item.title || "UChance 网球笔记",
      query: "id=" + encodeURIComponent(item.id || this._itemId || ""),
      imageUrl: item.cover || "",
    };
  },

  onToggleBookmark() {
    var item = this.data.item;
    if (!item) return;
    var res = toggleBookmark(item.id);
    this.setData({ bookmarked: res.on });
    wx.showToast({ title: res.on ? "已收藏" : "已取消收藏", icon: "none" });
  },

  onCommentInput(e) {
    var text = (e.detail && e.detail.value) || "";
    this.setData({ commentText: text });
  },

  onReplyComment(e) {
    if (!isLoggedIn()) {
      requireLogin("comment");
      return;
    }
    var id = e.currentTarget.dataset.id || "";
    var name = e.currentTarget.dataset.name || "球友";
    if (!id) return;
    this.setData({
      replyTo: { id: id, name: name },
      commentPlaceholder: "回复 @" + name + "... (最多140字)",
    });
  },

  onCancelReply() {
    this.setData({
      replyTo: null,
      commentPlaceholder: "说说你的想法... (最多140字)",
    });
  },

  onSubmitComment() {
    var that = this;
    var text = this.data.commentText;
    if (!text) {
      wx.showToast({ title: "评论不能为空", icon: "none" });
      return;
    }
    if (!isLoggedIn()) {
      requireLogin("comment");
      return;
    }

    var itemId = normalizeNoteId(this._itemId);
    if (!itemId) return;

    var replyTo = this.data.replyTo;
    var payload = { body: text };
    if (replyTo && replyTo.id) {
      payload.parent_id = replyTo.id;
    }

    this.setData({ submitting: true });
    wx.request({
      url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(itemId) + "/comments",
      method: "POST",
      header: authHeaders(),
      data: payload,
      timeout: 30000,
      success: function (res) {
        that.setData({ submitting: false });
        if (res.statusCode >= 200 && res.statusCode < 300) {
          that.setData({
            commentText: "",
            replyTo: null,
            commentPlaceholder: "说说你的想法... (最多140字)",
          });
          wx.showToast({ title: "已发送", icon: "success" });
          that.loadComments();
          return;
        }
        var msg = (res.data && res.data.detail) || "发送失败";
        wx.showToast({ title: msg, icon: "none" });
      },
      fail: function () {
        that.setData({ submitting: false });
        wx.showToast({ title: "网络错误", icon: "none" });
      },
    });
  },

  onRequireLogin() {
    requireLogin("comment");
  },
});
