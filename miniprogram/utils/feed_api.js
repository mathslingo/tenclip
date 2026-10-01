const { FEED_USE_MOCK: FEED_USE_MOCK_DEFAULT, API_BASE_URL } = require("./config");
const {
  fetchMockPage,
  getMockById,
  normalizeItem,
  FALLBACK_COVER,
  pickMockCover,
} = require("./feed_mock");
const { getNote, absUrl, normalizeNote } = require("./social_api");

const MOCK_KEY = "tenclip_feed_use_mock";

function isFeedMockEnabled() {
  try {
    var stored = wx.getStorageSync(MOCK_KEY);
    if (stored === "" || stored === undefined || stored === null) {
      return !!FEED_USE_MOCK_DEFAULT;
    }
    return stored === true || stored === "1";
  } catch (e) {
    return !!FEED_USE_MOCK_DEFAULT;
  }
}

function inferChannel(row) {
  var tags = row.tags || [];
  if (!tags.length && row.tags_csv) {
    tags = String(row.tags_csv)
      .split(",")
      .map(function (t) {
        return t.trim();
      })
      .filter(Boolean);
  }
  var blob = (tags.join(" ") + " " + (row.title || "") + " " + (row.source || "")).toLowerCase();
  if (
    /赛事|tournament|slam|atp|wta|温网|法网|美网|澳网|olympic|公开赛|决赛|冠军|排名|top\d|夺冠/.test(
      blob
    )
  ) {
    return "赛事";
  }
  if (/教学|tip|drill|coaching|教程|正手|反手|发球|步法|双打站位|训练/.test(blob)) {
    return "教学";
  }
  return "推荐";
}

function inferCoverRatio(imageUrl) {
  // live-tennis trophies: …/1200x648_….webp → height/width
  var m = String(imageUrl || "").match(/\/(\d{2,4})x(\d{2,4})_/);
  if (m) {
    var w = Number(m[1]);
    var h = Number(m[2]);
    if (w > 0 && h > 0) return Math.max(0.45, Math.min(h / w, 2.2));
  }
  if (/live-tennis\.cn\/images\/trophies\//i.test(String(imageUrl || ""))) {
    return 0.54; // 1200x648
  }
  return 1;
}

function mapApiItem(row) {
  if (row && (row.kind === "note" || String(row.id).indexOf("note-") === 0)) {
    var note = normalizeNote(row);
    note.channel = "推荐";
    note.score = row.score != null ? Number(row.score) : Date.parse(note.published_at || "") || 0;
    return note;
  }
  var channel = inferChannel(row);
  var tags = row.tags || (row.tags_csv ? String(row.tags_csv).split(",") : []);
  tags = tags
    .map(function (t) {
      return String(t).trim();
    })
    .filter(Boolean);
  var tourBadge = "";
  if (tags.indexOf("ATP") !== -1 && tags.indexOf("WTA") !== -1) {
    tourBadge = "ATP/WTA";
  } else if (tags.indexOf("ATP") !== -1) {
    tourBadge = "ATP";
  } else if (tags.indexOf("WTA") !== -1) {
    tourBadge = "WTA";
  }
  var imageUrl = absUrl((row.image_url || "").trim());
  var coverIsMock = false;
  var coverRatio = inferCoverRatio(imageUrl);
  if (!imageUrl) {
    var mock = pickMockCover(row.id);
    imageUrl = mock.url;
    coverRatio = mock.ratio;
    coverIsMock = true;
  }
  var item = normalizeItem({
    id: row.id,
    title: row.title,
    summary: row.summary,
    cover: imageUrl,
    image_url: imageUrl,
    author_name: row.source,
    like_count: Math.max(0, Math.round(Number(row.popularity) || 0)),
    popularity: row.popularity,
    tags: tags,
    channel: channel,
    url: row.url,
    published_at: row.published_at,
    cover_ratio: coverRatio,
  });
  item.tour_badge = tourBadge;
  item.cover_is_mock = coverIsMock;
  item.score = row.score != null ? Number(row.score) : 0;
  return item;
}

function filterApiItemsByTab(items, tab) {
  if (!tab || tab === "推荐") return items;
  return items.filter(function (it) {
    return it.channel === tab;
  });
}

var _nearbyCache = null;

function getDeviceLocation() {
  // 公众平台未开通「模糊地理位置」前不调用定位 API（否则上传 -80424）。
  // 开通后在此恢复定位调用。
  return Promise.reject(
    Object.assign(new Error("定位未开通"), { unavailable: true })
  );
}

function buildNearbyList(rows, loc) {
  var list = [];
  rows.forEach(function (row) {
    var note = normalizeNote(row);
    var lat = Number(note.latitude);
    var lng = Number(note.longitude);
    if (
      note.latitude == null ||
      note.longitude == null ||
      isNaN(lat) ||
      isNaN(lng)
    ) {
      return;
    }
    note.channel = "附近";
    if (loc && loc.latitude != null && loc.longitude != null) {
      var d = distanceMeters(loc.latitude, loc.longitude, lat, lng);
      note.distance_m = d;
      note.distance_badge = formatDistance(d);
    } else {
      note.distance_m = Number.POSITIVE_INFINITY;
      note.distance_badge = note.location_name || "有地点";
    }
    list.push(note);
  });
  list.sort(function (a, b) {
    if (a.distance_m !== b.distance_m) return a.distance_m - b.distance_m;
    return (b.created_at || 0) - (a.created_at || 0);
  });
  return list;
}

