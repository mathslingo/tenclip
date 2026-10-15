import 'dart:math' as math;

import '../core/api_client.dart';
import '../models/models.dart';

/// 球场 API + 本地 Mock 降级（对齐 miniprogram court_api.js / court_data.js）
class CourtApi {
  CourtApi(this._client);

  final ApiClient _client;

  static const filterTypes = [
    ('all', '全部'),
    ('indoor', '室内'),
    ('outdoor', '室外'),
  ];

  /// 搜索球场：服务端优先，失败降级 Mock（对齐 searchCourts）
  Future<CourtSearchResult> searchCourts({
    double? lat,
    double? lng,
    String keyword = '',
    String filter = 'all',
    String price = 'all',
    String county = '',
    int? radiusM,
    int limit = 10,
    int offset = 0,
  }) async {
    try {
      return await searchServerCourts(
        lat: lat,
        lng: lng,
        keyword: keyword,
        filter: filter,
        price: price,
        county: county,
        radiusM: radiusM,
        limit: limit,
        offset: offset,
      );
    } catch (_) {
      final all = _mockSearch(lat: lat, lng: lng, keyword: keyword, filter: filter);
      final page = all.skip(offset).take(limit).toList();
      return CourtSearchResult(courts: page, total: all.length, source: 'mock-fallback');
    }
  }

  Future<CourtSearchResult> searchServerCourts({
    double? lat,
    double? lng,
    String keyword = '',
    String filter = 'all',
    String price = 'all',
    String county = '',
    int? radiusM,
    int limit = 10,
    int offset = 0,
  }) async {
    final q = <String, String>{
      if (lat != null) 'lat': '$lat',
      if (lng != null) 'lng': '$lng',
      if (keyword.isNotEmpty) 'keyword': keyword,
      if (filter != 'all') 'type': filter,
      if (price != 'all') 'price': price,
      if (county.isNotEmpty) 'county': county,
      if (radiusM != null) 'radius_m': '$radiusM',
      'limit': '$limit',
      'offset': '$offset',
      'lite': '1',
    };
    final body = await _client.request('/api/courts/search', query: q, auth: false);
    final j = Map<String, dynamic>.from(body as Map);
    final items = (j['items'] as List?) ?? [];
    return CourtSearchResult(
      courts: items.map((e) => mapApiCourt(Map<String, dynamic>.from(e as Map))).toList(),
      total: (j['total'] as num?)?.toInt() ?? items.length,
      source: j['source']?.toString() ?? 'courts.db',
    );
  }

  Future<Court> fetchCourtDetail(String id) async {
    final body = await _client.request('/api/courts/${Uri.encodeComponent(id)}', auth: false);
    final court = mapApiCourt(Map<String, dynamic>.from(body as Map));
    // 本地 Mock 有更全的预约/跳转配置时补齐（对齐小程序逻辑）
    final mock = mockCourtById(id);
    if (mock != null) {
      if (mock.bookingOptions.isNotEmpty) court.bookingOptions = mock.bookingOptions;
      if (court.extSources.isEmpty && mock.extSources.isNotEmpty) {
        court.extSources = mock.extSources;
      }
    }
    return court;
  }

  /// 先查本地 Mock/缓存，没有再拉详情（对齐 fetchCourtById）
  Future<Court?> fetchCourtById(String id) async {
    final mock = mockCourtById(id);
    if (mock != null) return mock;
    try {
      return await fetchCourtDetail(id);
    } catch (_) {
      return null;
    }
  }

  // ── Mock 降级 ──

