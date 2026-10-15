import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/feed_api.dart';
import '../api/social_api.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 「我」个人中心（对齐 miniprogram pages/me）
///
/// 与 profile tab 不同：小红书式封面头图 + 身份面板 + 本地快捷编辑弹层，
/// 收藏/赞过通过 FeedApi.getFeedItemById 还原真实内容。
class MePage extends StatefulWidget {
  const MePage({super.key});

  @override
  State<MePage> createState() => _MePageState();
}

class _MePageState extends State<MePage> {
  String _activeTab = 'works'; // works | bookmarks | likes
  List<FeedItem> _left = [];
  List<FeedItem> _right = [];
  String _emptyTitle = '';
  String _emptySub = '';
  String _emptyCta = '';
  int _worksCount = 0;

  final _editNickCtrl = TextEditingController();
  final _editBioCtrl = TextEditingController();
  final _editTagsCtrl = TextEditingController();

  AppState get _app => context.read<AppState>();
  SocialApi get _social => context.read<SocialApi>();
  FeedApi get _feed => context.read<FeedApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  @override
  void dispose() {
    _editNickCtrl.dispose();
    _editBioCtrl.dispose();
    _editTagsCtrl.dispose();
    super.dispose();
  }

  // ── 数据（对齐 onShow / refreshProfile / loadTabContent）──

  Future<void> _refresh() async {
    if (!mounted) return;
    if (_app.isLoggedIn) {
      _social.upsertMe().catchError((_) {});
      _loadServerStats();
    }
    _loadTabContent(_activeTab);
  }

  Future<void> _loadServerStats() async {
    final uid = _app.userId;
    if (uid.isEmpty) return;
    try {
      final u = await _social.fetchUser(uid);
      if (!mounted) return;
      _app.saveMeProfile({'following': u.following, 'followers': u.followers});
      setState(() {});
    } catch (_) {}
    try {
      final notes = await _social.listNotes(userId: uid);
      if (!mounted) return;
      setState(() => _worksCount = notes.length);
    } catch (_) {}
  }

  void _applyEmptyCopy(String tab) {
    if (tab == 'works') {
      _emptyTitle = '还没有作品';
      _emptySub = '发一条网球笔记，记录训练与球场瞬间';
      _emptyCta = '去发笔记';
    } else if (tab == 'likes') {
      _emptyTitle = '还没有赞过';
      _emptySub = '在资讯详情里点赞，会出现在这里';
      _emptyCta = '去发现';
    } else {
      _emptyTitle = '还没有收藏';
      _emptySub = '收藏感兴趣的网球资讯，方便回看';
      _emptyCta = '去发现';
    }
  }

  Future<void> _loadTabContent(String tab) async {
    _applyEmptyCopy(tab);
    if (tab == 'works') {
      final uid = _app.userId;
      if (uid.isEmpty) {
        setState(() {
          _left = [];
          _right = [];
          _emptyTitle = '登录后查看作品';
          _emptySub = '登录后即可发笔记';
          _emptyCta = '去登录';
        });
        return;
      }
      try {
        final notes = await _social.listNotes(userId: uid);
        if (!mounted) return;
        setState(() {
          _worksCount = notes.length;
          if (notes.isEmpty) {
            _left = [];
            _right = [];
          } else {
            final cols = splitWaterfall(notes);
            _left = cols.left;
            _right = cols.right;
            _emptyTitle = '';
            _emptySub = '';
            _emptyCta = '';
          }
        });
      } catch (_) {
        if (mounted) {
          setState(() {
            _left = [];
            _right = [];
          });
        }
      }
      return;
    }
    // bookmarks / likes：按本地 ID 列表逐条取详情（对齐 getFeedItemById 逻辑）
    final ids = tab == 'likes' ? _app.likedIds : _app.bookmarkedIds;
    if (ids.isEmpty) {
      setState(() {
        _left = [];
        _right = [];
      });
      return;
    }
    final items = <FeedItem>[];
    for (final id in ids.take(40)) {
      try {
        final it = await _feed.getFeedItemById(id);
        if (it != null) items.add(it);
      } catch (_) {}
    }
    if (!mounted) return;
    final cols = splitWaterfall(items);
    setState(() {
      _left = cols.left;
      _right = cols.right;
      _emptyTitle = '';
      _emptySub = '';
      _emptyCta = '';
    });
  }

  // ── 交互 ──

  void _onEmptyCta() {
    if (!_app.isLoggedIn) {
      requireLogin(context, from: 'me');
      return;
    }
    if (_activeTab == 'works') {
      Navigator.pushNamed(context, '/note-compose', arguments: {'kind': 'note'});
    } else {
      // 发现在 HomeShell 的 IndexedStack 内，无法直接切 Tab（对齐 profile 页处理）
      showToast(context, '点底部「发现」浏览内容');
    }
  }

