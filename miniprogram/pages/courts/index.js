var courtData = require("../../utils/court_data");

var SH_LAT = 31.23;
var SH_LNG = 121.47;

var STATS_KEY = "tenclip_user_stats";

function addStats(delta) {
  try {
    var raw = wx.getStorageSync(STATS_KEY);
    var stats = raw ? JSON.parse(raw) : { clipCount: 0, analyzeCount: 0, points: 0 };
    if (delta.clipCount) stats.clipCount = (stats.clipCount || 0) + delta.clipCount;
    if (delta.analyzeCount) stats.analyzeCount = (stats.analyzeCount || 0) + delta.analyzeCount;
    if (delta.points) stats.points = (stats.points || 0) + delta.points;
    wx.setStorageSync(STATS_KEY, JSON.stringify(stats));
  } catch (e) {}
}

var PRICE_RANGES = [
  { key: "all", label: "全部" },
  { key: "free", label: "免费" },
  { key: "0-60", label: "60以下" },
  { key: "60-120", label: "60-120" },
  { key: "120-200", label: "120-200" },
  { key: "200+", label: "200以上" },
];

var SORT_OPTIONS = [
  { key: "default", label: "默认排序" },
  { key: "distance", label: "距离最近" },
];

var USER_COURTS_KEY = "tenclip_user_courts";

