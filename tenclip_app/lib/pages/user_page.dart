import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../api/social_api.dart';
import '../core/api_client.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 他人主页（对齐 miniprogram pages/user/index）
class UserPage extends StatefulWidget {
  const UserPage({super.key, required this.userId});

  final String userId;

  @override
  State<UserPage> createState() => _UserPageState();
}

class _UserPageState extends State<UserPage> {
  SocialUser? _user;
  List<FeedItem> _left = [];
  List<FeedItem> _right = [];
  int _notesCount = 0;
  bool _isMine = false;
  bool _following = false;
  bool _loading = true;
  String _errorText = '';

  AppState get _app => context.read<AppState>();
  SocialApi get _social => context.read<SocialApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.userId.trim().isEmpty) {
        setState(() {
          _loading = false;
          _errorText = '缺少用户 id';
        });
        return;
      }
      _reload();
    });
  }

  Future<void> _reload({bool quiet = false}) async {
    final uid = widget.userId;
    final me = _app.userId;
    if (!quiet) {
      setState(() {
        _loading = true;
        _errorText = '';
      });
    }
    try {
      final results = await Future.wait([
        _social.fetchUser(uid, viewerId: me),
        _social.listNotes(userId: uid).catchError((_) => <FeedItem>[]),
      ]);
      if (!mounted) return;
      final u = results[0] as SocialUser;
      final notes = results[1] as List<FeedItem>;
      final cols = splitWaterfall(notes);
      setState(() {
        _loading = false;
        _user = u;
        _left = cols.left;
        _right = cols.right;
        _notesCount = notes.length;
        _isMine = u.userId == me;
        _following = u.isFollowing;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _user = null;
        _errorText = '加载失败';
      });
    }
  }

  /// 标签（对齐 buildTags；SocialUser 仅含 tags / tennisLevel，其余字段小程序有、模型暂无）
  List<String> _buildTags(SocialUser u) {
    final tags = <String>[];
    for (final t in u.tags) {
      final s = t.trim();
      if (s.isNotEmpty && !tags.contains(s)) tags.add(s);
    }
    final lv = u.tennisLevel.trim();
    if (lv.isNotEmpty) {
      final v = 'NTRP $lv';
      if (!tags.contains(v)) tags.add(v);
    }
    return tags.take(8).toList();
  }

  void _onCopyId() {
    final id = _user?.userId ?? '';
    if (id.isEmpty) return;
    Clipboard.setData(ClipboardData(text: id));
    showToast(context, '已复制');
  }

  Future<void> _onToggleFollow() async {
    final u = _user;
    if (u == null || _isMine) return;
    if (!requireLogin(context, from: 'follow')) return;
    final was = _following;
    try {
      if (was) {
        await _social.unfollow(u.userId);
      } else {
        await _social.follow(u.userId);
      }
      if (!mounted) return;
      setState(() {
        _following = !was;
        u.isFollowing = !was;
        if (!was) {
          u.followers += 1;
        } else if (u.followers > 0) {
          u.followers -= 1;
        }
      });
      showToast(context, !was ? '已关注' : '已取消关注');
    } catch (e) {
      if (!mounted) return;
      showToast(context, e is ApiException ? e.message : '操作失败');
    }
  }

  void _onTapFollowList(String kind) {
    Navigator.pushNamed(context, '/follow-list',
        arguments: {'kind': kind, 'user_id': widget.userId});
  }

  @override
  Widget build(BuildContext context) {
    final u = _user;
    return Scaffold(
      appBar: themedAppBar(context, title: u?.nickname ?? ''),
      body: ThemedPage(
        child: u == null
            ? _loading
                ? const Padding(
                    padding: EdgeInsets.symmetric(vertical: 120, horizontal: 20),
                    child: Center(
                      child: Text('加载中…', style: TextStyle(color: Color(0xFF9AA3AD), fontSize: 14)),
                    ),
                  )
                : Padding(
                    padding: const EdgeInsets.only(top: 120),
                    child: EmptyHint(_errorText.isEmpty ? '用户不存在' : _errorText),
                  )
            : RefreshIndicator(
                onRefresh: () => _reload(quiet: true),
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.only(bottom: 24),
                  children: [
                    _hero(u),
                    _sectionBar(),
                    if (_left.isNotEmpty || _right.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(10, 0, 10, 12),
                        child: Waterfall(left: _left, right: _right, showAuthor: false),
                      )
                    else
                      const EmptyHint('还没有公开笔记', sub: '球友发布后会出现在这里'),
                  ],
                ),
              ),
      ),
    );
  }

  /// 资料区（对齐 .hero：固定绿色渐变，不随主题变化）
  Widget _hero(SocialUser u) {
    final tags = _buildTags(u);
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 16),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0F3D34), Color(0xFF147A62), Color(0xFF13D8A8)],
          stops: [0.0, 0.48, 1.0],
        ),
      ),
      child: Stack(
        children: [
          // 装饰光斑（对齐 .hero-glow）
          Positioned(
            right: -40,
            top: -30,
            child: Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.12),
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 66,
                    height: 66,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white.withValues(alpha: 0.9), width: 3),
                      boxShadow: const [
                        BoxShadow(color: Color(0x2E000000), blurRadius: 14, offset: Offset(0, 5)),
                      ],
                    ),
                    child: Avatar(url: u.avatarUrl, initial: u.initial, size: 60),
                  ),
                  const SizedBox(width: 11),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          u.nickname,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                            height: 1.2,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Row(
                          children: [
                            Flexible(
                              child: Text(
                                'UChance号 ${u.userId}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.white.withValues(alpha: 0.82),
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            GestureDetector(
                              onTap: _onCopyId,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.18),
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: const Text('复制',
                                    style: TextStyle(fontSize: 10, color: Colors.white)),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  _stat('${u.following}', '关注', () => _onTapFollowList('following')),
                  _stat('${u.followers}', '粉丝', () => _onTapFollowList('followers')),
                  _stat('$_notesCount', '笔记', null),
                ],
              ),
              const SizedBox(height: 11),
              Text(
                u.bio.isNotEmpty ? u.bio : '这个球友还没有简介',
                style: TextStyle(
                  fontSize: 13,
                  height: 1.55,
                  color: u.bio.isNotEmpty
                      ? Colors.white.withValues(alpha: 0.92)
                      : Colors.white.withValues(alpha: 0.65),
                ),
              ),
              if (tags.isNotEmpty) ...[
                const SizedBox(height: 9),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final t in tags)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.88),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(t,
                            style: const TextStyle(fontSize: 11, color: Color(0xFF0D3D32))),
                      ),
                  ],
                ),
              ],
              const SizedBox(height: 14),
              if (!_isMine)
                _heroButton(
                  _following ? '已关注' : '关注',
                  bg: _following ? Colors.white.withValues(alpha: 0.22) : Colors.white,
                  fg: _following ? Colors.white : const Color(0xFF0D3D32),
                  onTap: _onToggleFollow,
                )
              else
                _heroButton(
                  '编辑资料',
                  bg: Colors.white.withValues(alpha: 0.92),
                  fg: const Color(0xFF0D3D32),
                  onTap: () => Navigator.pushNamed(context, '/profile-edit'),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _stat(String num, String label, VoidCallback? onTap) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        constraints: const BoxConstraints(minWidth: 60),
        padding: const EdgeInsets.only(right: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              num,
              style: const TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w700,
                color: Colors.white,
                height: 1.1,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(fontSize: 11, color: Colors.white.withValues(alpha: 0.78)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _heroButton(String label,
      {required Color bg, required Color fg, required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        height: 38,
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
        alignment: Alignment.center,
        child: Text(
          label,
          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: fg),
        ),
      ),
    );
  }

  /// 「笔记」分节标题（对齐 .section-bar）
  Widget _sectionBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.baseline,
        textBaseline: TextBaseline.alphabetic,
        children: [
          const Text(
            '笔记',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: S.ink),
          ),
          const SizedBox(width: 5),
          Text('$_notesCount', style: const TextStyle(fontSize: 12, color: Color(0xFF9AA3AD))),
        ],
      ),
    );
  }
}