  void _goFollowList(String kind) {
    final uid = _app.userId;
    if (uid.isEmpty) return;
    Navigator.pushNamed(context, '/follow-list', arguments: {'kind': kind, 'user_id': uid});
  }

  /// 编辑资料弹层（对齐 editing + editForm：昵称 / 简介 / 兴趣标签，本地保存）
  void _openEditSheet() {
    final p = _app.meProfile;
    _editNickCtrl.text = p['nickname']?.toString() ?? '';
    _editBioCtrl.text = p['bio']?.toString() ?? '';
    _editTagsCtrl.text = ((p['tags'] as List?) ?? const []).join('，');
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: S.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetCtx) {
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(sheetCtx).viewInsets.bottom),
          child: SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 18),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Center(
                    child: Text('编辑资料',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32))),
                  ),
                  const SizedBox(height: 8),
                  _sheetLabel('昵称'),
                  SlamTextField(controller: _editNickCtrl, maxLength: 20),
                  const SizedBox(height: 12),
                  _sheetLabel('简介'),
                  SlamTextField(controller: _editBioCtrl, maxLines: 3, maxLength: 80),
                  const SizedBox(height: 12),
                  _sheetLabel('兴趣标签（逗号分隔）'),
                  SlamTextField(controller: _editTagsCtrl, maxLength: 40),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: _sheetButton('取消', ghost: true, onTap: () => Navigator.pop(sheetCtx)),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _sheetButton('保存', onTap: () => _saveEdit(sheetCtx)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  void _saveEdit(BuildContext sheetCtx) {
    var nick = _editNickCtrl.text.trim();
    if (nick.isEmpty) nick = '网球爱好者';
    final bio = _editBioCtrl.text.trim();
    final tags = _editTagsCtrl.text
        .split(RegExp(r'[,，\s]+'))
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .take(6)
        .toList();
    _app.saveMeProfile({'nickname': nick, 'bio': bio, 'tags': tags});
    Navigator.pop(sheetCtx);
    showToast(context, '已保存');
  }

  // ── UI ──

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final profile = app.meProfile;
    final nickname = profile['nickname']?.toString() ?? '网球爱好者';
    final uid = app.userId.isNotEmpty ? app.userId : profile['uid']?.toString() ?? '';
    final location = profile['location']?.toString() ?? '';
    final gender = profile['gender']?.toString() ?? '';
    final bio = profile['bio']?.toString() ?? '';
    final tags = (profile['tags'] as List?) ?? const [];
    final stats = app.statsFromLists();

    final tabs = <(String, String, int)>[
      ('works', '作品', _worksCount),
      ('bookmarks', '收藏', app.bookmarkedIds.length),
      ('likes', '赞过', app.likedIds.length),
    ];

    return Scaffold(
      appBar: themedAppBar(context, title: '我'),
      body: ThemedPage(
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            padding: const EdgeInsets.only(bottom: 60),
            children: [
              _buildCover(),
              Transform.translate(
                offset: const Offset(0, -36),
                child: Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: _buildPanel(profile, nickname, uid, location, gender, bio, tags, stats),
                    ),
                    const SizedBox(height: 10),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: _buildQuickRow(),
                    ),
                    const SizedBox(height: 14),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: _buildTabs(tabs),
                    ),
                    const SizedBox(height: 8),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: (_left.isNotEmpty || _right.isNotEmpty)
                          ? Waterfall(left: _left, right: _right, showAuthor: false)
                          : EmptyHint(_emptyTitle, sub: _emptySub, cta: _emptyCta, onCta: _onEmptyCta),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 封面头图 + 右上操作（对齐 .profile-cover / .cover-actions）
  Widget _buildCover() {
    return SizedBox(
      height: 140,
      child: Stack(
        children: [
          const Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment(-0.9, -1),
                  end: Alignment(0.9, 1),
                  colors: [Color(0xFF1A5C4A), Color(0xFF13D8A8), Color(0xFF7EE0C8)],
                  stops: [0, 0.48, 1],
                ),
              ),
            ),
          ),
          Positioned(
            top: 12,
            right: 12,
            child: Row(
              children: [
                _coverButton('设置', primary: false, onTap: () => Navigator.pushNamed(context, '/settings')),
                const SizedBox(width: 6),
                _coverButton('编辑资料', primary: true, onTap: _openEditSheet),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _coverButton(String label, {required bool primary, VoidCallback? onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
        decoration: BoxDecoration(
          color: primary ? Colors.white.withValues(alpha: 0.92) : Colors.black.withValues(alpha: 0.28),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: primary ? FontWeight.w600 : FontWeight.w400,
            color: primary ? const Color(0xFF0D3D32) : Colors.white,
          ),
        ),
      ),
    );
  }

  /// 身份面板（头像上探压封面，对齐 .profile-panel / .avatar-wrap 负边距）
  Widget _buildPanel(
    Map<String, dynamic> profile,
    String nickname,
    String uid,
    String location,
    String gender,
    String bio,
    List<dynamic> tags,
    Map<String, int> stats,
  ) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          width: double.infinity,
          margin: const EdgeInsets.only(top: 40),
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 12),
          decoration: BoxDecoration(
            color: S.cardBg,
            borderRadius: BorderRadius.circular(14),
            boxShadow: const [BoxShadow(color: Color(0x140D3D32), blurRadius: 14, offset: Offset(0, 4))],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const SizedBox(width: 82), // 给左上浮头像让位
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text(
                                nickname,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: S.ink),
                              ),
                            ),
                            if (gender.isNotEmpty) ...[
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFE8FAF4),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(gender,
                                    style: const TextStyle(fontSize: 10, color: Color(0xFF0D6B52))),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '用户号 $uid${location.isNotEmpty ? ' · IP $location' : ''}',
                          style: const TextStyle(fontSize: 11, color: S.faint),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  _stat('${stats['following']}', '关注', () => _goFollowList('following')),
                  const SizedBox(width: 20),
                  _stat('${stats['followers']}', '粉丝', () => _goFollowList('followers')),
                  const SizedBox(width: 20),
                  _stat('${stats['likedCollect']}', '获赞与收藏', null),
                ],
              ),
              if (bio.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(bio, style: const TextStyle(fontSize: 13, color: S.sub, height: 1.55)),
              ],
              if (tags.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final t in tags)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEEFAF6),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text('$t', style: const TextStyle(fontSize: 11, color: Color(0xFF0D6B52))),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
        Positioned(
          top: 0,
          left: 14,
          child: Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 3),
              boxShadow: const [BoxShadow(color: Color(0x1F000000), blurRadius: 10, offset: Offset(0, 3))],
            ),
            child: Avatar(
              url: profile['avatarUrl']?.toString() ?? '',
              initial: nickname.isNotEmpty ? nickname[0] : 'U',
              size: 64,
              onTap: _openEditSheet,
            ),
          ),
        ),
      ],
    );
  }

  /// 快捷入口（动作分析已在小程序下线，保持一致）
  Widget _buildQuickRow() {
    return Row(
      children: [
        _quickCard('✂', '剪辑视频', () => Navigator.pushNamed(context, '/stroke-extract')),
        const SizedBox(width: 6),
        _quickCard('◇', '测测球速', () => Navigator.pushNamed(context, '/pose-webview', arguments: {'url': ''})),
      ],
    );
  }

  Widget _quickCard(String icon, String label, VoidCallback onTap) {
    return Expanded(
      child: SlamCard(
        onTap: onTap,
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
        child: Column(
          children: [
            Text(icon, style: const TextStyle(fontSize: 16, color: Color(0xFF0D6B52), height: 1)),
            const SizedBox(height: 5),
            Text(label, style: const TextStyle(fontSize: 11, color: S.sub, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }

  /// 内容 Tab（对齐 .content-tabs；样式沿用 profile 页的白卡 + 主题色下划线）
  Widget _buildTabs(List<(String, String, int)> tabs) {
    return Container(
      decoration: S.card(radius: 10),
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          for (final t in tabs)
            Expanded(
              child: GestureDetector(
                onTap: () {
                  if (t.$1 == _activeTab) return;
                  setState(() => _activeTab = t.$1);
                  _loadTabContent(t.$1);
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  decoration: BoxDecoration(
                    border: Border(
                      bottom: BorderSide(
                        width: 2,
                        color: _activeTab == t.$1 ? slamOf(context).accent : Colors.transparent,
                      ),
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        t.$2,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: _activeTab == t.$1 ? FontWeight.w700 : FontWeight.w400,
                          color: _activeTab == t.$1 ? S.ink : S.muted,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Text('${t.$3}', style: const TextStyle(fontSize: 10, color: S.faint)),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _stat(String num, String label, VoidCallback? onTap) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(num, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: S.ink, height: 1.2)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 11, color: S.faint)),
        ],
      ),
    );
  }

  Widget _sheetLabel(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Text(text, style: const TextStyle(fontSize: 12, color: S.muted)),
    );
  }

  Widget _sheetButton(String label, {bool ghost = false, VoidCallback? onTap}) {
    final theme = slamOf(context);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 42,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: ghost ? const Color(0xFFEEF2F5) : theme.accent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: ghost ? S.sub : theme.accentInk,
          ),
        ),
      ),
    );
  }
}
