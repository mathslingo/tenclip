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
    note.score = row.score != null ? Number(row.score) : 160;
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

function fetchFeedPage(opts) {
  opts = opts || {};
  if (isFeedMockEnabled()) {
    return Promise.resolve(
      Object.assign({ source: "mock" }, fetchMockPage(opts))
    );
  }
  var tab = opts.tab || "推荐";
  var limit = opts.limit || 10;
  var offset = opts.offset || 0;
  // 「推荐」严格跟服务端 score 分页；其它 tab 多取再按 channel 过滤
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
        // 防御：保证按推荐分倒序（服务端应已排好）
        mapped.sort(function (a, b) {
          return (Number(b.score) || 0) - (Number(a.score) || 0);
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
};