function loadUserCourts() {
  try {
    var raw = wx.getStorageSync(USER_COURTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) { return []; }
}

Page({
  data: {
    markers: [],
    scale: 11,

    topTabs: [
      { key: "all", label: "全部" },
      { key: "filter", label: "筛选" },
    ],
    activeTab: "all",

    filterCourtType: "all",
    filterPrice: "all",
    sortBy: "default",
    priceOptions: PRICE_RANGES,
    sortOptions: SORT_OPTIONS,
    mapCenter: { lat: SH_LAT, lng: SH_LNG },
    searchKeyword: "",

    courts: [],
    showForm: false,
  },

  _mapCtx: null,

  onLoad: function () {
    this._mapCtx = wx.createMapContext("courtMap", this);
    this._loadCourts();
  },

  // ── Tab ──

  onTabTap: function (e) {
    var key = e.currentTarget.dataset.key;
    if (key === "all") {
      this.setData({
        activeTab: "all",
        filterCourtType: "all",
        filterPrice: "all",
        sortBy: "default",
        searchKeyword: "",
      });
      this._loadCourts();
      return;
    }
    this.setData({ activeTab: key });
  },

  // ── 加载球场 ──

  _loadCourts: function () {
    var that = this;
    var center = that.data.mapCenter;

    // 直接用本地数据（31条真实信息），POI 作为补充
    var result = courtData.fetchNearbyCourts({
      lat: center.lat,
      lng: center.lng,
      filter: that.data.filterCourtType,
      keyword: that.data.searchKeyword || "",
    });
    var courts = result.courts;

    // 合并用户提报
    var userCourts = loadUserCourts().map(function (c) {
      var n = courtData.normalizeCourt(c);
      n.isUserCourt = true;
      return n;
    });

    var all = courts.concat(userCourts);

    // 价格筛选
    if (that.data.filterPrice !== "all") {
      var pk = that.data.filterPrice;
      if (pk === "free") {
        all = all.filter(function (c) { return c.priceRange.indexOf("免费") !== -1; });
      } else if (pk !== "all") {
        all = all.filter(function (c) {
          var low = parseInt(c.priceRange, 10) || 0;
          if (pk === "0-60") return low <= 60;
          if (pk === "60-120") return low > 60 && low <= 120;
          if (pk === "120-200") return low > 120 && low <= 200;
          if (pk === "200+") return low > 200;
          return true;
        });
      }
    }

    // 距离排序
    if (that.data.sortBy === "distance") {
      all.sort(function (a, b) { return (a.distance||0) - (b.distance||0); });
    }

    // 缓存供详情页查询
    courtData.cacheCourts(all);

    var markers = courtData.toMarkers(all);
    that.setData({ courts: all, markers: markers, loading: false });

    // 自动缩放包含所有标记
    if (markers.length > 0) {
      this._mapCtx.includePoints({
        points: all.map(function (c) { return { latitude: c.lat, longitude: c.lng }; }),
        padding: [40, 40, 40, 40],
      });
    }
  },

  // ── 地图拖动 ──

  onRegionChange: function (e) {
    if (e.type === "end" && e.detail && e.detail.centerLocation) {
      this.setData({
        mapCenter: {
          lat: e.detail.centerLocation.latitude,
          lng: e.detail.centerLocation.longitude,
        },
      });
    }
  },

  // ── 筛选 ──

  onTypeFilter: function (e) {
    var key = e.currentTarget.dataset.key;
    if (key === this.data.filterCourtType) return;
    this.setData({ filterCourtType: key });
    this._loadCourts();
  },

  onPriceFilter: function (e) {
    var key = e.currentTarget.dataset.key;
    if (key === this.data.filterPrice) return;
    this.setData({ filterPrice: key });
    this._loadCourts();
  },

  onSortChange: function (e) {
    var key = e.currentTarget.dataset.key;
    if (key === this.data.sortBy) return;
    this.setData({ sortBy: key });
    this._loadCourts();
  },

  // ── 搜索 ──

  onSearchInput: function (e) {
    this.setData({ searchKeyword: e.detail.value });
  },

  onSearchConfirm: function () { this._loadCourts(); },

  onClearSearch: function () {
    this.setData({ searchKeyword: "" });
    this._loadCourts();
  },

  // ── 地图 ──

  onMarkerTap: function (e) {
    var markerId = e.detail.markerId;
    var court = this.data.courts[markerId];
    if (!court) return;
    this.setData({ highlightId: court.id });
    this._mapCtx.moveToLocation({ latitude: court.lat, longitude: court.lng });
    var that = this;
    setTimeout(function () { that.setData({ highlightId: "" }); }, 1500);
  },

  // ── 卡片 ──

  onCourtTap: function (e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: "/pages/court-detail/index?id=" + encodeURIComponent(id) });
  },

  onNavigateTap: function (e) {
    var index = e.currentTarget.dataset.index;
    var court = this.data.courts[index];
    if (!court) return;
    wx.openLocation({
      latitude: court.lat, longitude: court.lng,
      name: court.name, address: court.address, scale: 16,
    });
  },

  // ── 提报 ──

  onShowForm: function () {
    // 检查登录
    var app = getApp();
    if (!(app.isAuthDone && app.isAuthDone())) {
      wx.showModal({
        title: "请先登录",
        content: "登录后才能提报新球场",
        confirmText: "去登录",
        success: function (res) {
          if (res.confirm) {
            wx.reLaunch({ url: "/pages/login/index" });
          }
        },
      });
      return;
    }
    this.setData({ showForm: true });
  },
  onHideForm: function () { this.setData({ showForm: false }); },

  onFormSubmit: function (e) {
    var data = e.detail.value;
    if (!data.name || !data.address) {
      wx.showToast({ title: "请填写球场名称和地址", icon: "none" });
      return;
    }
    var userCourts = loadUserCourts();
    userCourts.push({
      id: "user-" + Date.now(),
      name: data.name,
      lat: 31.23, lng: 121.47,
      address: data.address,
      rating: 0,
      priceRange: data.price || "暂无",
      indoorCourts: parseInt(data.indoor, 10) || 0,
      outdoorCourts: parseInt(data.outdoor, 10) || 0,
      facilities: (data.facilities || "").split("、").filter(Boolean),
      photos: [],
      phone: data.phone || "",
      hours: data.hours || "",
      bookingOptions: [],
      extSources: [],
    });
    wx.setStorageSync(USER_COURTS_KEY, JSON.stringify(userCourts));
    this.setData({ showForm: false });
    wx.showToast({ title: "感谢提报！积分+100", icon: "success" });
    addStats({ points: 100 });
    this._loadCourts();
  },
});
