const { FEED_USE_MOCK: FEED_USE_MOCK_DEFAULT, API_BASE_URL } = require("./config");
const {
  fetchMockPage,
  getMockById,
  normalizeItem,
  FALLBACK_COVER,
} = require("./feed_mock");

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
    /赛事|tournament|slam|atp|wta|温网|法网|美网|澳网|olympic|公开赛|final|资格赛/.test(blob)
  ) {
    return "赛事";
  }
  if (/教学|tip|drill|coaching|教程|正手|反手|发球|步法|双打站位|训练/.test(blob)) {
    return "教学";
  }
  return "推荐";
}

function mapApiItem(row) {
  var channel = inferChannel(row);
  return normalizeItem({
    id: row.id,
    title: row.title,
    summary: row.summary,
    cover: row.image_url,
    image_url: row.image_url,
    author_name: row.source,
    like_count: Math.max(0, Math.round(Number(row.popularity) || 0)),
    popularity: row.popularity,
    tags: row.tags || (row.tags_csv ? String(row.tags_csv).split(",") : []),
    channel: channel,
    url: row.url,
    published_at: row.published_at,
    cover_ratio: 1,
  });
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
  // 服务端 tags 过滤较弱；多取一些再在客户端按 channel 粗分（M1）
  var fetchLimit = Math.max(opts.limit || 10, 20);
  var q =
    "limit=" +
    encodeURIComponent(fetchLimit) +
    "&offset=" +
    encodeURIComponent(opts.offset || 0);
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
        var filtered = filterApiItemsByTab(mapped, tab);
        var offset = opts.offset || 0;
        var limit = opts.limit || 10;
        // 服务端已按 offset 分页；客户端 channel 过滤后可能变少
        var pageItems = tab === "推荐" ? mapped.slice(0, limit) : filtered.slice(0, limit);
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
        resolve({
          items: pageItems,
          offset: offset,
          nextOffset: offset + (body.next_offset != null ? list.length : pageItems.length),
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
