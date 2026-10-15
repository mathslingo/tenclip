import '../config.dart';
import '../core/api_client.dart';
import '../core/storage.dart';
import '../core/url_util.dart';
import '../models/models.dart';
import 'court_api.dart';
import 'social_api.dart';

/// 发现页 Feed API（对齐 miniprogram/utils/feed_api.js + feed_mock.js）
class FeedApi {
  FeedApi(this._client, this._storage);

  final ApiClient _client;
  final Storage _storage;

  static const _mockKey = 'tenclip_feed_use_mock';

  /// 本地打包兜底封面（小程序为 /image/pic0.png；iOS 端用 asset）
  static const fallbackCoverAsset = 'assets/pic0.png';

  /// 无真实封面时轮换的 mock 图（与小程序一致，仅保留验证过的 Unsplash）
  static const mockCovers = [
    (url: 'https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=600&q=80&auto=format&fit=crop', ratio: 1.25),
    (url: 'https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=600&q=80&auto=format&fit=crop', ratio: 0.85),
    (url: 'https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?w=600&q=80&auto=format&fit=crop', ratio: 1.1),
    (url: 'https://images.unsplash.com/photo-1534158914592-062992fbe900?w=600&q=80&auto=format&fit=crop', ratio: 0.95),
    (url: 'https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=600&q=80&auto=format&fit=crop', ratio: 1.15),
  ];

  bool get isMockEnabled {
    final raw = _storage.getString(_mockKey);
    if (raw.isEmpty) return feedUseMockDefault;
    return raw == '1' || raw == 'true';
  }

  static ({String url, double ratio}) pickMockCover(String id) {
    var h = 0;
    final s = id.isEmpty ? '0' : id;
    for (var i = 0; i < s.length; i++) {
      h = (h * 31 + s.codeUnitAt(i)) & 0xFFFFFFFF;
    }
    final c = mockCovers[h % mockCovers.length];
    return (url: c.url, ratio: c.ratio);
  }

  // ── channel / 徽标推断（对齐 inferChannel / inferCoverRatio）──

  static final _eventRe = RegExp(r'赛事|tournament|slam|atp|wta|温网|法网|美网|澳网|olympic|公开赛|决赛|冠军|排名|top\d|夺冠', caseSensitive: false);
  static final _teachRe = RegExp(r'教学|tip|drill|coaching|教程|正手|反手|发球|步法|双打站位|训练', caseSensitive: false);

  static String inferChannel(Map<String, dynamic> row) {
    var tags = _tagsOf(row);
    final blob = ('${tags.join(' ')} ${row['title'] ?? ''} ${row['source'] ?? ''}').toLowerCase();
    if (_eventRe.hasMatch(blob)) return '赛事';
    if (_teachRe.hasMatch(blob)) return '教学';
    return '推荐';
  }

  static List<String> _tagsOf(Map<String, dynamic> row) {
    var tags = <String>[];
    if (row['tags'] is List) {
      tags = (row['tags'] as List).map((e) => e.toString()).toList();
    } else if (row['tags_csv'] != null) {
      tags = row['tags_csv'].toString().split(',');
    }
    return tags.map((t) => t.trim()).where((t) => t.isNotEmpty).toList();
  }

  static double inferCoverRatio(String imageUrl) {
    final m = RegExp(r'/(\d{2,4})x(\d{2,4})_').firstMatch(imageUrl);
    if (m != null) {
      final w = double.tryParse(m.group(1)!) ?? 0;
      final h = double.tryParse(m.group(2)!) ?? 0;
      if (w > 0 && h > 0) return (h / w).clamp(0.45, 2.2);
    }
    if (imageUrl.contains('live-tennis.cn/images/trophies/')) return 0.54;
    return 1;
  }

