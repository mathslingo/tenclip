const { getFeedItemById } = require("../../utils/feed_api");

Page({
  data: {
    item: null,
    coverFailed: false,
    publishedText: "",
    errorText: "",
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
      that.setData({ item: item, publishedText: publishedText });
      wx.setNavigationBarTitle({
        title: item.title ? item.title.slice(0, 12) : "笔记详情",
      });
    });
  },

  onCoverError() {
    this.setData({ coverFailed: true });
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
