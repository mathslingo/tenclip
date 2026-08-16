const { getNote, deleteNote, follow, unfollow, fetchUser } = require("../../utils/social_api");
const { getUserId } = require("../../utils/user_id");
const { isLoggedIn, requireLogin } = require("../../utils/auth_api");
const { API_BASE_URL } = require("../../utils/config");
const { authHeaders, getToken } = require("../../utils/auth_api");

function formatTime(isoOrTs) {
  if (!isoOrTs) return "";
  var d = typeof isoOrTs === "number" ? new Date(isoOrTs * (isoOrTs < 1e12 ? 1000 : 1)) : new Date(isoOrTs);
  if (isNaN(d.getTime())) return "";
  var y = d.getFullYear();
  var m = ("0" + (d.getMonth() + 1)).slice(-2);
  var day = ("0" + d.getDate()).slice(-2);
  var h = ("0" + d.getHours()).slice(-2);
  var min = ("0" + d.getMinutes()).slice(-2);
  return y + "-" + m + "-" + day + " " + h + ":" + min;
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
  return formatTime(ts);
}

Page({
  data: {
    note: null,
    timeText: "",
    eventTimeText: "",
    canOpenMap: false,
    isMine: false,
    following: false,
    errorText: "",
    comments: [],
    commentText: "",
    submitting: false,
    loggedIn: false,
    liked: false,
    bookmarked: false,
  },

  onLoad(options) {
    var id = options && options.id ? decodeURIComponent(options.id) : "";
    if (!id) {
      this.setData({ errorText: "缺少笔记 id" });
      return;
    }
    this.setData({ loggedIn: isLoggedIn() });
    var that = this;
    var me = getUserId();
    getNote(id)
      .then(function (note) {
        var isMine = String(note.user_id || "") === String(me);
        var canOpenMap =
          typeof note.latitude === "number" &&
          typeof note.longitude === "number" &&
          !isNaN(note.latitude) &&
          !isNaN(note.longitude);
        that.setData({
          note: note,
          timeText: formatTime(note.created_at || note.published_at),
          eventTimeText: formatTime(note.event_at || note.event_at_iso),
          canOpenMap: canOpenMap,
          isMine: isMine,
          liked: note.liked || false,
          bookmarked: note.bookmarked || false,
        });
        if (!isMine && note.user_id) {
          return fetchUser(note.user_id, me).then(function (u) {
            that.setData({ following: !!(u && u.is_following) });
          });
        }
      })
      .then(function () {
        return that.loadComments();
      })
      .catch(function () {
        that.setData({ errorText: "笔记不存在或已删除" });
      });
  },

  onShow() {
    this.setData({ loggedIn: isLoggedIn() });
  },

  loadComments() {
    var that = this;
    var noteId = this.data.note && this.data.note.id;
    if (!noteId) return Promise.resolve();
    
    return new Promise(function (resolve, reject) {
      wx.request({
        url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(noteId) + "/comments?limit=100",
        header: authHeaders(),
        success: function (res) {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            var items = (res.data && res.data.items) || [];
            var comments = items.map(function (c) {
              return Object.assign({}, c, {
                author_initial: String(c.author_name || "球").charAt(0),
                time_text: formatCommentTime(c.created_at),
              });
            });
            that.setData({ comments: comments });
            resolve();
            return;
          }
          reject();
        },
        fail: reject,
      });
    });
  },

  onCommentInput(e) {
    var text = (e.detail && e.detail.value) || "";
    this.setData({ commentText: text });
  },
    if (!text) {
      wx.showToast({ title: "评论不能为空", icon: "none" });
      return;
    }
    if (!isLoggedIn()) {
      requireLogin("comment");
      return;
    }

    var noteId = this.data.note && this.data.note.id;
    if (!noteId) return;

    this.setData({ submitting: true });
    wx.request({
      url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(noteId) + "/comments",
      method: "POST",
      header: authHeaders(),
      data: {
        note_id: noteId,
        body: text,
      },
      timeout: 30000,
      success: function (res) {
        that.setData({ submitting: false });
        if (res.statusCode >= 200 && res.statusCode < 300) {
          that.setData({ commentText: "" });
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

  onDeleteComment(e) {
    var that = this;
    var commentId = e.currentTarget.dataset.id;
    if (!commentId) return;
    
    wx.showModal({
      title: "删除评论",
      content: "确定删除？",
      confirmColor: "#b42318",
      success: function (res) {
        if (!res.confirm) return;
        
        var noteId = that.data.note && that.data.note.id;
        if (!noteId) return;
        
        wx.request({
          url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(noteId) + "/comments/" + encodeURIComponent(commentId),
          method: "DELETE",
          header: authHeaders(),
          success: function (res) {
            if (res.statusCode >= 200 && res.statusCode < 300) {
              wx.showToast({ title: "已删除", icon: "success" });
              that.loadComments();
              return;
            }
            wx.showToast({ title: "删除失败", icon: "none" });
          },
          fail: function () {
            wx.showToast({ title: "网络错误", icon: "none" });
          },
        });
      },
    });
  },

  onRequireLogin() {
    requireLogin("comment");
  },

  onPreview(e) {
    var src = e.currentTarget.dataset.src;
    var urls = (this.data.note && this.data.note.images) || [];
    wx.previewImage({ current: src, urls: urls });
  },

  onOpenAuthor() {
    var note = this.data.note;
    var uid = note && note.user_id;
    if (!uid) return;
    wx.navigateTo({
      url: "/pages/user/index?user_id=" + encodeURIComponent(uid),
    });
  },

  onOpenLocation() {
    var note = this.data.note;
    if (!note || !this.data.canOpenMap) {
      wx.showToast({ title: "暂无精确坐标", icon: "none" });
      return;
    }
    wx.openLocation({
      latitude: note.latitude,
      longitude: note.longitude,
      name: note.location_name || "笔记地点",
      address: note.location_address || "",
      scale: 16,
    });
  },

  onToggleFollow() {
    var note = this.data.note;
    if (!note || this.data.isMine) return;
    if (!isLoggedIn()) {
      requireLogin("follow");
      return;
    }
    var that = this;
    var uid = note.user_id;
    var op = this.data.following ? unfollow(uid) : follow(uid);
    op.then(function (res) {
      that.setData({ following: !!(res && res.following) });
      wx.showToast({
        title: that.data.following ? "已关注" : "已取消关注",
        icon: "none",
      });
    }).catch(function (err) {
      wx.showToast({ title: (err && err.message) || "操作失败", icon: "none" });
    });
  },

  onDelete() {
    var note = this.data.note;
    if (!note) return;
    wx.showModal({
      title: "删除笔记",
      content: "删除后无法恢复，确定吗？",
      confirmColor: "#b42318",
      success: function (res) {
        if (!res.confirm) return;
        deleteNote(note.id || note.note_id)
          .then(function () {
            wx.showToast({ title: "已删除", icon: "success" });
            setTimeout(function () {
              wx.navigateBack({
                fail: function () {
                  wx.switchTab({ url: "/pages/profile/index" });
                },
              });
            }, 400);
          })
          .catch(function (err) {
            wx.showToast({
              title: (err && err.message) || "删除失败",
              icon: "none",
            });
          });
      },
    });
  },

  onToggleLike() {
    var that = this;
    if (!isLoggedIn()) {
      requireLogin();
      return;
    }
    var note = this.data.note;
    if (!note) return;
    
    var noteId = note.id || note.note_id;
    wx.request({
      url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(noteId) + "/like",
      method: "POST",
      header: authHeaders(),
      success: function (res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          var liked = res.data && res.data.liked;
          that.setData({ liked: liked });
          wx.showToast({ title: liked ? "已赞" : "已取消赞", icon: "none" });
        }
      },
      fail: function () {
        wx.showToast({ title: "操作失败", icon: "none" });
      },
    });
  },

  onToggleBookmark() {
    var that = this;
    if (!isLoggedIn()) {
      requireLogin();
      return;
    }
    var note = this.data.note;
    if (!note) return;
    
    var noteId = note.id || note.note_id;
    wx.request({
      url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(noteId) + "/bookmark",
      method: "POST",
      header: authHeaders(),
      success: function (res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          var bookmarked = res.data && res.data.bookmarked;
          that.setData({ bookmarked: bookmarked });
          wx.showToast({ title: bookmarked ? "已收藏" : "已取消收藏", icon: "none" });
        }
      },
      fail: function () {
        wx.showToast({ title: "操作失败", icon: "none" });
      },
    });
  },
});
