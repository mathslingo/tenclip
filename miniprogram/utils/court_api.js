/**
 * 网球场数据 API — 优先服务端 courts.db，失败降级本地 Mock。
 */
var config = require("./config");
var courtData = require("./court_data");

var TENCENT_POI_URL = "https://apis.map.qq.com/ws/place/v1/search";

function mapPoiToCourt(poi) {
  var name = (poi.title || "").replace(/\(.*?\)/g, "").replace(/（.*?）/g, "").replace("网球场", "").trim();
  if (!name) name = poi.title || "网球场";
  return courtData.normalizeCourt({
    id: "poi-" + (poi.id || ""),
    name: name,
    lat: poi.location ? poi.location.lat : 0,
    lng: poi.location ? poi.location.lng : 0,
    address: poi.address || "",
    rating: -1,
    priceRange: "",
    indoorCourts: -1,
    outdoorCourts: -1,
    facilities: [],
    photos: [],
    phone: poi.tel || "",
    hours: "",
    bookingOptions: [],
    extSources: [
      { name: "大众点评", icon: "⭐", keyword: name },
      { name: "小红书", icon: "📕", keyword: name + " 网球场" },
    ],
  });
}

function mapApiCourt(c) {
  return courtData.normalizeCourt({
    id: c.id,
    name: c.name,
    lat: c.lat,
    lng: c.lng,
    address: c.address,
    distance: c.distance,
    rating: c.rating,
    priceRange: c.priceRange || "",
    indoorCourts: c.indoorCourts,
    outdoorCourts: c.outdoorCourts,
    facilities: c.facilities || [],
    photos: c.photos || [],
    phone: c.phone || "",
    hours: c.hours || "",
    bookingOptions: c.bookingOptions || [],
    extSources: c.extSources || [],
    courtType: c.courtType,
  });
}

function searchTencentPoi(opts) {
  opts = opts || {};
  var key = config.TENCENT_MAP_KEY;
  if (!key) {
    return Promise.reject(new Error("未配置腾讯地图 Key"));
  }
  var boundary = "nearby(" + (opts.lat || 31.23) + "," + (opts.lng || 121.47) + ",50000)";
  return new Promise(function (resolve, reject) {
    wx.request({
      url: TENCENT_POI_URL,
      data: {
        keyword: opts.keyword || "网球",
        boundary: boundary,
        page_size: 20,
        page_index: opts.pageIndex || 1,
        key: key,
      },
      success: function (res) {
        if (res.data && res.data.status === 0) {
          resolve(res.data);
        } else {
          reject(new Error(res.data ? res.data.message : "POI 搜索失败"));
        }
      },
      fail: function (err) {
        reject(err);
      },
    });
  });
}

/**
 * 服务端球场库搜索（低延迟）
 */
function searchServerCourts(opts) {
  opts = opts || {};
  var q = [];
  if (opts.lat != null) q.push("lat=" + encodeURIComponent(opts.lat));
  if (opts.lng != null) q.push("lng=" + encodeURIComponent(opts.lng));
  if (opts.keyword) q.push("keyword=" + encodeURIComponent(opts.keyword));
  if (opts.filter && opts.filter !== "all") q.push("type=" + encodeURIComponent(opts.filter));
  if (opts.price && opts.price !== "all") q.push("price=" + encodeURIComponent(opts.price));
  if (opts.county) q.push("county=" + encodeURIComponent(opts.county));
  if (opts.radius_m) q.push("radius_m=" + encodeURIComponent(opts.radius_m));
  q.push("limit=" + encodeURIComponent(opts.limit || 80));
  if (opts.offset) q.push("offset=" + encodeURIComponent(opts.offset));

  return new Promise(function (resolve, reject) {
    wx.request({
      url: config.API_BASE_URL + "/api/courts/search?" + q.join("&"),
      method: "GET",
      timeout: 8000,
      success: function (res) {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data) {
          var items = res.data.items || [];
          resolve({
            courts: items.map(mapApiCourt),
            total: res.data.total || items.length,
            source: res.data.source || "courts.db",
          });
          return;
        }
        reject(new Error((res.data && res.data.detail) || "球场搜索失败"));
      },
      fail: function (err) {
        reject(new Error((err && err.errMsg) || "网络错误"));
      },
    });
  });
}

function fetchCourtById(id) {
  var sid = String(id || "");
  if (!sid) return Promise.reject(new Error("缺少球场 ID"));

  // 先查本地缓存 / Mock
  var local = courtData.fetchCourtById(sid);
  if (local) return Promise.resolve(local);

  return new Promise(function (resolve, reject) {
    wx.request({
      url: config.API_BASE_URL + "/api/courts/" + encodeURIComponent(sid),
      method: "GET",
      timeout: 8000,
      success: function (res) {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.id) {
          var court = mapApiCourt(res.data);
          courtData.cacheCourts([court]);
          resolve(court);
          return;
        }
        reject(new Error((res.data && res.data.detail) || "球场不存在"));
      },
      fail: function (err) {
        reject(new Error((err && err.errMsg) || "网络错误"));
      },
    });
  });
}

/**
 * 搜索网球场 — 服务端库优先，失败降级 Mock
 */
function searchCourts(opts) {
  opts = opts || {};
  return searchServerCourts(opts).catch(function (err) {
    console.warn("[court_api] 服务端搜索失败，降级 Mock:", err.message || err);
    var result = courtData.fetchNearbyCourts({
      lat: opts.lat,
      lng: opts.lng,
      filter: opts.filter,
      keyword: opts.keyword,
    });
    // 本地价格筛选
    if (opts.price && opts.price !== "all") {
      var pk = opts.price;
      result.courts = (result.courts || []).filter(function (c) {
        if (pk === "free") return String(c.priceRange || "").indexOf("免费") !== -1;
        var low = parseInt(c.priceRange, 10) || 0;
        if (pk === "0-60") return low <= 60;
        if (pk === "60-120") return low > 60 && low <= 120;
        if (pk === "120-200") return low > 120 && low <= 200;
        if (pk === "200+") return low > 200;
        return true;
      });
      result.total = result.courts.length;
    }
    result.source = "mock-fallback";
    return result;
  });
}

module.exports = {
  searchCourts: searchCourts,
  searchServerCourts: searchServerCourts,
  searchTencentPoi: searchTencentPoi,
  fetchCourtById: fetchCourtById,
  mapPoiToCourt: mapPoiToCourt,
  mapApiCourt: mapApiCourt,
};