  List<Court> _mockSearch({double? lat, double? lng, String keyword = '', String filter = 'all'}) {
    var all = mockCourts.map(mapApiCourt).toList();
    if (filter == 'indoor') {
      all = all.where((c) => c.indoorCourts > 0).toList();
    } else if (filter == 'outdoor') {
      all = all.where((c) => c.outdoorCourts > 0).toList();
    }
    if (keyword.isNotEmpty) {
      final kw = keyword.toLowerCase();
      all = all
          .where((c) => c.name.toLowerCase().contains(kw) || c.address.toLowerCase().contains(kw))
          .toList();
    }
    if (lat != null && lng != null) {
      for (final c in all) {
        c.distance = distanceMeters(lat, lng, c.lat, c.lng);
        c.distanceText = formatDistance(c.distance);
      }
      all.sort((a, b) => a.distance.compareTo(b.distance));
    }
    return all;
  }

  static Court? mockCourtById(String id) {
    for (final raw in mockCourts) {
      if (raw['id']?.toString() == id) return mapApiCourt(raw);
    }
    return null;
  }

  // ── 工具函数（对齐 court_data.js）──

  static double distanceMeters(double lat1, double lng1, double lat2, double lng2) {
    const r = 6371000.0;
    final dLat = (lat2 - lat1) * math.pi / 180;
    final dLng = (lng2 - lng1) * math.pi / 180;
    final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
        math.cos(lat1 * math.pi / 180) *
            math.cos(lat2 * math.pi / 180) *
            math.sin(dLng / 2) *
            math.sin(dLng / 2);
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
  }

  static String formatDistance(double? m) {
    if (m == null || m <= 0) return '';
    return m < 1000 ? '${m.round()}m' : '${(m / 1000).toStringAsFixed(1)}km';
  }

  static List<String> _starStates(double rating) {
    final r = (rating * 2).round() / 2;
    final stars = <String>[];
    for (var i = 1; i <= 5; i++) {
      if (r >= i) {
        stars.add('full');
      } else if (r >= i - 0.5) {
        stars.add('half');
      } else {
        stars.add('empty');
      }
    }
    return stars;
  }

