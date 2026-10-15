import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/court_api.dart';
import '../core/storage.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 「找球场」Tab（对齐 miniprogram pages/courts）
///
/// 与小程序差异：
/// - 顶部 <map> 地图区块不内嵌（iOS v1），定位仍在后台获取用于距离排序
/// - 卡片右侧导航钉 → 直接进入详情（详情页内有「地图」入口）
/// - 列表卡片补充评分星级（ratingStars）与设施标签（小程序列表未展示）
class CourtsPage extends StatefulWidget {
  const CourtsPage({super.key});

  @override
  State<CourtsPage> createState() => _CourtsPageState();
}

class _CourtsPageState extends State<CourtsPage> {
  // 上海默认坐标（对齐 SH_LAT / SH_LNG）
  static const _shLat = 31.23;
  static const _shLng = 121.47;
  static const _pageSize = 10;
  static const _userCourtsKey = 'tenclip_user_courts';

  // 对齐 PRICE_RANGES / SORT_OPTIONS / topTabs
  static const _priceOptions = [
    ('all', '全部'),
    ('free', '免费'),
    ('0-60', '60以下'),
    ('60-120', '60-120'),
    ('120-200', '120-200'),
    ('200+', '200以上'),
  ];
  static const _sortOptions = [
    ('default', '默认排序'),
    ('distance', '距离最近'),
  ];
  static const _topTabs = [
    ('all', '全部'),
    ('filter', '筛选'),
  ];

  final _searchCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();

  String _activeTab = 'all';
  String _filterCourtType = 'all';
  String _filterPrice = 'all';
  String _sortBy = 'default';
  String _searchKeyword = '';

  double _userLat = _shLat;
  double _userLng = _shLng;
  bool _hasUserLocation = false;

  List<Court> _courts = [];
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = true;
  bool _loadFailed = false; // 无缓存时的首屏失败（对齐小程序 error 分支）

  bool _locating = false;
  int _reqSeq = 0;

  CourtApi get _api => context.read<CourtApi>();

