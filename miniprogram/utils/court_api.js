/**
 * 网球场数据 API — 列表走轻量接口；详情单独拉取。
 */
var config = require("./config");
var courtData = require("./court_data");

var PREVIEW_KEY = "tenclip_court_preview";

function mapApiCourt(c) {
  var photos = c.photos || [];
  var cover = c.cover || (photos[0] || "");
  return courtData.normalizeCourt({
    id: c.id,
    name: c.name,
    lat: c.lat,
    lng: c.lng,
    address: c.address,
    distance: c.distance,
    distanceText: c.distanceText,
    rating: c.rating,
    priceRange: c.priceRange || "",
    indoorCourts: c.indoorCourts,
    outdoorCourts: c.outdoorCourts,
    facilities: c.facilities || [],
    photos: photos,
    cover: cover,
    phone: c.phone || "",
    hours: c.hours || "",
    bookingOptions: c.bookingOptions || [],
    extSources: c.extSources || [],
    courtType: c.courtType,
  });
}

function savePreview(court) {
  try {
    wx.setStorageSync(PREVIEW_KEY, court || null);
  } catch (e) {}
}

function readPreview(id) {
  try {
    var c = wx.getStorageSync(PREVIEW_KEY);
    if (c && String(c.id) === String(id)) return c;
  } catch (e) {}
  return null;
}

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
  q.push("limit=" + encodeURIComponent(opts.limit || 10));
  q.push("offset=" + encodeURIComponent(opts.offset || 0));
  q.push("lite=1");

  return new Promise(function (resolve, reject) {
    wx.request({
      url: config.API_BASE_URL + "/api/courts/search?" + q.join("&"),
      method: "GET",
      timeout: 15000,
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

function fetchCourtDetail(id) {
  var sid = String(id || "");
  if (!sid) return Promise.reject(new Error("缺少球场 ID"));

  return new Promise(function (resolve, reject) {
    wx.request({
      url: config.API_BASE_URL + "/api/courts/" + encodeURIComponent(sid),
      method: "GET",
      timeout: 15000,
      success: function (res) {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.id) {
          var court = mapApiCourt(res.data);
          courtData.cacheCourts([court]);
          savePreview(court);
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

function fetchCourtById(id) {
  var sid = String(id || "");
  if (!sid) return Promise.reject(new Error("缺少球场 ID"));

  var preview = readPreview(sid) || courtData.fetchCourtById(sid);
  if (preview) {
    return Promise.resolve(courtData.normalizeCourt(preview));
  }
  return fetchCourtDetail(sid);
}

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
    var offset = Number(opts.offset) || 0;
    var limit = Number(opts.limit) || 10;
    var all = result.courts || [];
    result.courts = all.slice(offset, offset + limit);
    result.total = all.length;
    result.source = "mock-fallback";
    return result;
  });
}

module.exports = {
  searchCourts: searchCourts,
  searchServerCourts: searchServerCourts,
  fetchCourtById: fetchCourtById,
  fetchCourtDetail: fetchCourtDetail,
  mapApiCourt: mapApiCourt,
  savePreview: savePreview,
  readPreview: readPreview,
};