function distanceMeters(lat1, lng1, lat2, lng2) {
  var R = 6371000;
  var dLat = ((lat2 - lat1) * Math.PI) / 180;
  var dLng = ((lng2 - lng1) * Math.PI) / 180;
  var a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function formatDistance(m) {
  if (m < 1000) return Math.max(1, Math.round(m)) + "m";
  return (m / 1000).toFixed(m < 10000 ? 1 : 0) + "km";
}

function requestRecentNotes() {
  return new Promise(function (resolve, reject) {
    wx.request({
      url: API_BASE_URL + "/api/social/notes?limit=80&offset=0",
      method: "GET",
      success: function (res) {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error("请求失败 " + res.statusCode));
          return;
        }
        var items = (res.data && res.data.items) || [];
        resolve(Array.isArray(items) ? items : []);
      },
      fail: function (err) {
        reject(new Error((err && err.errMsg) || "网络错误"));
      },
    });
  });
}

/** 附近：有定位按距离；无定位仍展示带地点内容，避免反复弹授权 */
function fetchNearbyPage(opts) {
  var offset = opts.offset || 0;
  var limit = opts.limit || 10;
  var load;
  if (offset > 0 && _nearbyCache) {
    load = Promise.resolve(_nearbyCache);
  } else {
    load = getDeviceLocation()
      .then(function (loc) {
        return requestRecentNotes().then(function (rows) {
          var list = buildNearbyList(rows, loc);
          _nearbyCache = { list: list, mode: "located" };
          return _nearbyCache;
        });
      })
      .catch(function (err) {
        return requestRecentNotes().then(
          function (rows) {
            var list = buildNearbyList(rows, null);
            _nearbyCache = {
              list: list,
              mode: err && err.denied ? "denied" : "noloc",
            };
            return _nearbyCache;
          },
          function (netErr) {
            return Promise.reject(err && err.denied ? err : netErr || err);
          }
        );
      });
  }
  return load.then(
    function (pack) {
      var list = (pack && pack.list) || [];
      var mode = (pack && pack.mode) || "located";
      var pageItems = list.slice(offset, offset + limit);
      var next = offset + pageItems.length;
      var source = "nearby";
      if (!list.length) {
        source = mode === "denied" ? "nearby-denied" : "nearby-empty";
      } else if (mode === "noloc" || mode === "denied") {
        source = "nearby-noloc";
      }
      return {
        items: pageItems,
        offset: offset,
        nextOffset: next,
        reachedEnd: next >= list.length,
        total: list.length,
        source: source,
      };
    },
    function (err) {
      return {
        items: [],
        offset: 0,
        nextOffset: 0,
        reachedEnd: true,
        total: 0,
        source: err && err.denied ? "nearby-denied" : "nearby-error",
      };
    }
  );
}

function fetchFeedPage(opts) {
  opts = opts || {};
  if (opts.tab === "附近") {
    return fetchNearbyPage(opts);
  }
  if (isFeedMockEnabled()) {
    return Promise.resolve(
      Object.assign({ source: "mock" }, fetchMockPage(opts))
    );
  }
  var tab = opts.tab || "推荐";
  var limit = opts.limit || 10;
  var offset = opts.offset || 0;
  // 「推荐」跟服务端时间倒序分页；其它 tab 多取再按 channel 过滤
  var fetchLimit = tab === "推荐" ? limit : Math.max(limit * 4, 24);
  var q =
    "limit=" +
    encodeURIComponent(fetchLimit) +
    "&offset=" +
    encodeURIComponent(offset);
  return new Promise(function (resolve) {
    wx.request({
      url: API_BASE_URL + "/api/news/feed?" + q,
      method: "GET",
      success: function (res) {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          resolve(Object.assign({ source: "mock-fallback" }, fetchMockPage(opts)));
          return;
        }
        var body = res.data || {};
        var list = body.items || [];
        if (!Array.isArray(list)) list = [];
        var mapped = list.map(mapApiItem);
        mapped.sort(function (a, b) {
          var tb = Date.parse(b.published_at || "") || 0;
          var ta = Date.parse(a.published_at || "") || 0;
          return tb - ta;
        });
        var filtered = filterApiItemsByTab(mapped, tab);
        var pageItems =
          tab === "推荐" ? mapped.slice(0, limit) : filtered.slice(0, limit);
        if (offset === 0 && pageItems.length === 0) {
          resolve({
            items: [],
            offset: 0,
            nextOffset: 0,
            reachedEnd: true,
            total: 0,
            source: "api-empty",
          });
          return;
        }
        // 必须按「已消费的服务端窗口」推进，避免多取少展时跳过中间高分条目
        var nextOffset = offset + list.length;
        resolve({
          items: pageItems,
          offset: offset,
          nextOffset: nextOffset,
          reachedEnd: list.length < fetchLimit || pageItems.length === 0,
          total: offset + pageItems.length,
          source: "api",
        });
      },
      fail: function () {
        resolve(Object.assign({ source: "mock-fallback" }, fetchMockPage(opts)));
      },
    });
  });
}

function getFeedItemById(id) {
  if (isFeedMockEnabled() || String(id).indexOf("mock-") === 0) {
    return Promise.resolve(getMockById(id));
  }
  if (String(id).indexOf("note-") === 0) {
    return getNote(id).catch(function () {
      return null;
    });
  }
  return fetchFeedPage({ tab: "推荐", offset: 0, limit: 40 }).then(function (page) {
    for (var i = 0; i < page.items.length; i++) {
      if (String(page.items[i].id) === String(id)) return page.items[i];
    }
    return getMockById(id);
  });
}

module.exports = {
  FALLBACK_COVER,
  isFeedMockEnabled,
  fetchFeedPage,
  getFeedItemById,
  mapApiItem,
  inferChannel,
  inferCoverRatio,
};
