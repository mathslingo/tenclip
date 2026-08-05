/**
 * 网球资讯 Feed Mock（M0）
 * channel: 推荐池全量；顶栏「赛事」「教学」按 channel 过滤
 */

var FALLBACK_COVER = "/assets/feed-fallback.png";

/** 无真实封面时轮换的 mock 图（仅保留已验证 HTTP 200 的 Unsplash） */
var MOCK_COVERS = [
  {
    url: "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=600&q=80&auto=format&fit=crop",
    ratio: 1.25,
  },
  {
    url: "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=600&q=80&auto=format&fit=crop",
    ratio: 0.85,
  },
  {
    url: "https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?w=600&q=80&auto=format&fit=crop",
    ratio: 1.1,
  },
  {
    url: "https://images.unsplash.com/photo-1534158914592-062992fbe900?w=600&q=80&auto=format&fit=crop",
    ratio: 0.95,
  },
  {
    url: "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=600&q=80&auto=format&fit=crop",
    ratio: 1.15,
  },
];

function pickMockCover(id) {
  var s = String(id || "0");
  var h = 0;
  for (var i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return MOCK_COVERS[h % MOCK_COVERS.length];
}

var MOCK_ITEMS = [
  {
    id: "mock-001",
    title: "固定组合战术：发球上网的三个常用套路",
    summary:
      "适合业余双打的简单站位与线路。先把一发质量稳住，再谈上网时机。",
    cover:
      "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 教学",
    like_count: 805,
    tags: ["教学", "双打"],
    channel: "教学",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-10T10:00:00Z",
    cover_ratio: 1.25,
  },
  {
    id: "mock-002",
    title: "温网资格赛速览：谁在冲击正赛席位",
    summary: "几场关键战的比分与看点，帮你快速跟上草场赛季节奏。",
    cover:
      "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 赛事",
    like_count: 4323,
    tags: ["赛事", "温网"],
    channel: "赛事",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-09T08:00:00Z",
    cover_ratio: 0.85,
  },
  {
    id: "mock-003",
    title: "业余球员最容易忽视的分腿垫步",
    summary: "接发球与相持中，分腿垫步决定你能不能在合适的击球点完成挥拍。",
    cover:
      "https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 教学",
    like_count: 1260,
    tags: ["教学", "步法"],
    channel: "教学",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-08T12:00:00Z",
    cover_ratio: 1.1,
  },
  {
    id: "mock-004",
    title: "法网赛后复盘：红土滑动与重心",
    summary: "职业选手在红土上的滑动不是花活，而是为下一拍创造时间。",
    cover:
      "https://images.unsplash.com/photo-1534158914592-062992fbe900?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 赛事",
    like_count: 980,
    tags: ["赛事", "法网"],
    channel: "赛事",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-07T09:00:00Z",
    cover_ratio: 0.95,
  },
  {
    id: "mock-005",
    title: "正手加速：从转肩到击球点的三条检查",
    summary: "录像里常见「抡大臂」。用这三条自查，往往比盲目加力量更有效。",
    cover:
      "https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 教学",
    like_count: 2104,
    tags: ["教学", "正手"],
    channel: "教学",
    media_type: "video",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-06T15:00:00Z",
    cover_ratio: 1.35,
  },
  {
    id: "mock-006",
    title: "ATP 一周焦点：硬地赛季转场看什么",
    summary: "赛程密集时，关注选手的轮换与伤病名单，比盯每天比分更有用。",
    cover:
      "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 赛事",
    like_count: 556,
    tags: ["赛事", "ATP"],
    channel: "赛事",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-05T11:00:00Z",
    cover_ratio: 1.0,
  },
  {
    id: "mock-007",
    title: "双打站位：何时换边、何时死守直线",
    summary: "业余双打输分常常输在站位犹豫。先约定简单暗号再谈花式配合。",
    cover:
      "https://images.unsplash.com/photo-1551958219-acbc608c6377?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 教学",
    like_count: 743,
    tags: ["教学", "双打"],
    channel: "教学",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-04T14:00:00Z",
    cover_ratio: 1.15,
  },
  {
    id: "mock-008",
    title: "青少年球员赛季规划：强度与恢复",
    summary: "比赛周与训练周如何交替，避免「一周打满、下一周动不了」。",
    cover:
      "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 网球",
    like_count: 312,
    tags: ["教学", "青训"],
    channel: "教学",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-03T10:00:00Z",
    cover_ratio: 0.9,
  },
  {
    id: "mock-009",
    title: "美网热身站前瞻：谁在找手感",
    summary: "北美硬地串联赛，关注新球拍与新搭档磨合期的选手。",
    cover:
      "https://images.unsplash.com/photo-1560089000-7433a4ebbd64?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 赛事",
    like_count: 1890,
    tags: ["赛事", "美网"],
    channel: "赛事",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-02T16:00:00Z",
    cover_ratio: 1.05,
  },
  {
    id: "mock-010",
    title: "发球抛球：稳定比「抛得高」更重要",
    summary: "抛球点前后左右漂移，是一发成功率上不去的头号原因之一。",
    cover:
      "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 教学",
    like_count: 1502,
    tags: ["教学", "发球"],
    channel: "教学",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-07-01T09:00:00Z",
    cover_ratio: 1.2,
  },
  {
    id: "mock-011",
    title: "中国网球公开赛观赛指南（精简版）",
    summary: "场地、交通与值得蹲守的夜场，一篇看完。",
    cover:
      "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 赛事",
    like_count: 2201,
    tags: ["赛事", "中网"],
    channel: "赛事",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-06-30T12:00:00Z",
    cover_ratio: 0.88,
  },
  {
    id: "mock-012",
    title: "如何用手机拍出能分析的挥拍视频",
    summary: "机位、光线与时长：给 AI 分析与教练复盘用的拍摄清单。",
    cover:
      "https://images.unsplash.com/photo-1461896836934-ffe607ba6851?w=600&q=80&auto=format&fit=crop",
    author_name: "UChance 教学",
    like_count: 667,
    tags: ["教学", "拍摄"],
    channel: "教学",
    media_type: "image",
    url: "https://clip.uchanceai.com/news",
    published_at: "2026-06-29T11:00:00Z",
    cover_ratio: 1.3,
  },
];

function normalizeItem(raw) {
  var author = raw.author_name || raw.source || "UChance";
  return {
    id: String(raw.id),
    title: raw.title || "",
    summary: raw.summary || "",
    cover: raw.cover || raw.image_url || FALLBACK_COVER,
    coverFailed: false,
    author_name: author,
    author_initial: author.charAt(0) || "U",
    like_count: raw.like_count != null ? raw.like_count : raw.popularity || 0,
    tags: raw.tags || [],
    channel: raw.channel || "推荐",
    media_type: raw.media_type || "image",
    url: raw.url || "",
    published_at: raw.published_at || "",
    cover_ratio: raw.cover_ratio || 1,
  };
}

function filterByTab(tab) {
  var all = MOCK_ITEMS.map(normalizeItem);
  if (!tab || tab === "推荐") return all;
  return all.filter(function (it) {
    return it.channel === tab;
  });
}

function fetchMockPage(opts) {
  opts = opts || {};
  var tab = opts.tab || "推荐";
  var offset = opts.offset || 0;
  var limit = opts.limit != null ? opts.limit : 6;
  var filtered = filterByTab(tab);
  var slice = filtered.slice(offset, offset + limit);
  return {
    items: slice,
    offset: offset,
    nextOffset: offset + slice.length,
    reachedEnd: offset + slice.length >= filtered.length,
    total: filtered.length,
  };
}

function getMockById(id) {
  for (var i = 0; i < MOCK_ITEMS.length; i++) {
    if (String(MOCK_ITEMS[i].id) === String(id)) {
      return normalizeItem(MOCK_ITEMS[i]);
    }
  }
  return null;
}

module.exports = {
  FALLBACK_COVER,
  MOCK_COVERS,
  pickMockCover,
  MOCK_ITEMS,
  normalizeItem,
  filterByTab,
  fetchMockPage,
  getMockById,
};
