import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/feed_api.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme/slam_theme.dart';
import '../widgets/common.dart';

/// 「发现」Tab（对齐 miniprogram pages/feed/index）
class FeedPage extends StatefulWidget {
  const FeedPage({super.key});

  @override
  State<FeedPage> createState() => _FeedPageState();
}

class _FeedPageState extends State<FeedPage> {
  static const _pageSize = 6; // 对齐 PAGE_SIZE
  static const _topTabs = ['推荐', '赛事', '附近'];

  final _scroll = ScrollController();

  String _activeTab = '推荐';
  List<FeedItem> _left = [];
  List<FeedItem> _right = [];
  int _offset = 0;
  bool _reachedEnd = false;
  bool _loading = false;
  String _emptyHint = '';

  AppState get _app => context.read<AppState>();
  FeedApi get _feed => context.read<FeedApi>();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _reload();
      _app.refreshUnread(); // 对齐 onShow → refreshUnread
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  /// 对齐 onReachBottom
  void _onScroll() {
    if (!_scroll.hasClients) return;
    if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 100) {
      _loadMore();
    }
  }

  Future<void> _reload() async {
    setState(() {
      _left = [];
      _right = [];
      _offset = 0;
      _reachedEnd = false;
      _loading = false;
      _emptyHint = '';
    });
    await _loadMore();
  }

  Future<void> _loadMore() async {
    if (_loading || _reachedEnd) return;
    setState(() => _loading = true);
    try {
      final page = await _feed.fetchFeedPage(
        tab: _activeTab,
        offset: _offset,
        limit: _pageSize,
        getLocation: () => _app.getDeviceLocation(),
      );
      if (!mounted) return;
      final left = List<FeedItem>.from(_left);
      final right = List<FeedItem>.from(_right);
      // 按推荐序交替落入左右列（对齐小程序 forEach base+i 交替）
      appendAlternating(left, right, page.items);
      var emptyHint = '';
      if (left.isEmpty && right.isEmpty) {
        switch (page.source) {
          case 'api-empty':
            emptyHint = '暂时没有新内容，稍后再来看看。';
            break;
          case 'nearby-denied':
            emptyHint = '当前无法按距离排序。可先看「推荐」，或稍后再试。';
            break;
          case 'nearby-empty':
            emptyHint = '附近暂时没有带地点的内容。';
            break;
          case 'nearby-error':
          case 'mock-fallback':
            emptyHint = '网络繁忙，请稍后下拉刷新重试。';
            break;
          case 'nearby-noloc':
            emptyHint = '暂时无法按距离排序，附近还没有带地点的内容。';
            break;
        }
      }
      setState(() {
        _left = left;
        _right = right;
        _offset = page.nextOffset;
        _reachedEnd = page.reachedEnd;
        _loading = false;
        _emptyHint = emptyHint;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _onTopTab(String tab) {
    if (tab == _activeTab) return;
    _feed.clearNearbyCache(); // 切 tab 清附近缓存
    setState(() => _activeTab = tab);
    _reload();
  }

  void _onGoSearch() => Navigator.pushNamed(context, '/feed-search');

  void _onGoMessages() {
    _app.clearUnread(); // 对齐 onGoMessages 先清零角标
    Navigator.pushNamed(context, '/messages');
  }

  /// 封面失败：先换本地打包图，本地图再失败才退字母块（对齐 onCoverError）
  void _onCoverError(FeedItem it) {
    if (!mounted) return;
    setState(() {
      if (it.cover == FeedApi.fallbackCoverAsset) {
        it.coverFailed = true;
      } else {
        it.cover = FeedApi.fallbackCoverAsset;
        it.coverRatio = 0.75;
        it.coverIsMock = true;
        it.coverFailed = false;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = context.watch<SlamController>().theme;
    final unread = context.watch<AppState>().unreadCount;
    return Scaffold(
      appBar: themedAppBar(context, title: 'UChance'),
      body: ThemedPage(
        child: RefreshIndicator(
          onRefresh: _reload,
          child: ListView(
            controller: _scroll,
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(6, 0, 6, 110),
            children: [
              _searchBar(theme, unread),
              _topTabBar(theme),
              if (_left.isNotEmpty || _right.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(children: [
                          for (final it in _left) FeedNoteCard(item: it, onCoverError: _onCoverError),
                        ]),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Column(children: [
                          for (final it in _right) FeedNoteCard(item: it, onCoverError: _onCoverError),
                        ]),
                      ),
                    ],
                  ),
                )
              else if (!_loading)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Center(
                    child: Text('暂无内容', style: TextStyle(color: theme.ink, fontSize: 12)),
                  ),
                ),
              ListFooter(loading: _loading, reachedEnd: _reachedEnd, hint: _emptyHint),
            ],
          ),
        ),
      ),
    );
  }

  /// 搜索栏 + 消息铃铛（对齐 .search-bar / .msg-bell）
  Widget _searchBar(SlamTheme theme, int unread) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(6, 8, 6, 0),
      child: GestureDetector(
        onTap: _onGoSearch,
        behavior: HitTestBehavior.opaque,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          decoration: BoxDecoration(
            color: Colors.black.withValues(alpha: 0.38),
            border: Border.all(color: Colors.white.withValues(alpha: 0.28), width: 0.5),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Row(
            children: [
              const Text('🔍', style: TextStyle(fontSize: 14)),
              const SizedBox(width: 6),
              Expanded(
                child: Text('搜索笔记', style: TextStyle(color: theme.ink, fontSize: 14)),
              ),
              GestureDetector(
                onTap: _onGoMessages,
                behavior: HitTestBehavior.opaque,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                  child: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      const Text('🔔', style: TextStyle(fontSize: 17)),
                      if (unread > 0)
                        Positioned(
                          right: -5,
                          top: -3,
                          child: Container(
                            constraints: const BoxConstraints(minWidth: 14),
                            height: 14,
                            padding: const EdgeInsets.symmetric(horizontal: 3),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFF4D4F),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              unread > 99 ? '99+' : '$unread',
                              style: const TextStyle(color: Colors.white, fontSize: 9, height: 1),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 顶部 tabs（对齐 .top-tabs / .top-tab）
  Widget _topTabBar(SlamTheme theme) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(6, 8, 6, 6),
      child: Row(
        children: [
          for (var i = 0; i < _topTabs.length; i++) ...[
            if (i > 0) const SizedBox(width: 4),
            Expanded(
              child: GestureDetector(
                onTap: () => _onTopTab(_topTabs[i]),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    color: _activeTab == _topTabs[i]
                        ? theme.accent
                        : Colors.black.withValues(alpha: 0.32),
                    border: Border.all(
                      color: _activeTab == _topTabs[i]
                          ? Colors.transparent
                          : Colors.white.withValues(alpha: 0.2),
                      width: 0.5,
                    ),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    _topTabs[i],
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: _activeTab == _topTabs[i] ? FontWeight.w700 : FontWeight.w400,
                      color: _activeTab == _topTabs[i] ? theme.accentInk : theme.ink,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// 信息流卡片（对齐 feed 页 .note-card；封面两段式回退，故不复用 NoteCard）
class FeedNoteCard extends StatelessWidget {
  const FeedNoteCard({super.key, required this.item, required this.onCoverError});

  final FeedItem item;

  /// 封面加载失败回调（由宿主页面 setState 换图/置失败）
  final ValueChanged<FeedItem> onCoverError;

  void _scheduleError() {
    // errorWidget/errorBuilder 处于 build 阶段，延后到帧末再 setState
    WidgetsBinding.instance.addPostFrameCallback((_) => onCoverError(item));
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => openFeedItem(context, item),
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        decoration: BoxDecoration(
          color: const Color(0xFFF7FFF9),
          borderRadius: BorderRadius.circular(8),
          boxShadow: const [
            BoxShadow(color: Color(0x2E000000), blurRadius: 10, offset: Offset(0, 4)),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _cover(),
            Padding(
              padding: const EdgeInsets.fromLTRB(7, 8, 7, 7),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title.isNotEmpty ? item.title : item.summary,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: S.ink,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Row(
                    children: [
                      Expanded(
                        child: GestureDetector(
                          onTap: item.userId.isEmpty
                              ? null
                              : () => Navigator.pushNamed(context, '/user',
                                  arguments: {'user_id': item.userId}),
                          behavior: HitTestBehavior.opaque,
                          child: Row(
                            children: [
                              Avatar(url: item.authorAvatar, initial: item.authorInitial, size: 18),
                              const SizedBox(width: 4),
                              Flexible(
                                child: Text(
                                  item.authorName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontSize: 11, color: Color(0xFF6E7582)),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFF5F6),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          children: [
                            const Text('♡',
                                style: TextStyle(fontSize: 13, color: Color(0xFFE5515F), height: 1)),
                            const SizedBox(width: 3),
                            Text(
                              '${item.likeCount}',
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFFE5515F),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _cover() {
    return AspectRatio(
      aspectRatio: 1 / item.coverRatio.clamp(0.3, 3.0),
      child: Stack(
        fit: StackFit.expand,
        children: [
          _coverImage(),
          if (item.mediaType == 'video')
            const Positioned(
              right: 6,
              top: 6,
              child: CircleAvatar(
                radius: 11,
                backgroundColor: Colors.black54,
                child: Text('▶', style: TextStyle(color: Colors.white, fontSize: 10)),
              ),
            ),
          if (item.tourBadge.isNotEmpty)
            Positioned(
              left: 6,
              top: 6,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xD10D3D32),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  item.tourBadge,
                  style: const TextStyle(
                    color: Color(0xFFD4FFF4),
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _coverImage() {
    if (item.coverFailed) return _letterBlock();
    // 空封面等同失败：直接走本地打包图（对齐 <image src=""> 触发 error）
    if (item.cover.isEmpty || item.cover == FeedApi.fallbackCoverAsset) {
      return Image.asset(
        FeedApi.fallbackCoverAsset,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) {
          _scheduleError();
          return _letterBlock();
        },
      );
    }
    return CachedNetworkImage(
      imageUrl: item.cover,
      fit: BoxFit.cover,
      placeholder: (_, __) => Container(color: const Color(0xFFE8EEF2)),
      errorWidget: (_, __, ___) {
        _scheduleError();
        return _letterBlock();
      },
    );
  }

  Widget _letterBlock() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFBAF5E8), Color(0xFF7EE0C8)],
        ),
      ),
      alignment: Alignment.center,
      child: Text(
        item.authorInitial.isNotEmpty ? item.authorInitial[0] : 'U',
        style: const TextStyle(
          fontSize: 32,
          fontWeight: FontWeight.w700,
          color: Color(0x730D3D32),
        ),
      ),
    );
  }
}