  /// 对齐 mapApiItem
  FeedItem mapApiItem(Map<String, dynamic> row) {
    final id = row['id']?.toString() ?? '';
    if (row['kind'] == 'note' || id.startsWith('note-')) {
      final note = normalizeNote(row);
      note.channel = '推荐';
      note.score = row['score'] != null
          ? (row['score'] as num).toDouble()
          : (DateTime.tryParse(note.publishedAt)?.millisecondsSinceEpoch ?? 0).toDouble();
      return note;
    }
    final channel = inferChannel(row);
    final tags = _tagsOf(row);
    var tourBadge = '';
    if (tags.contains('ATP') && tags.contains('WTA')) {
      tourBadge = 'ATP/WTA';
    } else if (tags.contains('ATP')) {
      tourBadge = 'ATP';
    } else if (tags.contains('WTA')) {
      tourBadge = 'WTA';
    }
    var imageUrl = absUrl(row['image_url']?.toString().trim() ?? '');
    var coverIsMock = false;
    var coverRatio = inferCoverRatio(imageUrl);
    if (imageUrl.isEmpty) {
      final mock = pickMockCover(id);
      imageUrl = mock.url;
      coverRatio = mock.ratio;
      coverIsMock = true;
    }
    final likeRaw = row['like_count'] ?? row['popularity'] ?? 0;
    final author = row['source']?.toString() ?? 'UChance';
    final item = FeedItem(
      id: id,
      title: row['title']?.toString() ?? '',
      summary: row['summary']?.toString() ?? '',
      cover: imageUrl,
      coverIsMock: coverIsMock,
      authorName: author,
      authorInitial: author.isNotEmpty ? author[0] : 'U',
      likeCount: (likeRaw is num) ? likeRaw.round().clamp(0, 1 << 31) : 0,
      tags: tags,
      channel: channel,
      mediaType: row['media_type']?.toString() ?? 'image',
      url: row['url']?.toString() ?? '',
      publishedAt: row['published_at']?.toString() ?? '',
      coverRatio: coverRatio,
      kind: row['kind']?.toString() ?? (id.startsWith('note-') ? 'note' : 'news'),
      userId: row['user_id']?.toString() ?? '',
    );
    item.tourBadge = tourBadge;
    item.score = (row['score'] as num?)?.toDouble() ?? 0;
    return item;
  }

  // ── 分页拉取 ──

  Future<FeedPage> fetchFeedPage({
    String tab = '推荐',
    int offset = 0,
    int limit = 10,
    Future<({double lat, double lng})?> Function()? getLocation,
  }) async {
    if (tab == '附近') {
      return fetchNearbyPage(offset: offset, limit: limit, getLocation: getLocation);
    }
    if (isMockEnabled) {
      return _mockPage(tab: tab, offset: offset, limit: limit, source: 'mock');
    }
    final fetchLimit = tab == '推荐' ? limit : (limit * 4 > 24 ? limit * 4 : 24);
    try {
      final body = await _client.request(
        '/api/news/feed',
        query: {'limit': '$fetchLimit', 'offset': '$offset'},
        auth: false,
      );
      final j = Map<String, dynamic>.from(body as Map);
      final list = (j['items'] as List?) ?? [];
      var mapped = list
          .map((e) => mapApiItem(Map<String, dynamic>.from(e as Map)))
          .toList();
      if (tab != '推荐') {
        mapped.sort((a, b) {
          final tb = DateTime.tryParse(b.publishedAt)?.millisecondsSinceEpoch ?? 0;
          final ta = DateTime.tryParse(a.publishedAt)?.millisecondsSinceEpoch ?? 0;
          return tb.compareTo(ta);
        });
        mapped = mapped.where((it) => it.channel == tab).toList();
      }
      final pageItems = mapped.take(limit).toList();
      if (offset == 0 && pageItems.isEmpty) {
        return const FeedPage(items: [], offset: 0, nextOffset: 0, reachedEnd: true, total: 0, source: 'api-empty');
      }
      final nextOffset = offset + list.length;
      return FeedPage(
        items: pageItems,
        offset: offset,
        nextOffset: nextOffset,
        reachedEnd: list.length < fetchLimit || pageItems.isEmpty,
        total: offset + pageItems.length,
        source: 'api',
      );
    } catch (_) {
      return _mockPage(tab: tab, offset: offset, limit: limit, source: 'mock-fallback');
    }
  }

  // 附近缓存（对齐 _nearbyCache）
  ({List<FeedItem> list, String mode})? _nearbyCache;

  Future<FeedPage> fetchNearbyPage({
    int offset = 0,
    int limit = 10,
    Future<({double lat, double lng})?> Function()? getLocation,
  }) async {
    ({List<FeedItem> list, String mode}) pack;
    if (offset > 0 && _nearbyCache != null) {
      pack = _nearbyCache!;
    } else {
      ({double lat, double lng})? loc;
      var denied = false;
      if (getLocation != null) {
        try {
          loc = await getLocation();
        } catch (_) {
          denied = true;
        }
      }
      try {
        final rows = await _requestRecentNotes();
        final list = _buildNearbyList(rows, loc);
        pack = (list: list, mode: loc != null ? 'located' : (denied ? 'denied' : 'noloc'));
      } catch (e) {
        if (denied) {
          return const FeedPage(items: [], offset: 0, nextOffset: 0, reachedEnd: true, total: 0, source: 'nearby-denied');
        }
        return const FeedPage(items: [], offset: 0, nextOffset: 0, reachedEnd: true, total: 0, source: 'nearby-error');
      }
      _nearbyCache = pack;
    }
    final list = pack.list;
    final mode = pack.mode;
    final pageItems = list.skip(offset).take(limit).toList();
    final next = offset + pageItems.length;
    var source = 'nearby';
    if (list.isEmpty) {
      source = mode == 'denied' ? 'nearby-denied' : 'nearby-empty';
    } else if (mode == 'noloc' || mode == 'denied') {
      source = 'nearby-noloc';
    }
    return FeedPage(
      items: pageItems,
      offset: offset,
      nextOffset: next,
      reachedEnd: next >= list.length,
      total: list.length,
      source: source,
    );
  }

