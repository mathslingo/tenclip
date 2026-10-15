import 'dart:math' as math;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/feed_api.dart';
import '../api/social_api.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 资讯详情（对齐 miniprogram pages/feed-detail/index；笔记 id 转交笔记详情页）
class FeedDetailPage extends StatefulWidget {
  const FeedDetailPage({super.key, required this.itemId});

  final String itemId;

  @override
  State<FeedDetailPage> createState() => _FeedDetailPageState();
}

class _FeedDetailPageState extends State<FeedDetailPage> {
  FeedItem? _item;
  bool _coverFailed = false;
  String _publishedText = '';
  String _errorText = '';
  bool _liked = false;
  bool _bookmarked = false;

  AppState get _app => context.read<AppState>();
  FeedApi get _feed => context.read<FeedApi>();
  SocialApi get _social => context.read<SocialApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // note- 开头的 id 由笔记详情承接（对齐 openFeedItem / getFeedItemById 语义）
      if (widget.itemId.startsWith('note-')) {
        Navigator.pushReplacementNamed(context, '/note-detail', arguments: {'id': widget.itemId});
        return;
      }
      if (widget.itemId.isEmpty) {
        setState(() => _errorText = '缺少内容 id');
        return;
      }
      _load();
    });
  }

  Future<void> _load() async {
    try {
      final item = await _feed.getFeedItemById(widget.itemId);
      if (!mounted) return;
      if (item == null) {
        setState(() => _errorText = '内容不存在或已下线');
        return;
      }
      setState(() {
        _item = item;
        _publishedText =
            item.publishedAt.length >= 10 ? item.publishedAt.substring(0, 10) : item.publishedAt;
        _liked = _app.isLiked(item.id);
        _bookmarked = _app.isBookmarked(item.id);
      });
    } catch (_) {
      if (mounted) setState(() => _errorText = '加载失败');
    }
  }

  /// 封面失败：先退本地打包图，再退字母块（对齐 onCoverError）
  void _onCoverError() {
    if (!mounted) return;
    setState(() {
      final item = _item;
      if (item == null) return;
      if (item.cover == FeedApi.fallbackCoverAsset) {
        _coverFailed = true;
      } else {
        item.cover = FeedApi.fallbackCoverAsset;
      }
    });
  }

  void _scheduleCoverError() {
    WidgetsBinding.instance.addPostFrameCallback((_) => _onCoverError());
  }

  Future<void> _onToggleLike() async {
    final item = _item;
    if (item == null) return;
    if (!requireLogin(context, from: 'like')) return;
    final wasLiked = _liked;
    final base = math.max(0, item.likeCount);
    final nextLiked = !wasLiked;
    // 乐观更新展示数（对齐小程序）
    setState(() {
      _liked = nextLiked;
      item.likeCount = nextLiked ? base + 1 : math.max(0, base - 1);
    });
    _app.toggleLike(item.id);

    if (item.isNote) {
      try {
        final body = await _social.toggleNoteLikeRemote(item.id);
        if (!mounted) return;
        setState(() {
          _liked = body['liked'] == true;
          if (body['like_count'] != null) {
            item.likeCount = math.max(0, (body['like_count'] as num).toInt());
          }
        });
      } catch (_) {
        if (!mounted) return;
        setState(() {
          _liked = wasLiked;
          item.likeCount = base;
        });
        showToast(context, '点赞失败');
      }
      return;
    }

    try {
      // 对齐小程序 sendNewsFeedback：like / dislike
      await _social.sendNewsFeedback(item.id, nextLiked ? 'like' : 'dislike');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _liked = wasLiked;
        item.likeCount = base;
      });
      showToast(context, '点赞失败');
    }
  }

  void _onToggleBookmark() {
    final item = _item;
    if (item == null) return;
    final on = _app.toggleBookmark(item.id);
    setState(() => _bookmarked = on);
    showToast(context, on ? '已收藏' : '已取消收藏');
  }

  void _onShare() {
    final item = _item;
    if (item == null) return;
    final text = [item.title, item.url].where((e) => e.isNotEmpty).join(' ');
    Share.share(text.isEmpty ? 'UChance 网球社区' : text);
  }

  Future<void> _onOpenUrl() async {
    final item = _item;
    if (item == null || item.url.isEmpty) return;
    final uri = Uri.tryParse(item.url);
    if (uri == null) return;
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (mounted) showToast(context, '无法打开链接');
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = _item;
    final navTitle = item != null && item.title.isNotEmpty
        ? (item.title.length > 12 ? item.title.substring(0, 12) : item.title)
        : '笔记详情';
    return Scaffold(
      appBar: themedAppBar(context, title: navTitle),
      body: ThemedPage(
        child: item == null
            ? Padding(
                padding: const EdgeInsets.symmetric(vertical: 60, horizontal: 20),
                child: Center(
                  child: Text(
                    _errorText.isEmpty ? '加载中…' : _errorText,
                    style: const TextStyle(color: Color(0xFF9AA3AF), fontSize: 14),
                  ),
                ),
              )
            : ListView(
                padding: const EdgeInsets.only(bottom: 40),
                children: [
                  _hero(item),
                  Transform.translate(
                    offset: const Offset(0, -12),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Container(
                        padding: const EdgeInsets.fromLTRB(14, 16, 14, 18),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(14),
                          boxShadow: const [
                            BoxShadow(color: Color(0x0F000000), blurRadius: 10, offset: Offset(0, 2)),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.title,
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                                color: S.ink,
                                height: 1.4,
                              ),
                            ),
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                Avatar(url: item.authorAvatar, initial: item.authorInitial, size: 32),
                                const SizedBox(width: 7),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        item.authorName,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w600,
                                          color: S.ink,
                                        ),
                                      ),
                                      if (_publishedText.isNotEmpty) ...[
                                        const SizedBox(height: 2),
                                        Text(
                                          _publishedText,
                                          style: const TextStyle(fontSize: 11, color: Color(0xFF9AA3AF)),
                                        ),
                                      ],
                                    ],
                                  ),
                                ),
                                Text(
                                  '♡ ${item.likeCount}',
                                  style: const TextStyle(fontSize: 13, color: Color(0xFF6E7582)),
                                ),
                              ],
                            ),
                            const SizedBox(height: 14),
                            Text(
                              item.summary,
                              style: const TextStyle(fontSize: 14, height: 1.7, color: Color(0xFF415360)),
                            ),
                            if (item.tags.isNotEmpty) ...[
                              const SizedBox(height: 12),
                              Wrap(
                                spacing: 6,
                                runSpacing: 6,
                                children: [
                                  for (final t in item.tags)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFEEFBF6),
                                        borderRadius: BorderRadius.circular(999),
                                      ),
                                      child: Text(
                                        '#$t',
                                        style: const TextStyle(fontSize: 11, color: Color(0xFF0D7A62)),
                                      ),
                                    ),
                                ],
                              ),
                            ],
                            if (item.url.isNotEmpty) ...[
                              const SizedBox(height: 12),
                              GestureDetector(
                                onTap: _onOpenUrl,
                                behavior: HitTestBehavior.opaque,
                                child: const Padding(
                                  padding: EdgeInsets.symmetric(vertical: 4),
                                  child: Text(
                                    '阅读原文 ↗',
                                    style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                      color: S.green,
                                    ),
                                  ),
                                ),
                              ),
                            ],
                            const SizedBox(height: 14),
                            Row(
                              children: [
                                _actionChip(
                                  '${_liked ? '♥' : '♡'} ${_liked ? '已赞' : '赞'}'
                                  '${item.likeCount > 0 ? ' ${item.likeCount}' : ''}',
                                  on: _liked,
                                  onTap: _onToggleLike,
                                ),
                                const SizedBox(width: 8),
                                _actionChip(
                                  _bookmarked ? '★ 已收藏' : '☆ 收藏',
                                  on: _bookmarked,
                                  onTap: _onToggleBookmark,
                                ),
                                const SizedBox(width: 8),
                                _actionChip('↗ 分享', onTap: _onShare),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  /// 头图（对齐 .hero-cover：宽度撑满、按图自适应高度，最小 180）
  Widget _hero(FeedItem item) {
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 180),
      color: const Color(0xFFE8EEF2),
      child: _coverFailed
          ? _heroFallback(item)
          : (item.cover.isEmpty || item.cover == FeedApi.fallbackCoverAsset)
              ? Image.asset(
                  FeedApi.fallbackCoverAsset,
                  width: double.infinity,
                  fit: BoxFit.fitWidth,
                  errorBuilder: (_, __, ___) {
                    _scheduleCoverError();
                    return _heroFallback(item);
                  },
                )
              : CachedNetworkImage(
                  imageUrl: item.cover,
                  width: double.infinity,
                  fit: BoxFit.fitWidth,
                  placeholder: (_, __) => const SizedBox(height: 180),
                  errorWidget: (_, __, ___) {
                    _scheduleCoverError();
                    return _heroFallback(item);
                  },
                ),
    );
  }

  Widget _heroFallback(FeedItem item) {
    return Container(
      height: 210,
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
          fontSize: 40,
          fontWeight: FontWeight.w700,
          color: Color(0x660D3D32),
        ),
      ),
    );
  }

  Widget _actionChip(String label, {bool on = false, VoidCallback? onTap}) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 9),
          decoration: BoxDecoration(
            color: on ? const Color(0xFFE8FAF4) : const Color(0xFFF5F7F9),
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 13,
              height: 1.2,
              fontWeight: on ? FontWeight.w600 : FontWeight.w500,
              color: on ? const Color(0xFF0D3D32) : const Color(0xFF415360),
            ),
          ),
        ),
      ),
    );
  }
}
