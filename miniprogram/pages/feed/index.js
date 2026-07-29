const { fetchFeedPage, FALLBACK_COVER } = require("../../utils/feed_api");

const PAGE_SIZE = 6;

Page({
  data: {
    leftList: [],
    rightList: [],
    offset: 0,
    reachedEnd: false,
    loading: false,
    sourceLabel: "",
    emptyHint: "",
  },

  _leftH: 0,
  _rightH: 0,

  onLoad() {
    this.reload();
  },

  onPullDownRefresh() {
    this.reload().finally(function () {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    this.loadMore();
  },

  onTabInfo() {
    // 当前已在资讯
  },

  onTabStroke() {
    wx.redirectTo({ url: "/pages/stroke-extract/index" });
  },

  onTabCoach() {
    wx.redirectTo({ url: "/pages/action-analyze/index" });
  },

  reload() {
    this._leftH = 0;
    this._rightH = 0;
    this.setData({
      leftList: [],
      rightList: [],
      offset: 0,
      reachedEnd: false,
      emptyHint: "",
      sourceLabel: "",
    });
    return this.loadMore();
  },

  _sourceLabel(source) {
    if (source === "api") return "数据源：新闻库";
    if (source === "api-empty") return "数据源：新闻库（空）";
    if (source === "mock-fallback") return "数据源：Mock（接口失败回退）";
    return "数据源：Mock";
  },

  loadMore() {
    var that = this;
    if (that.data.loading || that.data.reachedEnd) {
      return Promise.resolve();
    }
    that.setData({ loading: true });
    return fetchFeedPage({
      tab: "推荐",
      offset: that.data.offset,
      limit: PAGE_SIZE,
    })
      .then(function (page) {
        var left = that.data.leftList.slice();
        var right = that.data.rightList.slice();
        (page.items || []).forEach(function (item) {
          var h = 180 * (item.cover_ratio || 1) + 90;
          if (that._leftH <= that._rightH) {
            left.push(item);
            that._leftH += h;
          } else {
            right.push(item);
            that._rightH += h;
          }
        });
        var emptyHint = "";
        if (
          page.source === "api-empty" &&
          !left.length &&
          !right.length
        ) {
          emptyHint = "新闻库暂无内容。请在后台抓取入库，或到「我」打开 Mock。";
        }
        that.setData({
          leftList: left,
          rightList: right,
          offset: page.nextOffset,
          reachedEnd: page.reachedEnd,
          loading: false,
          sourceLabel: that._sourceLabel(page.source),
          emptyHint: emptyHint,
        });
      })
      .catch(function () {
        that.setData({ loading: false });
      });
  },

  onCoverError(e) {
    var id = e.currentTarget.dataset.id;
    var col = e.currentTarget.dataset.col;
    var key = col === "right" ? "rightList" : "leftList";
    var list = (this.data[key] || []).map(function (it) {
      if (String(it.id) !== String(id)) return it;
      return Object.assign({}, it, { coverFailed: true, cover: FALLBACK_COVER });
    });
    var patch = {};
    patch[key] = list;
    this.setData(patch);
  },

  onOpenDetail(e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({
      url: "/pages/feed-detail/index?id=" + encodeURIComponent(id),
    });
  },
});