  void clearNearbyCache() => _nearbyCache = null;

  Future<List<Map<String, dynamic>>> _requestRecentNotes() async {
    final body = await _client.request(
      '/api/social/notes',
      query: {'limit': '80', 'offset': '0'},
      auth: false,
    );
    final items = (body is Map ? body['items'] : null) as List? ?? [];
    return items.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  List<FeedItem> _buildNearbyList(List<Map<String, dynamic>> rows, ({double lat, double lng})? loc) {
    final list = <FeedItem>[];
    for (final row in rows) {
      final note = normalizeNote(row);
      final lat = note.latitude;
      final lng = note.longitude;
      if (lat == null || lng == null) continue;
      note.channel = '附近';
      if (loc != null) {
        final d = CourtApi.distanceMeters(loc.lat, loc.lng, lat, lng);
        note.distanceM = d;
        note.distanceBadge = d < 1000
            ? '${d.round().clamp(1, 1 << 31)}m'
            : '${(d / 1000).toStringAsFixed(d < 10000 ? 1 : 0)}km';
      } else {
        note.distanceM = double.infinity;
        note.distanceBadge = note.locationName.isNotEmpty ? note.locationName : '有地点';
      }
      list.add(note);
    }
    list.sort((a, b) {
      final da = a.distanceM ?? double.infinity;
      final db = b.distanceM ?? double.infinity;
      if (da != db) return da.compareTo(db);
      return b.createdAt.compareTo(a.createdAt);
    });
    return list;
  }

  // ── 详情 ──

  Future<FeedItem?> getFeedItemById(String id) async {
    if (isMockEnabled || id.startsWith('mock-')) {
      return mockItemById(id);
    }
    if (id.startsWith('note-')) {
      try {
        final body = await _client.request('/api/social/notes/${Uri.encodeComponent(id.replaceFirst('note-', ''))}');
        return normalizeNote(Map<String, dynamic>.from(body as Map));
      } catch (_) {
        return null;
      }
    }
    try {
      final body = await _client.request('/api/news/articles/${Uri.encodeComponent(id)}', auth: false);
      final item = (body as Map)['item'];
      if (item is Map) return mapApiItem(Map<String, dynamic>.from(item));
      return null;
    } catch (_) {
      return null;
    }
  }

  // ── Mock（对齐 feed_mock.js）──

  FeedPage _mockPage({required String tab, required int offset, required int limit, required String source}) {
    final all = mockFeedItems.map((e) => _normalizeMock(e)).toList();
    final filtered = (tab.isEmpty || tab == '推荐') ? all : all.where((it) => it.channel == tab).toList();
    final slice = filtered.skip(offset).take(limit).toList();
    return FeedPage(
      items: slice,
      offset: offset,
      nextOffset: offset + slice.length,
      reachedEnd: offset + slice.length >= filtered.length,
      total: filtered.length,
      source: source,
    );
  }

  static FeedItem _normalizeMock(Map<String, dynamic> raw) {
    final author = raw['author_name']?.toString() ?? 'UChance';
    return FeedItem(
      id: raw['id']?.toString() ?? '',
      title: raw['title']?.toString() ?? '',
      summary: raw['summary']?.toString() ?? '',
      cover: raw['cover']?.toString() ?? '',
      authorName: author,
      authorInitial: author.isNotEmpty ? author[0] : 'U',
      likeCount: (raw['like_count'] as num?)?.toInt() ?? 0,
      tags: ((raw['tags'] as List?) ?? []).map((e) => e.toString()).toList(),
      channel: raw['channel']?.toString() ?? '推荐',
      mediaType: raw['media_type']?.toString() ?? 'image',
      url: raw['url']?.toString() ?? '',
      publishedAt: raw['published_at']?.toString() ?? '',
      coverRatio: (raw['cover_ratio'] as num?)?.toDouble() ?? 1,
    );
  }

  static FeedItem? mockItemById(String id) {
    for (final raw in mockFeedItems) {
      if (raw['id']?.toString() == id) return _normalizeMock(raw);
    }
    return null;
  }
}

/// 资讯 Mock（与 miniprogram feed_mock.js MOCK_ITEMS 一致）
final mockFeedItems = <Map<String, dynamic>>[
  {'id': 'mock-001', 'title': '固定组合战术：发球上网的三个常用套路', 'summary': '适合业余双打的简单站位与线路。先把一发质量稳住，再谈上网时机。', 'cover': 'https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 教学', 'like_count': 805, 'tags': ['教学', '双打'], 'channel': '教学', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-10T10:00:00Z', 'cover_ratio': 1.25},
  {'id': 'mock-002', 'title': '温网资格赛速览：谁在冲击正赛席位', 'summary': '几场关键战的比分与看点，帮你快速跟上草场赛季节奏。', 'cover': 'https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 赛事', 'like_count': 4323, 'tags': ['赛事', '温网'], 'channel': '赛事', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-09T08:00:00Z', 'cover_ratio': 0.85},
  {'id': 'mock-003', 'title': '业余球员最容易忽视的分腿垫步', 'summary': '接发球与相持中，分腿垫步决定你能不能在合适的击球点完成挥拍。', 'cover': 'https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 教学', 'like_count': 1260, 'tags': ['教学', '步法'], 'channel': '教学', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-08T12:00:00Z', 'cover_ratio': 1.1},
  {'id': 'mock-004', 'title': '法网赛后复盘：红土滑动与重心', 'summary': '职业选手在红土上的滑动不是花活，而是为下一拍创造时间。', 'cover': 'https://images.unsplash.com/photo-1534158914592-062992fbe900?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 赛事', 'like_count': 980, 'tags': ['赛事', '法网'], 'channel': '赛事', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-07T09:00:00Z', 'cover_ratio': 0.95},
  {'id': 'mock-005', 'title': '正手加速：从转肩到击球点的三条检查', 'summary': '录像里常见「抡大臂」。用这三条自查，往往比盲目加力量更有效。', 'cover': 'https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 教学', 'like_count': 2104, 'tags': ['教学', '正手'], 'channel': '教学', 'media_type': 'video', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-06T15:00:00Z', 'cover_ratio': 1.35},
  {'id': 'mock-006', 'title': 'ATP 一周焦点：硬地赛季转场看什么', 'summary': '赛程密集时，关注选手的轮换与伤病名单，比盯每天比分更有用。', 'cover': 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 赛事', 'like_count': 556, 'tags': ['赛事', 'ATP'], 'channel': '赛事', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-05T11:00:00Z', 'cover_ratio': 1.0},
  {'id': 'mock-007', 'title': '双打站位：何时换边、何时死守直线', 'summary': '业余双打输分常常输在站位犹豫。先约定简单暗号再谈花式配合。', 'cover': 'https://images.unsplash.com/photo-1551958219-acbc608c6377?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 教学', 'like_count': 743, 'tags': ['教学', '双打'], 'channel': '教学', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-04T14:00:00Z', 'cover_ratio': 1.15},
  {'id': 'mock-008', 'title': '青少年球员赛季规划：强度与恢复', 'summary': '比赛周与训练周如何交替，避免「一周打满、下一周动不了」。', 'cover': 'https://images.unsplash.com/photo-1518611012118-696072aa579a?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 网球', 'like_count': 312, 'tags': ['教学', '青训'], 'channel': '教学', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-03T10:00:00Z', 'cover_ratio': 0.9},
  {'id': 'mock-009', 'title': '美网热身站前瞻：谁在找手感', 'summary': '北美硬地串联赛，关注新球拍与新搭档磨合期的选手。', 'cover': 'https://images.unsplash.com/photo-1560089000-7433a4ebbd64?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 赛事', 'like_count': 1890, 'tags': ['赛事', '美网'], 'channel': '赛事', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-02T16:00:00Z', 'cover_ratio': 1.05},
  {'id': 'mock-010', 'title': '发球抛球：稳定比「抛得高」更重要', 'summary': '抛球点前后左右漂移，是一发成功率上不去的头号原因之一。', 'cover': 'https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 教学', 'like_count': 1502, 'tags': ['教学', '发球'], 'channel': '教学', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-07-01T09:00:00Z', 'cover_ratio': 1.2},
  {'id': 'mock-011', 'title': '中国网球公开赛观赛指南（精简版）', 'summary': '场地、交通与值得蹲守的夜场，一篇看完。', 'cover': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 赛事', 'like_count': 2201, 'tags': ['赛事', '中网'], 'channel': '赛事', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-06-30T12:00:00Z', 'cover_ratio': 0.88},
  {'id': 'mock-012', 'title': '如何用手机拍出能分析的挥拍视频', 'summary': '机位、光线与时长：给 AI 分析与教练复盘用的拍摄清单。', 'cover': 'https://images.unsplash.com/photo-1461896836934-ffe607ba6851?w=600&q=80&auto=format&fit=crop', 'author_name': 'UChance 教学', 'like_count': 667, 'tags': ['教学', '拍摄'], 'channel': '教学', 'media_type': 'image', 'url': 'https://clip.uchanceai.com/news', 'published_at': '2026-06-29T11:00:00Z', 'cover_ratio': 1.3},
];
