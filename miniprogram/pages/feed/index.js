const { fetchFeedPage } = require("../../utils/feed_api");
const { API_BASE_URL, LOCAL_DEV } = require("../../utils/config");
const { pickMockCover } = require("../../utils/feed_mock");

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
    var hostHint = LOCAL_DEV ? "本机库" : "线上";
    if (source === "api") return "数据源：新闻库 · " + hostHint;
    if (source === "api-empty") return "数据源：新闻库空 · " + hostHint + " · " + API_BASE_URL;
    if (source === "mock-fallback") return "数据源：Mock（接口失败 · " + API_BASE_URL + "）";
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
        // 按推荐序交替落入左右列：阅读顺序为 1→2→3→4…（左上=最高分）
        var base = left.length + right.length;
        (page.items || []).forEach(function (item, i) {
          if ((base + i) % 2 === 0) {
            left.push(item);
          } else {
            right.push(item);
          }
        });
        var emptyHint = "";
        if (
          page.source === "api-empty" &&
          !left.length &&
          !right.length
        ) {
          emptyHint =
            "新闻库暂无内容。请在 WSL 启动后端并执行 python -m tennis_news.ingest，或到「我」打开 Mock。";
        }
        if (page.source === "mock-fallback" && !left.length && !right.length) {
          emptyHint = "无法连接 " + API_BASE_URL + "，请启动 run-wsl.sh 并勾选不校验合法域名。";
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
      var mock = pickMockCover(it.id);
      return Object.assign({}, it, {
        coverFailed: false,
        cover: mock.url,
        cover_ratio: mock.ratio,
        cover_is_mock: true,
      });
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