  /// 对齐 normalizeCourt
  static Court mapApiCourt(Map<String, dynamic> raw) {
    final indoor = (raw['indoorCourts'] as num?)?.toInt() ?? -1;
    final outdoor = (raw['outdoorCourts'] as num?)?.toInt() ?? -1;
    var courtType = raw['courtType']?.toString() ?? '';
    if (courtType.isEmpty) {
      courtType = indoor > 0 && outdoor > 0
          ? '室内外'
          : indoor > 0
              ? '室内'
              : outdoor > 0
                  ? '室外'
                  : '';
    }
    final photos = ((raw['photos'] as List?) ?? [])
        .map((e) => e.toString())
        .where((u) => u.isNotEmpty && RegExp(r'^https?://', caseSensitive: false).hasMatch(u))
        .toList();
    var cover = raw['cover']?.toString() ?? (photos.isNotEmpty ? photos.first : '');
    if (cover.isNotEmpty && !RegExp(r'^https?://', caseSensitive: false).hasMatch(cover)) {
      cover = '';
    }
    final rating = (raw['rating'] as num?)?.toDouble() ?? -1;
    final distance = (raw['distance'] as num?)?.toDouble() ?? 0;
    return Court(
      id: raw['id']?.toString() ?? '',
      name: raw['name']?.toString() ?? '',
      lat: (raw['lat'] as num?)?.toDouble() ?? 0,
      lng: (raw['lng'] as num?)?.toDouble() ?? 0,
      address: raw['address']?.toString() ?? '',
      distance: distance,
      distanceText: raw['distanceText']?.toString() ?? formatDistance(distance),
      rating: rating,
      ratingStars: rating > 0 ? _starStates(rating) : const [],
      priceRange: raw['priceRange']?.toString() ?? '',
      indoorCourts: indoor,
      outdoorCourts: outdoor,
      totalCourts: indoor >= 0 && outdoor >= 0 ? indoor + outdoor : -1,
      courtType: courtType,
      facilities: ((raw['facilities'] as List?) ?? []).map((e) => e.toString()).toList(),
      photos: photos,
      cover: cover,
      phone: raw['phone']?.toString() ?? '',
      hours: raw['hours']?.toString() ?? '',
      bookingOptions: ((raw['bookingOptions'] as List?) ?? [])
          .whereType<Map>()
          .map((e) => BookingOption.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      extSources: ((raw['extSources'] as List?) ?? [])
          .whereType<Map>()
          .map((e) => ExtSource.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
    );
  }
}

/// 上海网球场 Mock 数据（与 miniprogram court_data.js 一致，服务端失败时降级用）
final mockCourts = <Map<String, dynamic>>[
  {'id': 'court-001', 'name': '源深体育中心网球中心', 'lat': 31.2296, 'lng': 121.5323, 'address': '浦东新区张杨路1458号', 'rating': 4.4, 'priceRange': '40-80', 'indoorCourts': 6, 'outdoorCourts': 4, 'facilities': ['停车', '淋浴', '空调', '器材租赁'], 'phone': '021-58606101', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}, {'name': '电话预约', 'type': 'phone', 'phone': '021-58606101'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '源深体育中心网球'}, {'name': '小红书', 'icon': '📕', 'keyword': '源深网球'}]},
  {'id': 'court-002', 'name': '东方体育中心网球馆', 'lat': 31.1547, 'lng': 121.4804, 'address': '浦东新区泳耀路300号', 'rating': 4.5, 'priceRange': '30-80', 'indoorCourts': 4, 'outdoorCourts': 8, 'facilities': ['停车', '淋浴', '商店', '餐厅'], 'phone': '021-20231234', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '久事体育', 'type': 'miniprogram', 'appId': ''}, {'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '东方体育中心网球'}, {'name': '小红书', 'icon': '📕', 'keyword': '东方体育中心网球'}]},
  {'id': 'court-003', 'name': '1877网球俱乐部', 'lat': 31.2370, 'lng': 121.5010, 'address': '浦东香格里拉酒店4楼屋顶', 'rating': 4.6, 'priceRange': '300-360', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车', '淋浴', '景观'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '电话预约', 'type': 'phone', 'phone': ''}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '1877网球俱乐部'}, {'name': '小红书', 'icon': '📕', 'keyword': '1877网球俱乐部'}]},
  {'id': 'court-004', 'name': '驿动网球运动中心', 'lat': 31.2070, 'lng': 121.5470, 'address': '浦东新区杨高南路2828号', 'rating': 4.3, 'priceRange': '170-300', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '驿动网球'}]},
  {'id': 'court-005', 'name': '至臻网球·康桥店', 'lat': 31.1420, 'lng': 121.5800, 'address': '浦东新区康桥路628号4栋', 'rating': 4.2, 'priceRange': '135-240', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调'], 'phone': '', 'hours': '07:00-23:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '至臻网球康桥'}]},
  {'id': 'court-006', 'name': '碧云荣广红土球场', 'lat': 31.2380, 'lng': 121.5820, 'address': '浦东新区碧云路299号', 'rating': 4.7, 'priceRange': '400', 'indoorCourts': 2, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '红土'], 'phone': '', 'hours': '08:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '碧云红土网球'}]},
  {'id': 'court-007', 'name': '徐汇万体馆(徐家汇体育公园)', 'lat': 31.1834, 'lng': 121.4393, 'address': '徐汇区漕溪北路1111号', 'rating': 4.6, 'priceRange': '100-320', 'indoorCourts': 3, 'outdoorCourts': 4, 'facilities': ['停车', '淋浴', '更衣室', '储物箱'], 'phone': '021-64385200', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '久事体育', 'type': 'miniprogram', 'appId': ''}, {'name': '电话预约', 'type': 'phone', 'phone': '021-64385200'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '徐家汇体育公园网球'}, {'name': '小红书', 'icon': '📕', 'keyword': '万体馆网球'}]},
  {'id': 'court-008', 'name': '康东网球馆', 'lat': 31.2305, 'lng': 121.4430, 'address': '静安区康定路151号', 'rating': 4.3, 'priceRange': '160-240', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['淋浴', '空调', 'WiFi'], 'phone': '021-62171234', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '康东网球馆'}]},
  {'id': 'court-009', 'name': 'RING·光环网球(徐汇店)', 'lat': 31.1800, 'lng': 121.4580, 'address': '徐汇区瑞平路230号保利时光里3楼天台', 'rating': 4.1, 'priceRange': '100-280', 'indoorCourts': 0, 'outdoorCourts': 1, 'facilities': ['停车'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '光环网球'}]},
  {'id': 'court-010', 'name': '亦新网球(光大店)', 'lat': 31.1650, 'lng': 121.4200, 'address': '徐汇区漕宝路82号光大会展中心E座4楼天台', 'rating': 4.0, 'priceRange': '200-259', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车'], 'phone': '', 'hours': '08:00-23:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '亦新网球'}]},
  {'id': 'court-011', 'name': '旗忠网球中心', 'lat': 31.0412, 'lng': 121.3449, 'address': '闵行区元江路5500号', 'rating': 4.9, 'priceRange': '200-500', 'indoorCourts': 6, 'outdoorCourts': 25, 'facilities': ['停车', '淋浴', '商店', '餐厅', 'VIP包厢', '教练'], 'phone': '021-34021234', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '久事体育', 'type': 'miniprogram', 'appId': ''}, {'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '旗忠网球中心'}, {'name': '小红书', 'icon': '📕', 'keyword': '旗忠网球中心'}]},
  {'id': 'court-012', 'name': '上海智胜网球旗舰店', 'lat': 31.1020, 'lng': 121.3940, 'address': '闵行区春申路1899号', 'rating': 4.3, 'priceRange': '180-250', 'indoorCourts': 12, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '教练', 'WiFi'], 'phone': '', 'hours': '07:00-23:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '智胜网球'}]},
  {'id': 'court-013', 'name': '梦网网球俱乐部', 'lat': 31.0800, 'lng': 121.5000, 'address': '闵行区浦江镇三鲁公路', 'rating': 4.2, 'priceRange': '130-220', 'indoorCourts': 2, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': <Map<String, String>>[]},
  {'id': 'court-014', 'name': 'OKK网球俱乐部', 'lat': 31.0500, 'lng': 121.4200, 'address': '闵行区都庄路4300号', 'rating': 4.4, 'priceRange': '138-298', 'indoorCourts': 6, 'outdoorCourts': 2, 'facilities': ['停车', '淋浴', '空调', '红土场'], 'phone': '', 'hours': '06:30-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': 'OKK网球'}]},
  {'id': 'court-015', 'name': '鹏佰网球场', 'lat': 31.0800, 'lng': 121.4000, 'address': '闵行区银都路春东路(屋顶)', 'rating': 4.0, 'priceRange': '38-68', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车'], 'phone': '', 'hours': '07:00-21:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '鹏佰网球'}]},
  {'id': 'court-016', 'name': '仙霞网球中心', 'lat': 31.2099, 'lng': 121.4120, 'address': '长宁区虹桥路1881号', 'rating': 4.5, 'priceRange': '60-260', 'indoorCourts': 1, 'outdoorCourts': 8, 'facilities': ['停车', '淋浴', '更衣室', '空调'], 'phone': '021-62626720', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '久事体育', 'type': 'miniprogram', 'appId': ''}, {'name': '电话预约', 'type': 'phone', 'phone': '021-62626720'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '仙霞网球中心'}, {'name': '小红书', 'icon': '📕', 'keyword': '仙霞网球中心'}]},
  {'id': 'court-017', 'name': '长宁网球中心', 'lat': 31.2220, 'lng': 121.4020, 'address': '长宁区华山路1038弄173号', 'rating': 4.2, 'priceRange': '60-160', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['停车', '淋浴'], 'phone': '021-62524436', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '来沪动', 'type': 'miniprogram', 'appId': ''}, {'name': '电话预约', 'type': 'phone', 'phone': '021-62524436'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '长宁网球中心'}]},
  {'id': 'court-018', 'name': '绿洲运动中心网球场(漕河泾)', 'lat': 31.1750, 'lng': 121.4000, 'address': '闵行区田林路888号', 'rating': 4.3, 'priceRange': '260-400', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '教练'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-019', 'name': '卢湾体育馆网球场', 'lat': 31.2110, 'lng': 121.4708, 'address': '黄浦区肇嘉浜路128号', 'rating': 4.4, 'priceRange': '50-280', 'indoorCourts': 2, 'outdoorCourts': 4, 'facilities': ['停车', '淋浴', '教练'], 'phone': '021-63011234', 'hours': '06:00-23:00', 'bookingOptions': [{'name': '勾勾运动', 'type': 'miniprogram', 'shortLink': '#小程序://勾勾运动/Mn9BgYZb0npey2g', 'appId': 'wxa43e880705719304', 'path': '/pages/index/index'}, {'name': '电话预约', 'type': 'phone', 'phone': '021-63011234'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '卢湾网球'}, {'name': '小红书', 'icon': '📕', 'keyword': '卢湾网球'}]},
  {'id': 'court-020', 'name': '静安区体育馆网球场', 'lat': 31.2498, 'lng': 121.4450, 'address': '静安区西康路99号', 'rating': 4.5, 'priceRange': '300-360', 'indoorCourts': 2, 'outdoorCourts': 0, 'facilities': ['淋浴', '空调', '更衣室'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '静安体育', 'type': 'miniprogram', 'appId': ''}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '静安体育馆网球'}, {'name': '小红书', 'icon': '📕', 'keyword': '静安网球馆'}]},
  {'id': 'court-021', 'name': '北外滩市民中心网球场', 'lat': 31.2580, 'lng': 121.4950, 'address': '虹口区通州路99号', 'rating': 4.6, 'priceRange': '280-600', 'indoorCourts': 3, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '更衣室', '红土场'], 'phone': '', 'hours': '07:00-23:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '北外滩网球'}]},
  {'id': 'court-022', 'name': 'Rising跃网网球俱乐部', 'lat': 31.2950, 'lng': 121.4700, 'address': '虹口区江杨南路425号商场6楼', 'rating': 4.3, 'priceRange': '188-340', 'indoorCourts': 2, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调'], 'phone': '', 'hours': '08:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': 'Rising跃网'}]},
  {'id': 'court-023', 'name': '杨浦体育场网球中心', 'lat': 31.2751, 'lng': 121.5261, 'address': '杨浦区隆昌路640号', 'rating': 4.0, 'priceRange': '40-100', 'indoorCourts': 2, 'outdoorCourts': 4, 'facilities': ['停车', '淋浴'], 'phone': '021-65501234', 'hours': '06:30-21:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': [{'name': '大众点评', 'icon': '⭐', 'keyword': '杨浦体育场网球'}]},
  {'id': 'court-024', 'name': '华东师范大学网球场', 'lat': 31.2280, 'lng': 121.4050, 'address': '普陀区中山北路3663号', 'rating': 4.0, 'priceRange': '40-60', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车', '淋浴'], 'phone': '', 'hours': '06:00-21:00', 'bookingOptions': [{'name': '电话预约', 'type': 'phone', 'phone': ''}], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '华师大网球'}]},
  {'id': 'court-025', 'name': '普陀体育宫网球场', 'lat': 31.2500, 'lng': 121.3900, 'address': '普陀区大渡河路1860号', 'rating': 3.8, 'priceRange': '40-60', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['停车', '淋浴'], 'phone': '', 'hours': '06:00-21:00', 'bookingOptions': [{'name': '场馆中心', 'type': 'miniprogram', 'appId': ''}], 'extSources': <Map<String, String>>[]},
  {'id': 'court-026', 'name': '麦斯特岚皋路网球场', 'lat': 31.2600, 'lng': 121.4200, 'address': '普陀区岚皋路', 'rating': 4.0, 'priceRange': '120-180', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['停车'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-027', 'name': 'RS网球俱乐部', 'lat': 31.3100, 'lng': 121.4100, 'address': '宝山区真大路520号米谷产业园', 'rating': 4.3, 'priceRange': '109-219', 'indoorCourts': 2, 'outdoorCourts': 1, 'facilities': ['停车', '淋浴', '空调'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': <Map<String, String>>[]},
  {'id': 'court-028', 'name': 'CPK TENNIS', 'lat': 31.3320, 'lng': 121.4800, 'address': '宝山区长逸路15号建配龙C馆5楼', 'rating': 4.1, 'priceRange': '200-400', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调'], 'phone': '', 'hours': '09:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-029', 'name': '至臻网球·南翔店', 'lat': 31.3100, 'lng': 121.3000, 'address': '嘉定区民主街385号电气都市工业园1号楼', 'rating': 4.1, 'priceRange': '130-180', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': <Map<String, String>>[]},
  {'id': 'court-030', 'name': '诸星耀网球俱乐部', 'lat': 31.1600, 'lng': 121.1200, 'address': '青浦区崧秀路', 'rating': 4.0, 'priceRange': '80-140', 'indoorCourts': 2, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-031', 'name': '奥帛球场', 'lat': 30.9200, 'lng': 121.4600, 'address': '奉贤区南桥镇望园路1888号', 'rating': 3.9, 'priceRange': '60-80', 'indoorCourts': 0, 'outdoorCourts': 1, 'facilities': ['停车'], 'phone': '', 'hours': '08:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'free-001', 'name': '唐丰公园网球场', 'lat': 31.2150, 'lng': 121.6600, 'address': '浦东新区创新西路520号', 'rating': 4.0, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['免费', '停车', '公园内'], 'phone': '', 'hours': '06:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '唐丰公园网球'}]},
  {'id': 'free-002', 'name': '唐镇公园网球场', 'lat': 31.2180, 'lng': 121.6550, 'address': '浦东新区唐镇公园内', 'rating': 3.9, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['免费', '公园内'], 'phone': '', 'hours': '06:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '唐镇公园网球'}]},
  {'id': 'free-003', 'name': '唐城绿地文化公园网球场', 'lat': 31.2200, 'lng': 121.6650, 'address': '浦东新区唐龙路479号', 'rating': 3.8, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 1, 'facilities': ['免费', '停车'], 'phone': '', 'hours': '06:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'free-004', 'name': '第二工业大学网球场', 'lat': 31.2850, 'lng': 121.6250, 'address': '浦东新区金海路2360号', 'rating': 4.1, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 5, 'facilities': ['免费', '雨棚', '停车收费'], 'phone': '', 'hours': '08:00-18:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '二工大网球'}]},
  {'id': 'free-005', 'name': '上海建桥学院网球场', 'lat': 30.9100, 'lng': 121.8700, 'address': '浦东新区沪城环路1111号', 'rating': 3.9, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['免费', '停车免费', '需门卫登记'], 'phone': '', 'hours': '08:00-18:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'free-006', 'name': '华夏公园网球场', 'lat': 31.1980, 'lng': 121.6100, 'address': '浦东新区华夏东路285号', 'rating': 3.7, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['免费', '停车'], 'phone': '', 'hours': '特定时段开放', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'free-007', 'name': '金石苑小区网球场', 'lat': 31.2900, 'lng': 121.5900, 'address': '浦东新区杨高北路5291弄1-27号', 'rating': 3.5, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 1, 'facilities': ['免费', '无灯光'], 'phone': '', 'hours': '全天', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'free-008', 'name': '上海城建职业学院网球场', 'lat': 31.2800, 'lng': 121.5400, 'address': '杨浦区港水路', 'rating': 3.8, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['免费', '先到先用', '需门卫登记'], 'phone': '', 'hours': '08:00-18:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '城建学院网球'}]},
  {'id': 'free-009', 'name': '莘庄中学公共运动场网球场', 'lat': 31.1100, 'lng': 121.3800, 'address': '闵行区腾冲路168号', 'rating': 3.9, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 1, 'facilities': ['免费', '学校开放'], 'phone': '', 'hours': '工作日8:30-18:00/节假日8:30-18:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'free-010', 'name': '长宁网球场(免费时段)', 'lat': 31.2220, 'lng': 121.4020, 'address': '长宁区华山路1038弄173号', 'rating': 4.2, 'priceRange': '免费(特定时段)', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['免费特定时段', '停车'], 'phone': '021-62524436', 'hours': '特殊时段免费', 'bookingOptions': [{'name': '电话确认', 'type': 'phone', 'phone': '021-62524436'}], 'extSources': <Map<String, String>>[]},
  {'id': 'free-011', 'name': '金山卫镇社区公共运动场网球场', 'lat': 30.7300, 'lng': 121.3100, 'address': '金山区金山卫镇西静路958号', 'rating': 3.6, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 1, 'facilities': ['免费', '公益'], 'phone': '', 'hours': '06:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'free-012', 'name': '普陀体育公园网球场', 'lat': 31.2600, 'lng': 121.3700, 'address': '普陀区桃浦镇金通路158号', 'rating': 3.8, 'priceRange': '免费', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['免费', '公园内', '停车'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-032', 'name': '得客会体育中心', 'lat': 31.0700, 'lng': 121.3800, 'address': '闵行区老厂房改造(全市最大室内馆)', 'rating': 4.5, 'priceRange': '80-180', 'indoorCourts': 25, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '惠民价'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '得客会网球'}]},
  {'id': 'court-033', 'name': '莘庄山花市民健身中心', 'lat': 31.1200, 'lng': 121.3800, 'address': '闵行区山花路(政府场馆)', 'rating': 4.3, 'priceRange': '40-100', 'indoorCourts': 2, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '政府定价'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-034', 'name': '绮梦网球中心', 'lat': 31.0500, 'lng': 121.4000, 'address': '闵行区梅州路505号', 'rating': 4.7, 'priceRange': '300-500', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '高端'], 'phone': '', 'hours': '07:00-23:00', 'bookingOptions': [{'name': '绮梦小程序', 'type': 'miniprogram', 'appId': ''}], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '绮梦网球'}]},
  {'id': 'court-035', 'name': '狼网网球(半室内)', 'lat': 31.1000, 'lng': 121.3600, 'address': '闵行区', 'rating': 4.0, 'priceRange': '60-120', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['停车', '畅打优惠'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': <Map<String, String>>[]},
  {'id': 'court-036', 'name': '交大闵行校区网球场', 'lat': 31.0300, 'lng': 121.4300, 'address': '闵行区东川路800号', 'rating': 4.0, 'priceRange': '20-50', 'indoorCourts': 0, 'outdoorCourts': 8, 'facilities': ['停车', '校园'], 'phone': '', 'hours': '06:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-037', 'name': '周浦网球中心', 'lat': 31.1200, 'lng': 121.5800, 'address': '浦东新区周浦镇', 'rating': 4.0, 'priceRange': '60-120', 'indoorCourts': 0, 'outdoorCourts': 4, 'facilities': ['停车', '淋浴'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': [{'name': '周浦小程序', 'type': 'miniprogram', 'appId': ''}], 'extSources': <Map<String, String>>[]},
  {'id': 'court-038', 'name': '三林体育中心网球场', 'lat': 31.1500, 'lng': 121.5100, 'address': '浦东新区三林路', 'rating': 4.1, 'priceRange': '50-100', 'indoorCourts': 0, 'outdoorCourts': 4, 'facilities': ['停车', '淋浴', '实惠'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-039', 'name': '森兰红土网球场', 'lat': 31.2900, 'lng': 121.5900, 'address': '浦东新区森兰国际社区', 'rating': 4.5, 'priceRange': '200-350', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['停车', '红土', '淋浴'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '森兰红土网球'}]},
  {'id': 'court-040', 'name': '浦东嘉里大酒店网球中心', 'lat': 31.2200, 'lng': 121.5600, 'address': '浦东新区花木路1388号', 'rating': 4.6, 'priceRange': '250-400', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车', '淋浴', '高端酒店'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-041', 'name': '行云网球(Our Tennis)', 'lat': 31.2500, 'lng': 121.4000, 'address': '普陀区', 'rating': 4.2, 'priceRange': '100-180', 'indoorCourts': 0, 'outdoorCourts': 5, 'facilities': ['停车', '淋浴', '好预定'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': [{'name': '韵动吧', 'type': 'miniprogram', 'appId': 'wxd0286fb3b0e39384'}], 'extSources': <Map<String, String>>[]},
  {'id': 'court-042', 'name': 'Master Tennis麦斯特', 'lat': 31.2600, 'lng': 121.4000, 'address': '普陀区岚皋路', 'rating': 3.8, 'priceRange': '120-180', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['停车'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-043', 'name': '穿越致胜网球场', 'lat': 31.2400, 'lng': 121.3800, 'address': '普陀区', 'rating': 3.7, 'priceRange': '80-140', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车'], 'phone': '', 'hours': '07:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-044', 'name': '体育宫网球场', 'lat': 31.2700, 'lng': 121.4200, 'address': '普陀区大渡河路', 'rating': 4.2, 'priceRange': '60-120', 'indoorCourts': 0, 'outdoorCourts': 4, 'facilities': ['停车', '淋浴', '性价比高'], 'phone': '', 'hours': '06:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-045', 'name': 'Breakpoint网球', 'lat': 31.2800, 'lng': 121.5200, 'address': '杨浦区', 'rating': 4.4, 'priceRange': '200-300', 'indoorCourts': 3, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '杨浦天花板'], 'phone': '', 'hours': '07:00-23:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-046', 'name': '跃网红光室内网球馆', 'lat': 31.3300, 'lng': 121.4100, 'address': '宝山区沪太路3651弄', 'rating': 4.2, 'priceRange': '180-250', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '性价比'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-047', 'name': '超越阳光草地网球', 'lat': 30.8500, 'lng': 121.5000, 'address': '奉贤区(真草+红土)', 'rating': 4.4, 'priceRange': '100-200', 'indoorCourts': 0, 'outdoorCourts': 3, 'facilities': ['停车', '真草地', '红土场'], 'phone': '', 'hours': '07:00-21:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '超越阳光草地网球'}]},
  {'id': 'court-048', 'name': '金徽上海网球中心', 'lat': 31.0300, 'lng': 121.2200, 'address': '松江区(气膜馆4片)', 'rating': 4.2, 'priceRange': '80-160', 'indoorCourts': 4, 'outdoorCourts': 0, 'facilities': ['停车', '淋浴', '空调', '气膜馆'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-049', 'name': '酷享网球', 'lat': 31.1500, 'lng': 121.1000, 'address': '青浦区(24h免费停车)', 'rating': 4.0, 'priceRange': '80-150', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车免费', '淋浴'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': <Map<String, String>>[]},
  {'id': 'court-050', 'name': '节奏网球俱乐部', 'lat': 31.2200, 'lng': 121.3800, 'address': '长宁区晨讯科技大楼顶楼', 'rating': 4.1, 'priceRange': '150-250', 'indoorCourts': 0, 'outdoorCourts': 2, 'facilities': ['停车', '顶楼视野好'], 'phone': '', 'hours': '07:00-22:00', 'bookingOptions': <Map<String, String>>[], 'extSources': [{'name': '小红书', 'icon': '📕', 'keyword': '节奏网球俱乐部'}]},
];
