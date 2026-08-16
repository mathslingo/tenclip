const { getFeedItemById } = require("../../utils/feed_api");
const { isLiked, isBookmarked, toggleLike, toggleBookmark } = require("../../utils/me_store");
const { API_BASE_URL } = require("../../utils/config");
const { authHeaders } = require("../../utils/auth_api");

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
  data: {
    item: null,
    coverFailed: false,
    publishedText: "",
    errorText: "",
    liked: false,
    bookmarked: false,
    comments: [],
  },

  onLoad(query) {
    var id = (query && query.id) || "";
    if (!id) {
      this.setData({ errorText: "缺少内容 id" });
      return;
    }
    this._itemId = id;
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
      that.loadComments();
    });
  },

  loadComments() {
    var that = this;
    var itemId = this._itemId;
    if (!itemId) return;
    
    wx.request({
      url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(itemId) + "/comments?limit=100",
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
        }
      },
      fail: function () {},
    });
  },

  onCoverError() {
    this.setData({ coverFailed: true });
  },

  onToggleLike() {
    var item = this.data.item;
    if (!item) return;
    var res = toggleLike(item.id);
    this.setData({ liked: res.on });
    wx.showToast({ title: res.on ? "已赞" : "已取消赞", icon: "none" });
  },

  onToggleBookmark() {
    var item = this.data.item;
    if (!item) return;
    var res = toggleBookmark(item.id);
    this.setData({ bookmarked: res.on });
    wx.showToast({ title: res.on ? "已收藏" : "已取消收藏", icon: "none" });
  },
});
