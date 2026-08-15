var courtData = require("../../utils/court_data");
var courtApi = require("../../utils/court_api");

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
  } catch (e) {
    return [];
  }
}

Page({
  data: {
    markers: [],
    scale: 12,
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
    /** 距离计算基准：优先真机定位，失败才用市中心 */
    userLat: SH_LAT,
    userLng: SH_LNG,
    hasUserLocation: false,
    searchKeyword: "",

    courts: [],
    showForm: false,
    loading: true,
  },

  _mapCtx: null,
  _locating: false,

  onLoad: function () {
    this._mapCtx = wx.createMapContext("courtMap", this);
    this._ensureLocationThenLoad(true);
  },

  onShow: function () {
    const tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) {
      tabBar.updateSelected();
    }
  },

  /**
   * 取定位作为「距离最近」基准；失败则退回上海中心点。
   * @param {boolean} moveMap 是否把地图中心移到用户位置
   */
  _ensureLocationThenLoad: function (moveMap) {
    var that = this;
    if (this._locating) return;
    this._locating = true;

    wx.getLocation({
      type: "gcj02",
      isHighAccuracy: true,
      success: function (res) {
        that._locating = false;
        var lat = Number(res.latitude) || SH_LAT;
        var lng = Number(res.longitude) || SH_LNG;
        var patch = {
          userLat: lat,
          userLng: lng,
          hasUserLocation: true,
        };
        if (moveMap) {
          patch.mapLat = lat;
          patch.mapLng = lng;
        }
        that.setData(patch);
        that._loadCourts();
      },
      fail: function () {
        that._locating = false;
        that.setData({ hasUserLocation: false });
        that._loadCourts();
        if (moveMap) {
          wx.showToast({
            title: "未开启定位，距离按市中心估算",
            icon: "none",
            duration: 2200,
          });
        }
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
      this._loadCourts();
      return;
    }
    this.setData({ activeTab: key });
  },

  _loadCourts: function () {
    var that = this;
    // 距离一律相对用户定位（或降级市中心），不要用地图拖动中心
    var lat = that.data.userLat;
    var lng = that.data.userLng;

    that.setData({ loading: true });

    courtApi
      .searchCourts({
        lat: lat,
        lng: lng,
        filter: that.data.filterCourtType,
        price: that.data.filterPrice,
        keyword: that.data.searchKeyword || "",
        limit: 80,
        radius_m: 80000,
      })
      .then(function (result) {
        var courts = (result && result.courts) || [];

        var userCourts = loadUserCourts().map(function (c) {
          var n = courtData.normalizeCourt(c);
          n.isUserCourt = true;
          if (n.lat && n.lng) {
            n.distance = courtData.calcDistance(lat, lng, n.lat, n.lng);
            n.distanceText = courtData.formatDistance(n.distance);
          }
          return n;
        });
        var all = courts.concat(userCourts);

        if (that.data.sortBy === "distance") {
          all.sort(function (a, b) {
            var da = a.distance != null && a.distance > 0 ? a.distance : 1e18;
            var db = b.distance != null && b.distance > 0 ? b.distance : 1e18;
            return da - db;
          });
        }

        courtData.cacheCourts(all);
        var markers = courtData.toMarkers(all);
        that.setData({ courts: all, markers: markers, loading: false });
      })
      .catch(function () {
        that.setData({ courts: [], markers: [], loading: false });
      });
  },

  onRegionChange: function (e) {
    if (e.type === "end" && e.detail && e.detail.centerLocation) {
      this.setData({
        mapLat: e.detail.centerLocation.latitude,
        mapLng: e.detail.centerLocation.longitude,
      });
    }
  },

  onLocateMe: function () {
    this._ensureLocationThenLoad(true);
  },

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
    if (key === "distance") {
      this._ensureLocationThenLoad(false);
    } else {
      this._loadCourts();
    }
  },

  onSearchInput: function (e) {
    this.setData({ searchKeyword: e.detail.value });
  },

  onSearchConfirm: function () {
    this._loadCourts();
  },

  onClearSearch: function () {
    this.setData({ searchKeyword: "" });
    this._loadCourts();
  },

  onMarkerTap: function (e) {
    var markerId = e.detail.markerId;
    var court = this.data.courts[markerId];
    if (!court) return;
    this.setData({ highlightId: court.id });
    this._mapCtx.moveToLocation({ latitude: court.lat, longitude: court.lng });
    var that = this;
    setTimeout(function () {
      that.setData({ highlightId: "" });
    }, 1500);
  },

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
    this._loadCourts();
  },
});
