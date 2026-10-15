import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/social_api.dart';
import '../core/api_client.dart';
import '../core/storage.dart';
import '../models/models.dart';
import '../widgets/common.dart';

/// 搜索页（对齐 miniprogram pages/feed-search/index）
class FeedSearchPage extends StatefulWidget {
  const FeedSearchPage({super.key});

  @override
  State<FeedSearchPage> createState() => _FeedSearchPageState();
}

class _FeedSearchPageState extends State<FeedSearchPage> {
  /// 搜索历史 key（小程序无此功能，沿用 tenclip_ 前缀约定新增）
  static const _historyKey = 'tenclip_feed_search_history';

  final _controller = TextEditingController();

  List<FeedItem> _left = [];
  List<FeedItem> _right = [];
  bool _loading = false;
  List<String> _history = [];

  SocialApi get _social => context.read<SocialApi>();

  @override
  void initState() {
    super.initState();
    final raw = Storage.I.getList(_historyKey);
    _history = raw.map((e) => e.toString()).where((e) => e.isNotEmpty).take(10).toList();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _saveHistory(String keyword) {
    _history = [keyword, ..._history.where((e) => e != keyword)];
    if (_history.length > 10) _history = _history.sublist(0, 10);
    Storage.I.setJson(_historyKey, _history);
  }

  void _clearHistory() {
    setState(() => _history = []);
    Storage.I.remove(_historyKey);
  }

  void _onSearch() {
    final keyword = _controller.text.trim();
    if (keyword.isEmpty) {
      showToast(context, '请输入关键词');
      return;
    }
    _saveHistory(keyword);
    _search(keyword);
  }

  Future<void> _search(String keyword) async {
    setState(() {
      _loading = true;
      _left = [];
      _right = [];
    });
    // 笔记 + 资讯同时搜（/api/feed/search 后端已按时间混排，笔记结果做去重补充）
    final notesF = _social.searchNotes(keyword);
    final feedF = _social.searchFeed(keyword);
    List<FeedItem>? notes;
    List<FeedItem>? feed;
    Object? err;
    try {
      notes = await notesF;
    } catch (e) {
      err = e;
    }
    try {
      feed = await feedF;
    } catch (e) {
      err ??= e;
    }
    if (!mounted) return;
    if (notes == null && feed == null) {
      setState(() => _loading = false);
      showToast(context, err is ApiException ? err.message : '搜索失败');
      return;
    }
    final seen = <String>{};
    final merged = <FeedItem>[];
    for (final it in [...?feed, ...?notes]) {
      if (it.id.isEmpty || seen.contains(it.id)) continue;
      seen.add(it.id);
      // searchFeed 经 normalizeNote 统一映射，非 note- 前缀的资讯条目恢复 kind 以便跳转资讯详情
      if (!it.id.startsWith('note-') && it.kind == 'note') {
        it.kind = 'news';
      }
      merged.add(it);
    }
    final cols = splitWaterfall(merged);
    setState(() {
      _left = cols.left;
      _right = cols.right;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = slamOf(context);
    final keyword = _controller.text.trim();
    final hasResult = _left.isNotEmpty || _right.isNotEmpty;
    return Scaffold(
      appBar: themedAppBar(context, title: '搜索'),
      body: ThemedPage(
        child: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(6, 0, 6, 60),
            children: [
              // 搜索栏（对齐 .search-bar 白色胶囊）
              Padding(
                padding: const EdgeInsets.fromLTRB(6, 8, 6, 8),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(999),
                    boxShadow: const [
                      BoxShadow(color: Color(0x0A000000), blurRadius: 5, offset: Offset(0, 1)),
                    ],
                  ),
                  child: Row(
                    children: [
                      const Text('🔍', style: TextStyle(fontSize: 14, color: Color(0xFF9AA3AD))),
                      const SizedBox(width: 6),
                      Expanded(
                        child: TextField(
                          controller: _controller,
                          autofocus: true, // 对齐 focus="{{true}}"
                          textInputAction: TextInputAction.search,
                          onSubmitted: (_) => _onSearch(),
                          onChanged: (_) => setState(() {}),
                          style: const TextStyle(fontSize: 14, color: S.ink),
                          cursorColor: S.green,
                          decoration: const InputDecoration(
                            hintText: '搜索笔记、资讯',
                            hintStyle: TextStyle(fontSize: 14, color: S.faint),
                            border: InputBorder.none,
                            isDense: true,
                            contentPadding: EdgeInsets.symmetric(vertical: 10),
                          ),
                        ),
                      ),
                      GestureDetector(
                        onTap: _onSearch,
                        behavior: HitTestBehavior.opaque,
                        child: const Padding(
                          padding: EdgeInsets.symmetric(horizontal: 4, vertical: 10),
                          child: Text(
                            '搜索',
                            style: TextStyle(
                              color: Color(0xFF13D8A8),
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // 搜索历史（新增能力：本地保存最近 10 条）
              if (!hasResult && !_loading && keyword.isEmpty && _history.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(10, 4, 10, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              '搜索历史',
                              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: theme.ink),
                            ),
                          ),
                          GestureDetector(
                            onTap: _clearHistory,
                            child: Text('清空', style: TextStyle(fontSize: 12, color: theme.muted)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final h in _history)
                            GestureDetector(
                              onTap: () {
                                _controller.text = h;
                                _onSearch();
                              },
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(h, style: const TextStyle(fontSize: 13, color: S.sub)),
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),

              // 结果瀑布流
              if (hasResult)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: Column(children: [for (final it in _left) _SearchCard(item: it)])),
                      const SizedBox(width: 6),
                      Expanded(child: Column(children: [for (final it in _right) _SearchCard(item: it)])),
                    ],
                  ),
                )
              else if (!_loading)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 60, horizontal: 20),
                  child: Center(
                    child: Text(
                      keyword.isNotEmpty ? '未找到「$keyword」相关结果' : '输入关键词搜索笔记、资讯',
                      style: const TextStyle(color: Color(0xFF8A8A8A), fontSize: 14),
                    ),
                  ),
                ),
              if (_loading)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 60),
                  child: Center(
                    child: Text('搜索中…', style: TextStyle(color: Color(0xFF8A8A8A), fontSize: 14)),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 搜索结果卡片（对齐 feed-search .note-card；封面失败直接退字母块）
class _SearchCard extends StatelessWidget {
  const _SearchCard({required this.item});

  final FeedItem item;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => openFeedItem(context, item),
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          boxShadow: const [
            BoxShadow(color: Color(0x0A000000), blurRadius: 5, offset: Offset(0, 1)),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                CoverImage(
                  url: item.cover,
                  ratio: item.coverRatio,
                  fallbackLetter: item.authorInitial,
                ),
                if (item.mediaType == 'video')
                  const Positioned(
                    right: 6,
                    bottom: 6,
                    child: CircleAvatar(
                      radius: 11,
                      backgroundColor: Colors.black54,
                      child: Text('▶', style: TextStyle(color: Colors.white, fontSize: 11)),
                    ),
                  ),
                if (item.tourBadge.isNotEmpty)
                  Positioned(
                    left: 6,
                    top: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xE60DD8A8),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        item.tourBadge,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.all(8),
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
                  const SizedBox(height: 6),
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
}