  @override
  void initState() {
    super.initState();
    _scrollCtrl.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // 对齐 onLoad：先按默认位置拉一版，再定位后刷新
      _loadCourts(reset: true);
      _ensureLocationThenLoad();
    });
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollCtrl.hasClients) return;
    // 对齐 lower-threshold=120（rpx≈60px，略放宽）
    if (_scrollCtrl.position.extentAfter < 200) {
      _loadCourts(reset: false);
    }
  }

  // ── 定位（对齐 _ensureLocationThenLoad）──

  Future<void> _ensureLocationThenLoad() async {
    if (_hasUserLocation) {
      _loadCourts(reset: true);
      return;
    }
    if (_locating) return;
    _locating = true;
    final loc = await context.read<AppState>().getDeviceLocation();
    _locating = false;
    if (!mounted) return;
    if (loc != null) {
      setState(() {
        _userLat = loc.lat;
        _userLng = loc.lng;
        _hasUserLocation = true;
      });
    } else {
      // 对齐小程序 fail 分支：降级默认位置（上海）
      _userLat = _shLat;
      _userLng = _shLng;
      _hasUserLocation = false;
    }
    _loadCourts(reset: true);
  }

  // ── 加载列表（对齐 _loadCourts）──

  Future<void> _loadCourts({required bool reset}) async {
    if (!reset) {
      if (!_hasMore || _loadingMore || _loading) return;
      setState(() => _loadingMore = true);
    } else {
      _loadFailed = false;
      setState(() {
        _loading = true;
        _hasMore = true;
        _loadingMore = false;
      });
    }

    final offset = reset ? 0 : _courts.length;
    final seq = ++_reqSeq;
    final hasKeyword = _searchKeyword.trim().isNotEmpty;

    // 对齐小程序：有关键词时不传地理位置（全库搜索）；无关键词时带上定位
    double? lat;
    double? lng;
    if (!hasKeyword && _hasUserLocation) {
      lat = _userLat;
      lng = _userLng;
    }

    try {
      final result = await _api.searchCourts(
        lat: lat,
        lng: lng,
        keyword: _searchKeyword,
        filter: _filterCourtType,
        price: _filterPrice,
        radiusM: 25000,
        limit: _pageSize,
        offset: offset,
      );
      if (!mounted || seq != _reqSeq) return;

      final page = result.courts;
      final total = result.total;

      List<Court> merged;
      if (reset) {
        // 用户提报只在首屏拼一次（对齐 loadUserCourts 拼接）
        final userCourts = _loadUserCourts();
        merged = [...page, ...userCourts];
        if (_sortBy == 'distance') {
          merged.sort((a, b) {
            final da = a.distance > 0 ? a.distance : 1e18;
            final db = b.distance > 0 ? b.distance : 1e18;
            return da.compareTo(db);
          });
        }
      } else {
        // 追加：按 id 去重
        final seen = _courts.map((c) => c.id).toSet();
        merged = [..._courts, ...page.where((c) => !seen.contains(c.id))];
      }

      final hasMore =
          total > 0 ? offset + page.length < total : page.length >= _pageSize;

      setState(() {
        _courts = merged;
        _loading = false;
        _loadingMore = false;
        _hasMore = hasMore;
      });
    } catch (_) {
      if (!mounted || seq != _reqSeq) return;
      if (reset) {
        final hasCache = _courts.isNotEmpty;
        setState(() {
          _loading = false;
          _loadingMore = false;
          _hasMore = false;
          _loadFailed = !hasCache;
        });
        if (!hasCache) {
          showToast(context, '加载失败，请检查网络连接');
        }
      } else {
        setState(() {
          _loadingMore = false;
          _hasMore = false;
        });
        showToast(context, '加载更多失败');
      }
    }
  }

  /// 用户提报的本地球场（对齐 loadUserCourts + normalizeCourt）
  List<Court> _loadUserCourts() {
    final list = context.read<Storage>().getList(_userCourtsKey);
    if (list.isEmpty) return const [];
    final out = <Court>[];
    for (final e in list) {
      if (e is! Map) continue;
      final c = CourtApi.mapApiCourt(Map<String, dynamic>.from(e));
      if (c.lat != 0 && c.lng != 0) {
        c.distance = CourtApi.distanceMeters(_userLat, _userLng, c.lat, c.lng);
        c.distanceText = CourtApi.formatDistance(c.distance);
      }
      out.add(c);
    }
    return out;
  }

  bool _isUserCourt(Court c) => c.id.startsWith('user-');

  // ── 交互（对齐各 onXxx）──

  void _onTabTap(String key) {
    if (key == 'all') {
      _searchCtrl.clear();
      setState(() {
        _activeTab = 'all';
        _filterCourtType = 'all';
        _filterPrice = 'all';
        _sortBy = 'default';
        _searchKeyword = '';
      });
      _loadCourts(reset: true);
      return;
    }
    setState(() => _activeTab = key);
  }

  void _onTypeFilter(String key) {
    if (key == _filterCourtType) return;
    setState(() => _filterCourtType = key);
    _loadCourts(reset: true);
  }

  void _onPriceFilter(String key) {
    if (key == _filterPrice) return;
    setState(() => _filterPrice = key);
    _loadCourts(reset: true);
  }

  void _onSortChange(String key) {
    if (key == _sortBy) return;
    setState(() => _sortBy = key);
    if (key == 'distance' && !_hasUserLocation) {
      _ensureLocationThenLoad();
    } else {
      _loadCourts(reset: true);
    }
  }

  void _onSearchConfirm() {
    _searchKeyword = _searchCtrl.text;
    _loadCourts(reset: true);
  }

  void _onClearSearch() {
    _searchCtrl.clear();
    _searchKeyword = '';
    _loadCourts(reset: true);
  }

  void _onCourtTap(Court court) {
    Navigator.pushNamed(context, '/court-detail', arguments: {'id': court.id});
  }

  /// 封面加载失败 → 换占位块（对齐 onCoverError）
  void _markCoverFailed(String id) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final idx = _courts.indexWhere((c) => c.id == id);
      if (idx < 0 || _courts[idx].coverFailed) return;
      setState(() => _courts[idx].coverFailed = true);
    });
  }

  // ── 提报新球场（对齐 showForm / onFormSubmit）──

  void _onShowSubmitForm() {
    if (!requireLogin(context, from: 'courts')) return;
    final nameCtrl = TextEditingController();
    final addrCtrl = TextEditingController();
    final indoorCtrl = TextEditingController();
    final outdoorCtrl = TextEditingController();
    final priceCtrl = TextEditingController();
    final facilitiesCtrl = TextEditingController();
    final phoneCtrl = TextEditingController();
    final hoursCtrl = TextEditingController();

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: S.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        Widget field(String label, TextEditingController ctrl,
            {String hint = '', bool required = false, TextInputType? keyboard}) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  required ? '$label *' : label,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: S.sub),
                ),
                const SizedBox(height: 7),
                SlamTextField(controller: ctrl, hint: hint, keyboardType: keyboard),
              ],
            ),
          );
        }

        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
          child: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      const Expanded(
                        child: Text(
                          '提报网球场',
                          style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: S.ink),
                        ),
                      ),
                      GestureDetector(
                        onTap: () => Navigator.pop(ctx),
                        child: const Padding(
                          padding: EdgeInsets.all(4),
                          child: Text('关闭', style: TextStyle(fontSize: 13, color: S.faint)),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  field('球场名称', nameCtrl, hint: '如：XX网球中心', required: true),
                  field('地址', addrCtrl, hint: '如：浦东新区XX路XX号', required: true),
                  Row(
                    children: [
                      Expanded(
                        child: field('室内场数', indoorCtrl,
                            hint: '0', keyboard: TextInputType.number),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: field('室外场数', outdoorCtrl,
                            hint: '0', keyboard: TextInputType.number),
                      ),
                    ],
                  ),
                  field('参考价格（元/小时）', priceCtrl, hint: '如：80-150'),
                  field('设施（用、分隔）', facilitiesCtrl, hint: '如：停车、淋浴、教练'),
                  field('电话', phoneCtrl, hint: '021-XXXXXXXX', keyboard: TextInputType.phone),
                  field('营业时间', hoursCtrl, hint: '如：06:00-22:00'),
                  AccentButton(
                    label: '提交',
                    onPressed: () {
                      final name = nameCtrl.text.trim();
                      final addr = addrCtrl.text.trim();
                      if (name.isEmpty || addr.isEmpty) {
                        showToast(context, '请填写球场名称和地址');
                        return;
                      }
                      _submitUserCourt(
                        name: name,
                        address: addr,
                        indoor: int.tryParse(indoorCtrl.text.trim()) ?? 0,
                        outdoor: int.tryParse(outdoorCtrl.text.trim()) ?? 0,
                        price: priceCtrl.text.trim(),
                        facilities: facilitiesCtrl.text.trim(),
                        phone: phoneCtrl.text.trim(),
                        hours: hoursCtrl.text.trim(),
                      );
                      Navigator.pop(ctx);
                    },
                  ),
                  GestureDetector(
                    onTap: () => Navigator.pop(ctx),
                    child: const Padding(
                      padding: EdgeInsets.only(top: 14, bottom: 4),
                      child: Text('取消', style: TextStyle(fontSize: 14, color: S.faint)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  void _submitUserCourt({
    required String name,
    required String address,
    required int indoor,
    required int outdoor,
    required String price,
    required String facilities,
    required String phone,
    required String hours,
  }) {
    final storage = context.read<Storage>();
    final list = storage.getList(_userCourtsKey);
    list.add({
      'id': 'user-${DateTime.now().millisecondsSinceEpoch}',
      'name': name,
      'lat': _hasUserLocation ? _userLat : _shLat,
      'lng': _hasUserLocation ? _userLng : _shLng,
      'address': address,
      'rating': 0,
      'priceRange': price.isNotEmpty ? price : '暂无',
      'indoorCourts': indoor,
      'outdoorCourts': outdoor,
      'facilities': facilities.split('、').where((s) => s.trim().isNotEmpty).toList(),
      'photos': <String>[],
      'phone': phone,
      'hours': hours,
      'bookingOptions': <dynamic>[],
      'extSources': <dynamic>[],
    });
    storage.setJson(_userCourtsKey, list);
    showToast(context, '感谢提报！积分+100');
    _loadCourts(reset: true);
  }

  // ── UI ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: themedAppBar(context, title: '找球场'),
      body: ThemedPage(
        child: Column(
          children: [
            _buildSearchBar(),
            _buildTabBar(),
            if (_activeTab == 'filter') _buildFilterPanel(),
            Expanded(child: _buildList()),
          ],
        ),
      ),
    );
  }

  /// 搜索栏（对齐 .search-bar）
  Widget _buildSearchBar() {
    final theme = slamOf(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.38),
          border: Border.all(color: Colors.white.withValues(alpha: 0.22)),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          children: [
            const Text('🔍', style: TextStyle(fontSize: 14)),
            const SizedBox(width: 5),
            Expanded(
              child: TextField(
                controller: _searchCtrl,
                textInputAction: TextInputAction.search,
                onChanged: (_) => setState(() {}), // 对齐 onSearchInput：驱动 ✕ 显隐
                onSubmitted: (_) => _onSearchConfirm(),
                style: TextStyle(fontSize: 13, color: theme.ink),
                cursorColor: S.green,
                decoration: InputDecoration(
                  hintText: '搜索网球场名称',
                  hintStyle: TextStyle(fontSize: 13, color: Colors.white.withValues(alpha: 0.62)),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(vertical: 9),
                ),
              ),
            ),
            if (_searchCtrl.text.isNotEmpty)
              GestureDetector(
                onTap: _onClearSearch,
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                  child: Text('✕', style: TextStyle(fontSize: 13, color: S.faint)),
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// 双 Tab（对齐 .tab-bar：全部 / 筛选）
  Widget _buildTabBar() {
    final theme = slamOf(context);
    return Container(
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.32),
        border: Border(
          bottom: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
        ),
      ),
      child: Row(
        children: [
          for (final t in _topTabs)
            Expanded(
              child: GestureDetector(
                onTap: () => _onTabTap(t.$1),
                behavior: HitTestBehavior.opaque,
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  decoration: BoxDecoration(
                    border: Border(
                      bottom: BorderSide(
                        width: 3,
                        color: _activeTab == t.$1 ? theme.accent : Colors.transparent,
                      ),
                    ),
                  ),
                  child: Text(
                    t.$2,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: _activeTab == t.$1 ? FontWeight.w700 : FontWeight.w400,
                      color: _activeTab == t.$1 ? Colors.white : theme.ink,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  /// 筛选面板（对齐 .panel：场地类型 / 价格区间 / 排序）
  Widget _buildFilterPanel() {
    final theme = slamOf(context);
    Widget section(String label, List<(String, String)> options, String current,
        ValueChanged<String> onTap,
        {bool wrap = false}) {
      final chips = [
        for (final o in options)
          GestureDetector(
            onTap: () => onTap(o.$1),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: current == o.$1
                    ? theme.accent
                    : Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                o.$2,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: current == o.$1 ? FontWeight.w600 : FontWeight.w400,
                  color: current == o.$1 ? theme.accentInk : theme.ink,
                ),
              ),
            ),
          ),
      ];
      return Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(fontSize: 12, color: theme.muted)),
            const SizedBox(height: 6),
            wrap
                ? Wrap(spacing: 5, runSpacing: 5, children: chips)
                : Row(children: [for (final c in chips) Padding(padding: const EdgeInsets.only(right: 5), child: c)]),
          ],
        ),
      );
    }

    return Container(
      width: double.infinity,
      color: Colors.black.withValues(alpha: 0.28),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          section('场地类型', CourtApi.filterTypes, _filterCourtType, _onTypeFilter),
          section('价格区间', _priceOptions, _filterPrice, _onPriceFilter, wrap: true),
          section('排序', _sortOptions, _sortBy, _onSortChange),
        ],
      ),
    );
  }

  /// 球场列表（对齐 .court-list；提报入口恒在顶部）
  Widget _buildList() {
    final theme = slamOf(context);

    // 首屏失败且无缓存：重试 UI（对齐小程序 error 分支 + 重试入口）
    if (_loadFailed && _courts.isEmpty && !_loading) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('加载失败，请检查网络连接',
                style: TextStyle(color: theme.ink, fontSize: 14)),
            const SizedBox(height: 18),
            GestureDetector(
              onTap: () => _loadCourts(reset: true),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 9),
                decoration: BoxDecoration(
                  color: theme.accent,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text('重试',
                    style: TextStyle(
                        color: theme.accentInk,
                        fontSize: 13,
                        fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      );
    }

    return ListView(
      controller: _scrollCtrl,
      padding: const EdgeInsets.only(bottom: 110),
      children: [
        // 提报入口（对齐 .submit-banner；wxss 为虚线边框，Flutter 用实线近似）
        GestureDetector(
          onTap: _onShowSubmitForm,
          child: Container(
            margin: const EdgeInsets.fromLTRB(12, 10, 12, 6),
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              color: S.cardBg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: S.green),
            ),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('➕', style: TextStyle(fontSize: 16)),
                SizedBox(width: 6),
                Text('提报新球场（补充数据获积分）', style: TextStyle(fontSize: 13, color: S.green)),
              ],
            ),
          ),
        ),

        if (_loading)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 12),
            child: Text('正在搜索网球场…',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: theme.ink)),
          )
        else if (_courts.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 50, horizontal: 24),
            child: Column(
              children: [
                const Text('🎾', style: TextStyle(fontSize: 40)),
                const SizedBox(height: 12),
                Text('未找到符合条件的网球场',
                    style: TextStyle(fontSize: 14, color: theme.ink)),
              ],
            ),
          )
        else ...[
          for (final entry in _courts.asMap().entries)
            _CourtCard(
              court: entry.value,
              showCover: entry.key < 10, // 对齐 COVER_LIMIT：仅前 10 条渲染封面
              isUserCourt: _isUserCourt(entry.value),
              onTap: () => _onCourtTap(entry.value),
              onCoverError: () => _markCoverFailed(entry.value.id),
            ),
          ListFooter(loading: _loadingMore, reachedEnd: !_hasMore, hint: _hasMore ? '' : '没有更多了'),
        ],
      ],
    );
  }
}

