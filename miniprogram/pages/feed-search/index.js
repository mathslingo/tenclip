const { searchNotes } = require("../../utils/social_api");

Page({
  data: {
    keyword: "",
    leftList: [],
    rightList: [],
    loading: false,
  },

  onLoad() {
    // nothing
  },

  onInput(e) {
    this.setData({ keyword: (e.detail && e.detail.value) || "" });
  },

  onSearch() {
    var keyword = String(this.data.keyword || "").trim();
    if (!keyword) {
      wx.showToast({ title: "请输入关键词", icon: "none" });
      return;
    }
    this._search(keyword);
  },

  _search(keyword) {
    var that = this;
    this.setData({ loading: true, leftList: [], rightList: [] });
    searchNotes(keyword)
      .then(function (items) {
        var cols = that._split(items || []);
        that.setData({
          leftList: cols.left,
          rightList: cols.right,
          loading: false,
        });
      })
      .catch(function (err) {
        that.setData({ loading: false });
        wx.showToast({
          title: (err && err.message) || "搜索失败",
          icon: "none",
        });
      });
  },

  _split(items) {
    var left = [];
    var right = [];
    var leftH = 0;
    var rightH = 0;
    items.forEach(function (it) {
      var h = Number(it.cover_ratio) || 1;
      if (leftH <= rightH) {
        left.push(it);
        leftH += h;
      } else {
        right.push(it);
        rightH += h;
      }
    });
    return { left: left, right: right };
  },

  onOpenDetail(e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({
      url: "/pages/note-detail/index?id=" + encodeURIComponent(id),
    });
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
});
