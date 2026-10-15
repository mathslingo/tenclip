import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/social_api.dart';
import '../core/api_client.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 关注 / 粉丝列表（对齐 miniprogram pages/follow-list/index）
class FollowListPage extends StatefulWidget {
  const FollowListPage({super.key, required this.userId, this.kind = 'following'});

  final String userId;

  /// 'following' | 'followers'
  final String kind;

  @override
  State<FollowListPage> createState() => _FollowListPageState();
}

class _FollowListPageState extends State<FollowListPage> {
  late String _kind = widget.kind == 'followers' ? 'followers' : 'following';
  List<SocialUser> _items = [];
  bool _loading = true;

  AppState get _app => context.read<AppState>();
  SocialApi get _social => context.read<SocialApi>();

  String get _meId => _app.userId;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _reload());
  }

  void _onKind(String kind) {
    if (kind == _kind) return;
    setState(() => _kind = kind);
    _reload();
  }

  Future<void> _reload() async {
    final me = _meId;
    setState(() => _loading = true);
    try {
      final items = await _social.fetchFollowList(widget.userId, _kind);
      // 逐个补全 is_following（列表接口不带关注态，对齐小程序 reload）
      final full = await Future.wait(items.map((u) async {
        if (u.userId == me) {
          u.isFollowing = false;
          return u;
        }
        try {
          final f = await _social.fetchUser(u.userId, viewerId: me);
          u.isFollowing = f.isFollowing;
        } catch (_) {
          u.isFollowing = _kind == 'following' && widget.userId == me;
        }
        return u;
      }));
      if (!mounted) return;
      setState(() {
        _items = full;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _items = [];
        _loading = false;
      });
    }
  }

  Future<void> _onToggle(SocialUser target) async {
    if (target.userId.isEmpty || target.userId == _meId) return;
    if (!requireLogin(context, from: 'follow')) return;
    final was = target.isFollowing;
    try {
      if (was) {
        await _social.unfollow(target.userId);
      } else {
        await _social.follow(target.userId);
      }
      if (!mounted) return;
      setState(() => target.isFollowing = !was);
    } catch (e) {
      if (!mounted) return;
      showToast(context, e is ApiException ? e.message : '操作失败');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: themedAppBar(context, title: _kind == 'followers' ? '粉丝' : '关注'),
      body: ThemedPage(
        child: ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            // 分段切换（对齐 .tabs / .tab）
            Container(
              margin: const EdgeInsets.fromLTRB(12, 10, 12, 10),
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Row(
                children: [
                  _tab('关注', 'following'),
                  _tab('粉丝', 'followers'),
                ],
              ),
            ),
            for (final u in _items) _row(u),
            if (!_loading && _items.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
                child: Center(
                  child: Text(
                    _kind == 'followers' ? '还没有粉丝' : '还没有关注任何人',
                    style: const TextStyle(color: Color(0xFF8A8A8A), fontSize: 14),
                  ),
                ),
              ),
            if (_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 40),
                child: Center(
                  child: Text('加载中…', style: TextStyle(color: Color(0xFF8A8A8A), fontSize: 14)),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _tab(String label, String kind) {
    final on = _kind == kind;
    return Expanded(
      child: GestureDetector(
        onTap: () => _onKind(kind),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: on ? const Color(0xFFD4FFF4) : Colors.transparent,
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              fontWeight: on ? FontWeight.w700 : FontWeight.w400,
              color: on ? const Color(0xFF0D3D32) : const Color(0xFF6E7582),
            ),
          ),
        ),
      ),
    );
  }

  Widget _row(SocialUser u) {
    return GestureDetector(
      onTap: u.userId.isEmpty
          ? null
          : () => Navigator.pushNamed(context, '/user', arguments: {'user_id': u.userId}),
      behavior: HitTestBehavior.opaque,
      child: Container(
        margin: const EdgeInsets.fromLTRB(12, 0, 12, 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          children: [
            Avatar(url: u.avatarUrl, initial: u.initial, size: 36),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    u.nickname,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink),
                  ),
                  if (u.bio.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      u.bio,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 11, color: Color(0xFF9AA3AD)),
                    ),
                  ],
                ],
              ),
            ),
            if (u.userId != _meId) ...[
              const SizedBox(width: 8),
              GestureDetector(
                onTap: () => _onToggle(u),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                  decoration: BoxDecoration(
                    color: u.isFollowing ? const Color(0xFFEEF1F4) : const Color(0xFF13D8A8),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    u.isFollowing ? '已关注' : '关注',
                    style: TextStyle(
                      fontSize: 12,
                      color: u.isFollowing ? const Color(0xFF5C6570) : Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