/// 球场卡片（对齐 .court-card；右侧导航钉在 iOS 简化为进入详情）
class _CourtCard extends StatelessWidget {
  const _CourtCard({
    required this.court,
    required this.showCover,
    required this.isUserCourt,
    this.onTap,
    this.onCoverError,
  });

  final Court court;
  final bool showCover;
  final bool isUserCourt;
  final VoidCallback? onTap;
  final VoidCallback? onCoverError;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.fromLTRB(12, 6, 12, 6),
        padding: const EdgeInsets.all(9),
        decoration: S.card(radius: 10),
        child: Row(
          children: [
            // 封面（对齐 .card-cover 150rpx≈75）
            ClipRRect(
              borderRadius: BorderRadius.circular(7),
              child: SizedBox(
                width: 75,
                height: 75,
                child: showCover && court.cover.isNotEmpty && !court.coverFailed
                    ? CoverImage(
                        url: court.cover,
                        ratio: 1,
                        fallbackLetter: court.name,
                        onError: onCoverError,
                      )
                    : Container(
                        color: const Color(0xFFE8F8F2),
                        alignment: Alignment.center,
                        child: const Icon(Icons.location_on, color: S.green, size: 22),
                      ),
              ),
            ),
            const SizedBox(width: 9),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 名称 + 评分星级（对齐 .card-rating）
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          court.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                              fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF1A1F26)),
                        ),
                      ),
                      if (court.rating > 0) ...[
                        const SizedBox(width: 5),
                        _RatingStars(stars: court.ratingStars, rating: court.rating),
                      ],
                    ],
                  ),
                  const SizedBox(height: 3),
                  // 距离 + 类型
                  Row(
                    children: [
                      if (court.distanceText.isNotEmpty)
                        Text('📍 ${court.distanceText}',
                            style: const TextStyle(fontSize: 11, color: S.muted)),
                      if (court.courtType.isNotEmpty) ...[
                        if (court.distanceText.isNotEmpty) const SizedBox(width: 8),
                        Text(
                          '${court.courtType}${court.totalCourts > 0 ? '${court.totalCourts}片' : ''}',
                          style: const TextStyle(fontSize: 11, color: S.muted),
                        ),
                      ],
                    ],
                  ),
                  if (court.address.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      '📍 ${court.address}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 10, color: S.faint),
                    ),
                  ],
                  const SizedBox(height: 3),
                  // 价格 + 电话 + 提报标
                  Row(
                    children: [
                      if (court.priceRange.isNotEmpty)
                        Text('💰 ¥${court.priceRange}/h',
                            style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFF0D3D32))),
                      if (court.phone.isNotEmpty) ...[
                        const SizedBox(width: 8),
                        Flexible(
                          child: Text('📞 ${court.phone}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 11, color: S.muted)),
                        ),
                      ],
                      if (isUserCourt)
                        Container(
                          margin: const EdgeInsets.only(left: 6),
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                            color: const Color(0xFFD4FFF4),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text('球友提报',
                              style: TextStyle(fontSize: 9, color: S.green)),
                        ),
                    ],
                  ),
                  // 设施标签（对齐 .card-tags；小程序详情页同款 chips）
                  if (court.facilities.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 3,
                      runSpacing: 3,
                      children: [
                        for (final f in court.facilities.take(4))
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF2F3F5),
                              borderRadius: BorderRadius.circular(3),
                            ),
                            child: Text(f, style: const TextStyle(fontSize: 9, color: S.muted)),
                          ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 评分星级（对齐 ratingStars：full / half / empty）
class _RatingStars extends StatelessWidget {
  const _RatingStars({required this.stars, required this.rating});

  final List<String> stars;
  final double rating;

  @override
  Widget build(BuildContext context) {
    const starColor = Color(0xFFF5A623);
    const emptyColor = Color(0xFFD0D5DD);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final s in stars)
          Icon(
            s == 'full'
                ? Icons.star
                : s == 'half'
                    ? Icons.star_half
                    : Icons.star_border,
            size: 11,
            color: s == 'empty' ? emptyColor : starColor,
          ),
        const SizedBox(width: 2),
        Text(
          rating.toStringAsFixed(1),
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: starColor),
        ),
      ],
    );
  }
}
