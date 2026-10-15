import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/social_api.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 消息页（对齐 miniprogram pages/messages/index）
class MessagesPage extends StatefulWidget {
  const MessagesPage({super.key});

  @override
  State<MessagesPage> createState() => _MessagesPageState();
}

class _MessagesPageState extends State<MessagesPage> {
  List<AppNotification> _list = [];
  bool _loading = true;

  AppState get _app => context.read<AppState>();
  SocialApi get _social => context.read<SocialApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    if (!_app.isLoggedIn) {
      setState(() => _loading = false);
      return;
    }
    setState(() => _loading = true);
    try {
      final list = await _social.fetchMessages(limit: 50, offset: 0);
      if (!mounted) return;
      setState(() {
        _list = list;
        _loading = false;
      });
      // 进入页面即全部标记已读并清零角标（对齐小程序 load()）
      _social.markAllMessagesRead().catchError((_) {});
      _app.clearUnread();
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _typeText(AppNotification n) {
    switch (n.type) {
      case 'like':
        return '赞了你的笔记';
      case 'comment':
        return '评论了你';
      case 'reply':
        return '回复了你';
      case 'follow':
        return '关注了你';
      default:
        return '发来一条消息';
    }
  }

  void _onTapItem(AppNotification n) {
    if (n.type == 'follow') {
      if (n.actorId.isNotEmpty) {
        Navigator.pushNamed(context, '/user', arguments: {'user_id': n.actorId});
      }
      return;
    }
    if (n.noteId.isNotEmpty) {
      Navigator.pushNamed(context, '/note-detail', arguments: {'id': n.noteId});
    }
  }

  @override
  Widget build(BuildContext context) {
    final loggedIn = context.watch<AppState>().isLoggedIn;
    return Scaffold(
      appBar: themedAppBar(context, title: '消息'),
      body: ThemedPage(
        child: !loggedIn
            ? EmptyHint(
                '登录后查看消息',
                sub: '赞、评论与关注动态都在这里',
                cta: '去登录',
                onCta: () => requireLogin(context, from: 'messages'),
              )
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(0, 8, 0, 40),
                  children: [
                    if (_loading)
                      Padding(
                        padding: const EdgeInsets.only(top: 60),
                        child: Center(
                          child: Text('加载中…',
                              style: TextStyle(color: slamOf(context).ink, fontSize: 14)),
                        ),
                      )
                    else if (_list.isEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 60),
                        child: Center(
                          child: Text('暂无消息',
                              style: TextStyle(color: slamOf(context).ink, fontSize: 14)),
                        ),
                      )
                    else
                      Column(children: [for (final n in _list) _msgItem(n)]),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _msgItem(AppNotification n) {
    return GestureDetector(
      onTap: () => _onTapItem(n),
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(bottom: BorderSide(color: Color(0xFFF0F0F0), width: 0.5)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Avatar(
              url: n.actorAvatar,
              initial: n.actorName.isNotEmpty ? n.actorName[0] : '球',
              size: 36,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(
                          text: n.actorName,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF222222),
                          ),
                        ),
                        TextSpan(
                          text: ' ${_typeText(n)}',
                          style: const TextStyle(fontSize: 13, color: Color(0xFF888888)),
                        ),
                      ],
                    ),
                  ),
                  if (n.body.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      n.body,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13, color: Color(0xFF555555)),
                    ),
                  ],
                  const SizedBox(height: 3),
                  Text(
                    formatFeedTime(n.createdAt),
                    style: const TextStyle(fontSize: 11, color: Color(0xFFAAAAAA)),
                  ),
                ],
              ),
            ),
            if (!n.read)
              Container(
                width: 7,
                height: 7,
                margin: const EdgeInsets.only(top: 4),
                decoration: const BoxDecoration(
                  color: Color(0xFFFF4D4F),
                  shape: BoxShape.circle,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
