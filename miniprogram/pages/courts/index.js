var courtData = require("../../utils/court_data");
var courtApi = require("../../utils/court_api");

var SH_LAT = 31.23;
var SH_LNG = 121.47;
/** 每页条数；默认只拉一页，下滑再加载 */
var PAGE_SIZE = 10;
/** 仅前 N 条渲染封面（与首屏页大小一致） */
var COVER_LIMIT = 10;

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
  } catch (e) {
    return [];
  }
}

function toListItem(c, index) {
  var showCover = index < COVER_LIMIT && c.cover && !c.coverFailed;
  return {
    id: c.id,
    name: c.name,
    lat: c.lat,
    lng: c.lng,
    address: c.address,
    distanceText: c.distanceText,
    priceRange: c.priceRange,
    courtType: c.courtType,
    totalCourts: c.totalCourts,
    phone: c.phone,
    isUserCourt: !!c.isUserCourt,
    cover: showCover ? c.cover : "",
    coverFailed: !!c.coverFailed,
  };
}

Page({
  data: {
    markers: [],
    scale: 13,
    mapLat: SH_LAT,
    mapLng: SH_LNG,
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
    userLat: SH_LAT,
    userLng: SH_LNG,
    hasUserLocation: false,
    searchKeyword: "",
    courts: [],
    showForm: false,
    loading: true,
    loadingMore: false,
    hasMore: true,
    listTotal: 0,
  },

  _mapCtx: null,
  _locating: false,
  _reqSeq: 0,
  _fullCourts: [],
  _loadingMoreLock: false,

  onLoad: function () {
    this._mapCtx = wx.createMapContext("courtMap", this);
    this._loadCourts({ reset: true });
    this._ensureLocationThenLoad(true);
  },

  onShow: function () {
    const tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) {
      tabBar.updateSelected();
    }
  },

  _ensureLocationThenLoad: function (moveMap) {
    var that = this;
    if (this.data.hasUserLocation && !moveMap) {
      this._loadCourts({ reset: true });
      return;
    }
    if (this._locating) return;
    this._locating = true;

    wx.getLocation({
      type: "gcj02",
      success: function (res) {
        that._locating = false;
        var lat = Number(res.latitude) || SH_LAT;
        var lng = Number(res.longitude) || SH_LNG;
        var patch = { userLat: lat, userLng: lng, hasUserLocation: true };
        if (moveMap) {
          patch.mapLat = lat;
          patch.mapLng = lng;
        }
        that.setData(patch);
        that._loadCourts({ reset: true });
      },
      fail: function () {
        that._locating = false;
        that.setData({ hasUserLocation: false });
      },
    });
  },

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
      this._loadCourts({ reset: true });
      return;
    }
    this.setData({ activeTab: key });
  },

  /**
   * @param {{ reset?: boolean }} opts
   */
  _loadCourts: function (opts) {
    opts = opts || {};
    var reset = !!opts.reset;
    var that = this;
    var lat = that.data.userLat;
    var lng = that.data.userLng;

    if (!reset) {
      if (!that.data.hasMore || that._loadingMoreLock || that.data.loading) return;
      that._loadingMoreLock = true;
      that.setData({ loadingMore: true });
    } else {
      that._loadingMoreLock = false;
      that.setData({ loading: true, hasMore: true, loadingMore: false });
    }

    var offset = reset ? 0 : (that._fullCourts || []).length;
    var seq = ++that._reqSeq;

    courtApi
      .searchCourts({
        lat: lat,
        lng: lng,
        filter: that.data.filterCourtType,
        price: that.data.filterPrice,
        keyword: that.data.searchKeyword || "",
        limit: PAGE_SIZE,
        offset: offset,
        radius_m: 25000,
      })
      .then(function (result) {
        if (seq !== that._reqSeq) return;

        var page = (result && result.courts) || [];
        var total = Number((result && result.total) || 0);

        var merged;
        if (reset) {
          // 用户提报只在首屏拼一次
          var userCourts = loadUserCourts().map(function (c) {
            var n = courtData.normalizeCourt(c);
            n.isUserCourt = true;
            if (n.lat && n.lng) {
              n.distance = courtData.calcDistance(lat, lng, n.lat, n.lng);
              n.distanceText = courtData.formatDistance(n.distance);
            }
            return n;
          });
          merged = page.concat(userCourts);
          if (that.data.sortBy === "distance") {
            merged.sort(function (a, b) {
              var da = a.distance != null && a.distance > 0 ? a.distance : 1e18;
              var db = b.distance != null && b.distance > 0 ? b.distance : 1e18;
              return da - db;
            });
          }
        } else {
          // 追加：去重
          var seen = {};
          (that._fullCourts || []).forEach(function (c) {
            seen[String(c.id)] = true;
          });
          var append = page.filter(function (c) {
            return !seen[String(c.id)];
          });
          merged = (that._fullCourts || []).concat(append);
        }

        that._fullCourts = merged;
        courtData.cacheCourts(merged);

        var hasMore = merged.length < total || page.length >= PAGE_SIZE;
        // 服务端 total 更准
        if (total > 0) {
          hasMore = offset + page.length < total;
        } else {
          hasMore = page.length >= PAGE_SIZE;
        }

        that._loadingMoreLock = false;
        that.setData({
          courts: merged.map(toListItem),
          markers: [],
          loading: false,
          loadingMore: false,
          hasMore: hasMore,
          listTotal: total || merged.length,
        });
      })
      .catch(function () {
        if (seq !== that._reqSeq) return;
        that._loadingMoreLock = false;
        if (reset) {
          that._fullCourts = [];
          that.setData({
            courts: [],
            markers: [],
            loading: false,
            loadingMore: false,
            hasMore: false,
          });
        } else {
          that.setData({ loadingMore: false, hasMore: false });
        }
      });
  },

  onReachListBottom: function () {
    this._loadCourts({ reset: false });
  },

  onCoverError: function (e) {
    var id = e.currentTarget.dataset.id;
    if (!id) return;
    var courts = this.data.courts || [];
    var idx = -1;
    for (var i = 0; i < courts.length; i++) {
      if (String(courts[i].id) === String(id)) {
        idx = i;
        break;
      }
    }
    if (idx < 0) return;
    var patch = {};
    patch["courts[" + idx + "].cover"] = "";
    patch["courts[" + idx + "].coverFailed"] = true;
    this.setData(patch);
  },

  onLocateMe: function () {
    this._ensureLocationThenLoad(true);
  },

  onTypeFilter: function (e) {
    var key = e.currentTarget.dataset.key;
    if (key === this.data.filterCourtType) return;
    this.setData({ filterCourtType: key });
    this._loadCourts({ reset: true });
  },

  onPriceFilter: function (e) {
    var key = e.currentTarget.dataset.key;
    if (key === this.data.filterPrice) return;
    this.setData({ filterPrice: key });
    this._loadCourts({ reset: true });
  },

  onSortChange: function (e) {
    var key = e.currentTarget.dataset.key;
    if (key === this.data.sortBy) return;
    this.setData({ sortBy: key });
    if (key === "distance" && !this.data.hasUserLocation) {
      this._ensureLocationThenLoad(false);
    } else {
      this._loadCourts({ reset: true });
    }
  },

  onSearchInput: function (e) {
    this.setData({ searchKeyword: e.detail.value });
  },

  onSearchConfirm: function () {
    this._loadCourts({ reset: true });
  },

  onClearSearch: function () {
    this.setData({ searchKeyword: "" });
    this._loadCourts({ reset: true });
  },

  onCourtTap: function (e) {
    var id = e.currentTarget.dataset.id;
    var index = e.currentTarget.dataset.index;
    if (!id) return;
    var full = this._fullCourts[index] || this._fullCourts.find(function (c) {
      return String(c.id) === String(id);
    });
    if (full) {
      courtApi.savePreview(full);
      courtData.cacheCourts([full]);
    }
    wx.navigateTo({
      url: "/pages/court-detail/index?id=" + encodeURIComponent(id),
      fail: function () {
        wx.showToast({ title: "打开详情失败", icon: "none" });
      },
    });
  },

  onNavigateTap: function (e) {
    var index = e.currentTarget.dataset.index;
    var court = this._fullCourts[index] || this.data.courts[index];
    if (!court) return;
    wx.openLocation({
      latitude: court.lat,
      longitude: court.lng,
      name: court.name,
      address: court.address,
      scale: 16,
    });
  },

  onShowForm: function () {
    var app = getApp();
    if (!(app.isAuthDone && app.isAuthDone())) {
      wx.showModal({
        title: "请先登录",
        content: "登录后才能提报新球场",
        confirmText: "去登录",
        success: function (res) {
          if (res.confirm) {
            wx.navigateTo({ url: "/pages/login/index" });
          }
        },
      });
      return;
    }
    this.setData({ showForm: true });
  },
  onHideForm: function () {
    this.setData({ showForm: false });
  },

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
      lat: this.data.userLat || SH_LAT,
      lng: this.data.userLng || SH_LNG,
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
    this._loadCourts({ reset: true });
  },
});
