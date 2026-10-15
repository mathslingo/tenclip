import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/social_api.dart';
import '../core/api_client.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 笔记详情（对齐 miniprogram pages/note-detail）
class NoteDetailPage extends StatefulWidget {
  const NoteDetailPage({super.key, required this.noteId});

  final String noteId;

  @override
  State<NoteDetailPage> createState() => _NoteDetailPageState();
}

class _NoteDetailPageState extends State<NoteDetailPage> {
  FeedItem? _note;
  String _errorText = '';
  bool _isMine = false;
  bool _following = false;
  bool _liked = false;
  bool _bookmarked = false;
  int _imageIndex = 0;

  List<NoteComment> _comments = [];
  int _commentTotal = 0;
  Map<String, String> _nameById = {};
  final TextEditingController _commentCtrl = TextEditingController();
  final FocusNode _commentFocus = FocusNode();
  ({String id, String name})? _replyTo;
  bool _submitting = false;

  static const _placeholder = '说说你的想法... (最多140字)';

  AppState get _app => context.read<AppState>();
  SocialApi get _social => context.read<SocialApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    _commentFocus.dispose();
    super.dispose();
  }

  // ── 加载（对齐 onLoad）──

  Future<void> _load() async {
    final id = widget.noteId.trim();
    if (id.isEmpty) {
      setState(() {
        _errorText = '缺少笔记 id';
        _note = null;
      });
      return;
    }
    try {
      final note = await _social.getNote(id);
      if (!mounted) return;
      if (note == null || note.id.isEmpty) {
        throw ApiException('笔记不存在或已删除');
      }
      final me = _app.userId;
      setState(() {
        _note = note;
        _errorText = '';
        _isMine = me.isNotEmpty && note.userId == me;
        _liked = _app.isLiked(note.id);
        _bookmarked = _app.isBookmarked(note.id);
      });
      if (!_isMine && note.userId.isNotEmpty) {
        _social.fetchUser(note.userId, viewerId: me).then((u) {
          if (mounted) setState(() => _following = u.isFollowing);
        }).catchError((_) {});
      }
      _loadComments().catchError((_) {});
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _note = null;
        _errorText = e is ApiException && e.message.isNotEmpty ? e.message : '笔记不存在或已删除';
      });
    }
  }

  Future<void> _loadComments() async {
    final note = _note;
    if (note == null) return;
    final items = await _social.fetchComments(note.id);
    if (!mounted) return;
    final nested = SocialApi.nestComments(items, formatFeedTime);
    setState(() {
      _comments = nested.comments;
      _commentTotal = nested.total;
      _nameById = {for (final c in items) c.id: c.authorName};
    });
  }

  // ── 笔记时间（对齐 formatTime(created_at || published_at)）──

  String _timeText(FeedItem n) {
    DateTime? dt;
    if (n.createdAt > 0) {
      dt = DateTime.fromMillisecondsSinceEpoch(n.createdAt * 1000);
    } else if (n.publishedAt.isNotEmpty) {
      dt = DateTime.tryParse(n.publishedAt)?.toLocal();
    }
    if (dt == null) return '';
    String p2(int v) => v.toString().padLeft(2, '0');
    return '${dt.year}-${p2(dt.month)}-${p2(dt.day)} ${p2(dt.hour)}:${p2(dt.minute)}';
  }

  // ── 点赞（对齐 onToggleLike：本地乐观 + 远端校准 + 失败回滚）──

  void _syncLocalLike(String id, bool on) {
    if (_app.isLiked(id) != on) _app.toggleLike(id);
  }

  Future<void> _onToggleLike() async {
    if (!requireLogin(context)) return;
    final note = _note;
    if (note == null) return;
    final wasLiked = _liked;
    final base = note.likeCount < 0 ? 0 : note.likeCount;
    final nextLiked = !wasLiked;
    setState(() {
      _liked = nextLiked;
      note.likeCount = nextLiked ? base + 1 : (base > 0 ? base - 1 : 0);
    });
    _syncLocalLike(note.id, nextLiked);
    try {
      final res = await _social.toggleNoteLikeRemote(note.id);
      if (!mounted) return;
      final liked = res['liked'] == true;
      setState(() {
        _liked = liked;
        final c = res['like_count'];
        if (c is num) note.likeCount = c.toInt() < 0 ? 0 : c.toInt();
      });
      _syncLocalLike(note.id, liked);
      showToast(context, liked ? '已赞' : '已取消赞');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _liked = wasLiked;
        note.likeCount = base;
      });
      _syncLocalLike(note.id, wasLiked);
      showToast(context, '操作失败');
    }
  }

  // ── 收藏（小程序走远端 bookmark 接口；Flutter v1 仅本地，对齐 profile 收藏列表）──

  void _onToggleBookmark() {
    if (!requireLogin(context)) return;
    final note = _note;
    if (note == null) return;
    final on = _app.toggleBookmark(note.id);
    setState(() => _bookmarked = on);
    showToast(context, on ? '已收藏' : '已取消收藏');
  }

  // ── 关注（对齐 onToggleFollow）──

  Future<void> _onToggleFollow() async {
    final note = _note;
    if (note == null || _isMine) return;
    if (!requireLogin(context, from: 'follow')) return;
    final next = !_following;
    try {
      if (next) {
        await _social.follow(note.userId);
      } else {
        await _social.unfollow(note.userId);
      }
      if (!mounted) return;
      setState(() => _following = next);
      showToast(context, next ? '已关注' : '已取消关注');
    } catch (e) {
      if (!mounted) return;
      showToast(context, e is ApiException && e.message.isNotEmpty ? e.message : '操作失败');
    }
  }

  // ── 删除笔记（对齐 onDelete）──

  Future<void> _onDelete() async {
    final note = _note;
    if (note == null) return;
    final ok = await showConfirm(
      context,
      title: '删除笔记',
      content: '删除后无法恢复，确定吗？',
      danger: true,
    );
    if (!ok || !mounted) return;
    try {
      await _social.deleteNote(note.id);
      if (!mounted) return;
      showToast(context, '已删除');
      await Future<void>.delayed(const Duration(milliseconds: 400));
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      showToast(context, e is ApiException && e.message.isNotEmpty ? e.message : '删除失败');
    }
  }

  void _onOpenAuthor() {
    final uid = _note?.userId ?? '';
    if (uid.isEmpty) return;
    Navigator.pushNamed(context, '/user', arguments: {'user_id': uid});
  }

  // ── 地图（wx.openLocation → Apple Maps 链接）──

  Future<void> _onOpenLocation() async {
    final note = _note;
    final lat = note?.latitude;
    final lng = note?.longitude;
    if (note == null || lat == null || lng == null) {
      showToast(context, '暂无精确坐标');
      return;
    }
    final name = note.locationName.isNotEmpty ? note.locationName : '笔记地点';
    final uri = Uri.parse('https://maps.apple.com/?ll=$lat,$lng&q=${Uri.encodeComponent(name)}');
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (mounted) showToast(context, '无法打开地图');
    }
  }

  // ── 分享（小程序 open-type=share → 系统分享标题文本）──

  void _onShare() {
    final note = _note;
    if (note == null) return;
    Share.share(note.title.isNotEmpty ? note.title : 'UChance 网球笔记');
  }

  // ── 评论（对齐评论区逻辑）──

  bool _canDelete(NoteComment c) {
    final me = _app.userId;
    return me.isNotEmpty && c.authorId == me;
  }

  void _onReply(NoteComment c) {
    if (!requireLogin(context, from: 'comment')) return;
    setState(() {
      _replyTo = (id: c.id, name: c.authorName.isNotEmpty ? c.authorName : '球友');
    });
    _commentFocus.requestFocus();
  }

  void _onCancelReply() => setState(() => _replyTo = null);

  Future<void> _onSubmitComment() async {
    final text = _commentCtrl.text;
    if (text.isEmpty) {
      showToast(context, '评论不能为空');
      return;
    }
    if (!requireLogin(context, from: 'comment')) return;
    final note = _note;
    if (note == null) return;
    setState(() => _submitting = true);
    try {
      await _social.postComment(note.id, text, parentId: _replyTo?.id ?? '');
      if (!mounted) return;
      setState(() {
        _commentCtrl.clear();
        _replyTo = null;
        _submitting = false;
      });
      showToast(context, '已发送');
      await _loadComments();
    } catch (e) {
      if (!mounted) return;
      setState(() => _submitting = false);
      showToast(context, e is ApiException && e.message.isNotEmpty ? e.message : '网络错误');
    }
  }

  Future<void> _onDeleteComment(NoteComment c) async {
    final note = _note;
    if (note == null || c.id.isEmpty) return;
    final ok = await showConfirm(context, title: '删除评论', content: '确定删除？', danger: true);
    if (!ok || !mounted) return;
    try {
      await _social.deleteComment(note.id, c.id);
      if (!mounted) return;
      showToast(context, '已删除');
      await _loadComments();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e is ApiException && e.message.isNotEmpty ? e.message : '网络错误');
    }
  }

  // ── 图片预览（对齐 wx.previewImage）──

  void _onPreview(int index) {
    final images = _note?.images ?? const <String>[];
    if (images.isEmpty) return;
    showDialog<void>(
      context: context,
      barrierColor: Colors.black,
      builder: (_) => _ImagePreview(urls: images, initial: index),
    );
  }

  // ── 构建 ──

  @override
  Widget build(BuildContext context) {
    final loggedIn = context.watch<AppState>().isLoggedIn;
    final note = _note;
    return Scaffold(
      appBar: themedAppBar(context, title: '笔记详情'),
      body: ThemedPage(
        child: note == null ? _buildEmpty() : _buildContent(note, loggedIn),
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 60),
        child: Text(
          _errorText.isNotEmpty ? _errorText : '加载中…',
          style: const TextStyle(color: Color(0xFF8A8A8A), fontSize: 14),
        ),
      ),
    );
  }

  Widget _buildContent(FeedItem note, bool loggedIn) {
    final canOpenMap = note.latitude != null && note.longitude != null;
    return ListView(
      padding: EdgeInsets.only(bottom: 12 + MediaQuery.of(context).padding.bottom),
      children: [
        if (note.images.isNotEmpty) _buildSwiper(note),
        if (note.userId.isNotEmpty) _buildAuthorRow(note),
        _buildBodyCard(note, canOpenMap),
        _buildActionBar(note),
        _buildCommentDock(loggedIn),
      ],
    );
  }

  // 多图 swiper + 指示器（对齐 .swiper，高 720rpx→360）
  Widget _buildSwiper(FeedItem note) {
    final accent = slamOf(context).accent;
    return Container(
      height: 360,
      color: const Color(0xFF111111),
      child: Stack(
        children: [
          PageView.builder(
            itemCount: note.images.length,
            onPageChanged: (i) => setState(() => _imageIndex = i),
            itemBuilder: (_, i) => GestureDetector(
              onTap: () => _onPreview(i),
              child: CachedNetworkImage(
                imageUrl: note.images[i],
                fit: BoxFit.cover,
                width: double.infinity,
                height: double.infinity,
                errorWidget: (_, __, ___) => const SizedBox.expand(),
              ),
            ),
          ),
          if (note.images.length > 1)
            Positioned(
              left: 0,
              right: 0,
              bottom: 10,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (var i = 0; i < note.images.length; i++)
                    Container(
                      width: 6,
                      height: 6,
                      margin: const EdgeInsets.symmetric(horizontal: 3),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: i == _imageIndex ? accent : Colors.white.withValues(alpha: 0.5),
                      ),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  // 作者行（对齐 .author-row）
  Widget _buildAuthorRow(FeedItem note) {
    final theme = slamOf(context);
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: S.card(),
      child: Row(
        children: [
          Avatar(url: note.authorAvatar, initial: note.authorInitial, size: 36, onTap: _onOpenAuthor),
          const SizedBox(width: 8),
          Expanded(
            child: GestureDetector(
              onTap: _onOpenAuthor,
              behavior: HitTestBehavior.opaque,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    note.authorName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink),
                  ),
                  const SizedBox(height: 2),
                  Text(_timeText(note), style: const TextStyle(fontSize: 11, color: S.faint)),
                ],
              ),
            ),
          ),
          if (!_isMine)
            GestureDetector(
              onTap: _onToggleFollow,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                decoration: BoxDecoration(
                  color: _following ? S.line : theme.accent,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  _following ? '已关注' : '关注',
                  style: TextStyle(
                    fontSize: 12,
                    color: _following ? const Color(0xFF5C6570) : theme.accentInk,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  // 标题 / 正文 / 地点（对齐 .body-card）
  Widget _buildBodyCard(FeedItem note, bool canOpenMap) {
    final body = note.body.isNotEmpty ? note.body : note.summary;
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(14),
      decoration: S.card(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(note.title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: S.ink)),
          const SizedBox(height: 6),
          SelectableText(
            body,
            style: const TextStyle(fontSize: 14, color: Color(0xFF333333), height: 1.65),
          ),
          if (note.locationName.isNotEmpty || note.locationAddress.isNotEmpty) ...[
            const SizedBox(height: 10),
            GestureDetector(
              onTap: _onOpenLocation,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 9),
                decoration: BoxDecoration(
                  color: const Color(0xFFF7FAF9),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.location_on, size: 18, color: slamOf(context).accent),
                    const SizedBox(width: 7),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            note.locationName.isNotEmpty ? note.locationName : '地点',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: S.ink),
                          ),
                          if (note.locationAddress.isNotEmpty) ...[
                            const SizedBox(height: 2),
                            Text(
                              note.locationAddress,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 11, color: S.faint),
                            ),
                          ],
                        ],
                      ),
                    ),
                    if (canOpenMap)
                      Text('地图', style: TextStyle(fontSize: 12, color: slamOf(context).accent)),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  // 赞 / 收藏 / 分享 / 删除（对齐 .action-bar）
  Widget _buildActionBar(FeedItem note) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
      child: Row(
        children: [
          if (!_isMine) ...[
            _actionChip(
              text: '${_liked ? '♥' : '♡'} ${_liked ? '已赞' : '赞'}'
                  '${note.likeCount > 0 ? ' ${note.likeCount}' : ''}',
              on: _liked,
              onTap: _onToggleLike,
            ),
            const SizedBox(width: 6),
            _actionChip(
              text: '${_bookmarked ? '★' : '☆'} ${_bookmarked ? '已收藏' : '收藏'}',
              on: _bookmarked,
              onTap: _onToggleBookmark,
            ),
            const SizedBox(width: 6),
          ],
          _actionChip(text: '↗ 分享', onTap: _onShare),
          if (_isMine) ...[
            const SizedBox(width: 6),
            Expanded(
              child: GestureDetector(
                onTap: _onDelete,
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 7),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: S.danger.withValues(alpha: 0.25)),
                  ),
                  alignment: Alignment.center,
                  child: const Text(
                    '删除笔记',
                    style: TextStyle(fontSize: 12, height: 1.2, color: S.danger),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _actionChip({required String text, bool on = false, VoidCallback? onTap}) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 7),
          decoration: BoxDecoration(
            color: on ? const Color(0xFFE8FAF4) : const Color(0xFFF5F7F9),
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(
            text,
            style: TextStyle(
              fontSize: 12,
              height: 1.2,
              fontWeight: on ? FontWeight.w600 : FontWeight.w500,
              color: on ? const Color(0xFF0D3D32) : S.sub,
            ),
          ),
        ),
      ),
    );
  }

  // 评论区（对齐 .comment-dock）
  Widget _buildCommentDock(bool loggedIn) {
    return Container(
      margin: const EdgeInsets.all(12),
      decoration: S.card(),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 0),
            child: Text(
              '评论 $_commentTotal',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink),
            ),
          ),
          const SizedBox(height: 10),
          if (_comments.isNotEmpty)
            Column(children: [for (final c in _comments) _buildRootComment(c)])
          else
            const Padding(
              padding: EdgeInsets.fromLTRB(14, 20, 14, 10),
              child: Center(
                child: Text('还没有评论，来评个吧~', style: TextStyle(fontSize: 12, color: S.faint)),
              ),
            ),
          if (_replyTo != null)
            GestureDetector(
              onTap: _onCancelReply,
              behavior: HitTestBehavior.opaque,
              child: Container(
                color: Colors.white,
                padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '回复 @${_replyTo!.name}',
                      style: TextStyle(fontSize: 11, color: slamOf(context).accent),
                    ),
                    const Text('取消', style: TextStyle(fontSize: 11, color: S.faint)),
                  ],
                ),
              ),
            ),
          _buildCommentInput(loggedIn),
        ],
      ),
    );
  }

  Widget _buildRootComment(NoteComment c) {
    return Column(
      children: [
        _commentItem(c),
        if (c.replies.isNotEmpty)
          Container(
            color: const Color(0xFFFAFBFC),
            padding: const EdgeInsets.only(left: 20),
            child: Column(
              children: [for (final r in c.replies) _commentItem(r, root: c)],
            ),
          ),
      ],
    );
  }

  Widget _commentItem(NoteComment c, {NoteComment? root}) {
    // 回复他人回复时显示「回复 xx：」（对齐 reply_to_name；父级是根评论时省略）
    final isReply = root != null;
    final toName = isReply && c.parentId.isNotEmpty && c.parentId != root.id
        ? _nameById[c.parentId] ?? ''
        : '';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: Color(0xFFEEF0F3), width: 0.5)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Avatar(url: c.authorAvatar, initial: c.initial, size: 20),
          const SizedBox(width: 7),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  c.authorName,
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: S.ink),
                ),
                const SizedBox(height: 3),
                Text.rich(
                  TextSpan(
                    children: [
                      if (toName.isNotEmpty)
                        TextSpan(
                          text: '回复 $toName：',
                          style: const TextStyle(color: Color(0xFF5B6B7A), fontWeight: FontWeight.w500),
                        ),
                      TextSpan(text: c.body),
                    ],
                  ),
                  style: const TextStyle(fontSize: 11, color: Color(0xFF4A5568), height: 1.5),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(c.timeText, style: const TextStyle(fontSize: 10, color: S.faint)),
                    const SizedBox(width: 10),
                    GestureDetector(
                      onTap: () => _onReply(c),
                      behavior: HitTestBehavior.opaque,
                      child: const Text(
                        '回复',
                        style: TextStyle(fontSize: 10, color: Color(0xFF5B6B7A), fontWeight: FontWeight.w500),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          if (_canDelete(c))
            GestureDetector(
              onTap: () => _onDeleteComment(c),
              child: const SizedBox(
                width: 15,
                height: 15,
                child: Center(
                  child: Text('×', style: TextStyle(fontSize: 12, color: Color(0xFFD0D5DD))),
                ),
              ),
            ),
        ],
      ),
    );
  }

  // 评论输入区（对齐 .comment-input-wrapper）
  Widget _buildCommentInput(bool loggedIn) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: Color(0xFFEEF0F3), width: 0.5)),
      ),
      child: loggedIn
          ? Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _commentCtrl,
                    focusNode: _commentFocus,
                    maxLength: 140,
                    onChanged: (_) => setState(() {}),
                    style: const TextStyle(fontSize: 12, color: Color(0xFF333333)),
                    cursorColor: S.green,
                    decoration: InputDecoration(
                      hintText: _replyTo != null ? '回复 @${_replyTo!.name}... (最多140字)' : _placeholder,
                      hintStyle: const TextStyle(fontSize: 12, color: Color(0xFFC0C5CE)),
                      counterText: '',
                      isDense: true,
                      filled: true,
                      fillColor: const Color(0xFFF7F8FA),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(999),
                        borderSide: BorderSide.none,
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(999),
                        borderSide: BorderSide.none,
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(999),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                ),
                if (_commentCtrl.text.isNotEmpty) ...[
                  const SizedBox(width: 6),
                  GestureDetector(
                    onTap: _submitting ? null : _onSubmitComment,
                    child: Container(
                      width: 40,
                      height: 32,
                      decoration: BoxDecoration(
                        color: slamOf(context).accent.withValues(alpha: _submitting ? 0.5 : 1),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      alignment: Alignment.center,
                      child: _submitting
                          ? SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: slamOf(context).accentInk,
                              ),
                            )
                          : Text(
                              '发',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: slamOf(context).accentInk,
                              ),
                            ),
                    ),
                  ),
                ],
              ],
            )
          : GestureDetector(
              onTap: () => requireLogin(context, from: 'comment'),
              child: Container(
                width: 80,
                height: 32,
                decoration: BoxDecoration(
                  color: const Color(0xFFF7F8FA),
                  borderRadius: BorderRadius.circular(999),
                ),
                alignment: Alignment.center,
                child: const Text('登录后评论', style: TextStyle(fontSize: 11, color: Color(0xFF8A8A8A))),
              ),
            ),
    );
  }
}

