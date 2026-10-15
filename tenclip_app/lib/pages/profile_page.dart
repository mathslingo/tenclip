import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/auth_api.dart';
import '../api/social_api.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 「我的」Tab（对齐 miniprogram pages/profile）
class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  String _activeTab = 'works'; // works | bookmarks | likes
  List<FeedItem> _left = [];
  List<FeedItem> _right = [];
  String _emptyTitle = '';
  String _emptySub = '';
  String _emptyCta = '';
  int _worksCount = 0;

  AppState get _app => context.read<AppState>();
  AuthApi get _auth => context.read<AuthApi>();
  SocialApi get _social => context.read<SocialApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    final app = _app;
    if (app.isLoggedIn) {
      // 拉取服务端资料 → 本地（对齐 onShow 的 fetchMe + saveProfile）
      _auth.fetchMe().then((_) {
        if (mounted) setState(() {});
      }).catchError((_) {});
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
      _sessionSaveCounts(u.following, u.followers);
      setState(() {});
    } catch (_) {}
    try {
      final notes = await _social.listNotes(userId: uid);
      if (!mounted) return;
      setState(() => _worksCount = notes.length);
    } catch (_) {}
  }

  void _sessionSaveCounts(int following, int followers) {
    _app.saveMeProfile({'following': following, 'followers': followers});
  }

  // ── 空态文案（对齐 emptyCopy）──

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
    // bookmarks / likes 暂用本地 ID 列表（对齐小程序）
    final ids = tab == 'likes' ? _likedIds() : _bookmarkedIds();
    if (ids.isEmpty) {
      setState(() {
        _left = [];
        _right = [];
      });
      return;
    }
    final mockItems = ids
        .map((id) => FeedItem(
              id: id,
              title: tab == 'likes' ? '赞过的内容' : '收藏的内容',
              cover: '',
              coverRatio: 1,
              authorInitial: '球',
            ))
        .toList();
    final cols = splitWaterfall(mockItems);
    setState(() {
      _left = cols.left;
      _right = cols.right;
      _emptyTitle = '';
      _emptySub = '';
      _emptyCta = '';
    });
  }

  List<String> _likedIds() => context.read<AppState>().likedIds;
  List<String> _bookmarkedIds() => context.read<AppState>().bookmarkedIds;

  // ── 交互 ──

  void _onEditProfile() {
    if (!_app.isLoggedIn) {
      requireLogin(context, from: 'profile-edit');
      return;
    }
    Navigator.pushNamed(context, '/profile-edit');
  }

  void _onEmptyCta() {
    if (!_app.isLoggedIn) {
      requireLogin(context, from: 'profile');
      return;
    }
    if (_activeTab == 'works') {
      Navigator.pushNamed(context, '/note-compose', arguments: {'kind': 'note'});
    } else {
      // 去发现 Tab
      Navigator.of(context, rootNavigator: true).popUntil((r) => r.isFirst);
      // HomeShell 内部切换：通过全局 key 太绕，直接跳到发现页路由不可行（Tab 在 IndexedStack）
      // 简单处理：切到 feed 由用户点底栏；此处提示
      showToast(context, '点底部「发现」浏览内容');
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final profile = app.meProfile;
    final nickname = profile['nickname']?.toString() ?? '网球爱好者';
    final uid = app.userId.isNotEmpty ? app.userId : profile['uid']?.toString() ?? '';
    final stats = app.statsFromLists();
    final likesN = app.likedIds.length;
    final bmN = app.bookmarkedIds.length;

    // 网球水平行（对齐 tennisLine 组装）
    final bits = <String>[];
    if ('${profile['tennisHand']}'.isNotEmpty) bits.add('${profile['tennisHand']}');
    if ('${profile['tennisLevel']}'.isNotEmpty) bits.add('NTRP ${profile['tennisLevel']}');
    if ('${profile['tennis123Level']}'.isNotEmpty) bits.add('Tennis123 ${profile['tennis123Level']}');
    if ('${profile['tennisServeLevel']}'.isNotEmpty) bits.add('发${profile['tennisServeLevel']}');
    if ('${profile['tennisForehandLevel']}'.isNotEmpty) bits.add('正${profile['tennisForehandLevel']}');
    if ('${profile['tennisBackhandLevel']}'.isNotEmpty) bits.add('反${profile['tennisBackhandLevel']}');
    if ('${profile['tennisStyle']}'.isNotEmpty) bits.add('${profile['tennisStyle']}');
    if ('${profile['preferredSurface']}'.isNotEmpty) bits.add('${profile['preferredSurface']}');
    final tennisLine = bits.join(' · ');

    final tabs = <(String, String, int?)>[
      ('works', '作品', _worksCount),
      ('bookmarks', '收藏', bmN),
      ('likes', '赞过', likesN),
    ];

    return Scaffold(
      appBar: themedAppBar(context, title: '我的'),
      body: ThemedPage(
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 110),
            children: [
              // ── 资料卡 ──
              SlamCard(
                padding: const EdgeInsets.fromLTRB(14, 16, 14, 12),
                child: Column(
                  children: [
                    Avatar(
                      url: profile['avatarUrl']?.toString() ?? '',
                      initial: nickname.isNotEmpty ? nickname[0] : 'U',
                      size: 56,
                      onTap: _onEditProfile,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Flexible(
                          child: Text(
                            nickname,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: S.ink),
                          ),
                        ),
                        if ('${profile['gender']}'.isNotEmpty) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFFE8FAF4),
                              borderRadius: BorderRadius.circular(5),
                            ),
                            child: Text(
                              '${profile['gender']}',
                              style: const TextStyle(fontSize: 10, color: Color(0xFF0D6B52)),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '用户号 $uid${'${profile['location']}'.isNotEmpty ? ' · IP ${profile['location']}' : ''}',
                      style: const TextStyle(fontSize: 11, color: S.faint),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _pillButton('编辑资料', primary: true, onTap: _onEditProfile),
                        const SizedBox(width: 8),
                        _pillButton('设置', onTap: () => Navigator.pushNamed(context, '/settings')),
                      ],
                    ),
                    const SizedBox(height: 12),
                    const Divider(height: 1, color: S.line),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        _stat('${stats['following']}', '关注', () {
                          if (uid.isEmpty) return;
                          Navigator.pushNamed(context, '/follow-list',
                              arguments: {'kind': 'following', 'user_id': uid});
                        }),
                        _stat('${stats['followers']}', '粉丝', () {
                          if (uid.isEmpty) return;
                          Navigator.pushNamed(context, '/follow-list',
                              arguments: {'kind': 'followers', 'user_id': uid});
                        }),
                        _stat('${stats['likedCollect']}', '获赞与收藏', null),
                      ],
                    ),
                    if ('${profile['bio']}'.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text('${profile['bio']}', style: const TextStyle(fontSize: 12, color: S.sub)),
                    ],
                    if (tennisLine.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(tennisLine, style: const TextStyle(fontSize: 11, color: S.muted)),
                    ],
                    if ((profile['tags'] as List?)?.isNotEmpty ?? false) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          for (final t in (profile['tags'] as List))
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: const Color(0xFFE8FAF4),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text('$t', style: const TextStyle(fontSize: 10, color: Color(0xFF0D6B52))),
                            ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // ── 快捷入口（动作分析已在小程序下线，保持一致）──
              Row(
                children: [
                  _quickItem('✂', '剪辑视频', () => Navigator.pushNamed(context, '/stroke-extract')),
                  const SizedBox(width: 10),
                  _quickItem('◇', '测测球速', () => Navigator.pushNamed(context, '/pose-webview', arguments: {'url': ''})),
                ],
              ),
              const SizedBox(height: 12),

              // ── 内容标签 ──
              Container(
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
                                    fontWeight: _activeTab == t.$1 ? FontWeight.w600 : FontWeight.w400,
                                    color: _activeTab == t.$1 ? S.ink : S.faint,
                                  ),
                                ),
                                if (t.$3 != null) ...[
                                  const SizedBox(width: 4),
                                  Text('${t.$3}', style: const TextStyle(fontSize: 11, color: S.faint)),
                                ],
                              ],
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // ── 瀑布流 / 空态 ──
              if (_left.isNotEmpty || _right.isNotEmpty)
                Waterfall(left: _left, right: _right, showAuthor: false)
              else
                EmptyHint(_emptyTitle, sub: _emptySub, cta: _emptyCta, onCta: _onEmptyCta),
            ],
          ),
        ),
      ),
    );
  }

  Widget _pillButton(String label, {bool primary = false, VoidCallback? onTap}) {
    final theme = slamOf(context);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minWidth: 100),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: primary ? theme.accent : const Color(0xFFF2F4F6),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 12,
            fontWeight: primary ? FontWeight.w600 : FontWeight.w400,
            color: primary ? theme.accentInk : S.sub,
          ),
        ),
      ),
    );
  }

  Widget _stat(String num, String label, VoidCallback? onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Column(
          children: [
            Text(num, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: S.ink)),
            const SizedBox(height: 2),
            Text(label, style: const TextStyle(fontSize: 11, color: S.faint)),
          ],
        ),
      ),
    );
  }

  Widget _quickItem(String icon, String text, VoidCallback onTap) {
    return Expanded(
      child: SlamCard(
        onTap: onTap,
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Column(
          children: [
            Text(icon, style: const TextStyle(fontSize: 20, color: S.green)),
            const SizedBox(height: 4),
            Text(text, style: const TextStyle(fontSize: 12, color: S.sub)),
          ],
        ),
      ),
    );
  }
}
