/**
 * 网球场数据 API — 腾讯地图 POI 搜索 + Mock 降级
 *
 * 数据源优先级：
 *   1. 腾讯地图 POI 搜索（真实球场数据）
 *   2. 本地 Mock 数据（接口异常时降级）
 */

var config = require("./config");
var courtData = require("./court_data");

var TENCENT_POI_URL = "https://apis.map.qq.com/ws/place/v1/search";

/**
 * 将腾讯 POI 数据转为球场格式
 */
function mapPoiToCourt(poi) {
  var name = (poi.title || "").replace(/\(.*?\)/g, "").replace(/（.*?）/g, "").replace("网球场", "").trim();
  if (!name) name = poi.title || "网球场";
  return courtData.normalizeCourt({
    id: "poi-" + (poi.id || ""),
    name: name,
    lat: poi.location ? poi.location.lat : 0,
    lng: poi.location ? poi.location.lng : 0,
    address: poi.address || "",
    rating: -1,              // -1 = 无评分数据
    priceRange: "",           // 空 = 无价格数据
    indoorCourts: -1,         // -1 = 未知
    outdoorCourts: -1,         // -1 = 未知
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

/**
 * 从腾讯地图 POI 搜索网球场
 * @param {Object} opts - { lat, lng, keyword, pageIndex }
 * @returns {Promise}
 */
function searchTencentPoi(opts) {
  opts = opts || {};
  var key = config.TENCENT_MAP_KEY;

  if (!key) {
    return Promise.reject(new Error("未配置腾讯地图 Key"));
  }

  // 搜索半径 50km 覆盖全上海
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
 * 搜索网球场 — 先调腾讯 POI，失败降级 Mock
 * @param {Object} opts
 * @returns {Promise<{courts: Array, source: string, total: number}>}
 */
function searchCourts(opts) {
  opts = opts || {};

  return searchTencentPoi(opts)
    .then(function (response) {
      var pois = response.data || [];
      var courts = pois.map(mapPoiToCourt);

      // 名称去重
      var seen = {};
      courts = courts.filter(function (c) {
        if (seen[c.name]) return false;
        seen[c.name] = true;
        return true;
      });

      return {
        courts: courts,
        total: response.count || courts.length,
        source: "tencent-poi",
      };
    })
    .catch(function (err) {
      console.warn("[court_api] POI 搜索失败，降级Mock:", err.message || err);
      // 降级到 Mock 数据
      var result = courtData.fetchNearbyCourts({
        lat: opts.lat,
        lng: opts.lng,
        filter: opts.filter,
        keyword: opts.keyword,
      });
      result.source = "mock-fallback";
      return result;
    });
}

module.exports = {
  searchCourts,
  searchTencentPoi,
  mapPoiToCourt,
};
