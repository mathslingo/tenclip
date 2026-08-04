const { getFeedItemById } = require("../../utils/feed_api");
const { isLiked, isBookmarked, toggleLike, toggleBookmark } = require("../../utils/me_store");

Page({
  data: {
    item: null,
    coverFailed: false,
    publishedText: "",
    errorText: "",
    liked: false,
    bookmarked: false,
  },

  onLoad(query) {
    var id = (query && query.id) || "";
    if (!id) {
      this.setData({ errorText: "缺少内容 id" });
      return;
    }
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

  onCopyLink() {
    var url = this.data.item && this.data.item.url;
    if (!url) return;
    wx.setClipboardData({
      data: url,
      success: function () {
        wx.showToast({ title: "链接已复制", icon: "success" });
      },
    });
  },

  onGoAnalyze() {
    wx.redirectTo({ url: "/pages/action-analyze/index" });
  },
});