/// 全屏图片预览（对齐 wx.previewImage：左右滑动 + 点按关闭）
class _ImagePreview extends StatefulWidget {
  const _ImagePreview({required this.urls, this.initial = 0});

  final List<String> urls;
  final int initial;

  @override
  State<_ImagePreview> createState() => _ImagePreviewState();
}

class _ImagePreviewState extends State<_ImagePreview> {
  late final PageController _ctrl = PageController(initialPage: widget.initial);
  late int _index = widget.initial;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Dialog.fullscreen(
      backgroundColor: Colors.black,
      child: Stack(
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: PageView.builder(
              controller: _ctrl,
              itemCount: widget.urls.length,
              onPageChanged: (i) => setState(() => _index = i),
              itemBuilder: (_, i) => InteractiveViewer(
                maxScale: 4,
                child: Center(
                  child: CachedNetworkImage(
                    imageUrl: widget.urls[i],
                    fit: BoxFit.contain,
                    placeholder: (_, __) =>
                        const Center(child: CircularProgressIndicator(color: Colors.white54)),
                    errorWidget: (_, __, ___) =>
                        const Icon(Icons.broken_image, color: Colors.white54, size: 48),
                  ),
                ),
              ),
            ),
          ),
          if (widget.urls.length > 1)
            Positioned(
              left: 0,
              right: 0,
              bottom: 24,
              child: Center(
                child: Text(
                  '${_index + 1}/${widget.urls.length}',
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                ),
              ),
            ),
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            right: 12,
            child: IconButton(
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(Icons.close, color: Colors.white, size: 26),
            ),
          ),
        ],
      ),
    );
  }
}
