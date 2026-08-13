const { fetchFeedPage } = require("../../utils/feed_api");
const { LOCAL_DEV } = require("../../utils/config");
const { pickMockCover } = require("../../utils/feed_mock");

const PAGE_SIZE = 6;

Page({
  data: {
    topTabs: ["推荐", "赛事", "教学"],
    activeTab: "推荐",
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

  onShow() {
    const tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) {
      tabBar.updateSelected();
    }
  },

  onPullDownRefresh() {
    this.reload().finally(function () {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    this.loadMore();
  },

  onTopTab(e) {
    var tab = e.currentTarget.dataset.tab;
    if (!tab || tab === this.data.activeTab) return;
    this.setData({ activeTab: tab });
    this.reload();
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
    // 生产环境不向用户暴露 Mock / 数据源调试信息
    if (!LOCAL_DEV) return "";
    var hostHint = "本机库";
    if (source === "api") return "数据源：新闻库 · " + hostHint;
    if (source === "api-empty") return "数据源：新闻库空 · " + hostHint;
    if (source === "mock-fallback") return "数据源：Mock（接口失败）";
    return "数据源：Mock";
  },


  loadMore() {
    var that = this;
    if (that.data.loading || that.data.reachedEnd) {
      return Promise.resolve();
    }
    that.setData({ loading: true });
    return fetchFeedPage({
      tab: that.data.activeTab,
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
          emptyHint = LOCAL_DEV
            ? "新闻库暂无内容。请启动后端并执行新闻抓取。"
            : "暂时没有新内容，稍后再来看看。";
        }
        if (page.source === "mock-fallback" && !left.length && !right.length) {
          emptyHint = LOCAL_DEV
            ? "无法连接本机后端，请启动服务并勾选不校验合法域名。"
            : "网络繁忙，请稍后下拉刷新重试。";
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
    var url =
      String(id).indexOf("note-") === 0
        ? "/pages/note-detail/index?id=" + encodeURIComponent(id)
        : "/pages/feed-detail/index?id=" + encodeURIComponent(id);
    wx.navigateTo({ url: url });
  },
});
