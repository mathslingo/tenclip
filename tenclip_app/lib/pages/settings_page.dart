import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../main.dart' show requireLogin;
import '../state/app_state.dart';
import '../theme/slam_theme.dart';
import '../widgets/common.dart';

/// 设置（对齐 miniprogram pages/settings）
///
/// 球场风格切换 / 账号（退出登录、去登录）/ 关于与协议入口。
/// 小程序的「开发者选项」依赖打包白名单（isDevModeAllowed），
/// 「数据源与调试」仅 localDev 显示，iOS 端均无对应设施，故不下移。
class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  Future<void> _onLogout(BuildContext context) async {
    final ok = await showConfirm(
      context,
      title: '退出登录',
      content: '退出后可用昵称+密码重新登录同一游客账号；也可先逛逛',
      confirmText: '退出',
      danger: true,
    );
    if (!ok || !context.mounted) return;
    final app = context.read<AppState>();
    try {
      await app.logout();
    } catch (_) {}
    app.enterGuest();
    if (!context.mounted) return;
    showToast(context, '已退出');
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final slam = context.watch<SlamController>();
    final loggedIn = app.isLoggedIn;
    final uid = app.userId;

    return Scaffold(
      appBar: themedAppBar(context, title: '设置'),
      body: ThemedPage(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 20),
          children: [
            // ── 球场风格（对齐 slam-grid / slam-chip）──
            SlamCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('球场风格', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: S.ink)),
                  const SizedBox(height: 12),
                  LayoutBuilder(
                    builder: (context, c) {
                      final w = (c.maxWidth - 8) / 2;
                      return Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final t in SlamTheme.all)
                            SizedBox(
                              width: w,
                              child: _SlamChip(
                                theme: t,
                                selected: t.id == slam.theme.id,
                                onTap: () => context.read<SlamController>().setTheme(t.id),
                              ),
                            ),
                        ],
                      );
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // ── 账号 ──
            SlamCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('账号', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: S.ink)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              loggedIn ? '已登录' : '游客模式',
                              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              loggedIn ? '用户号 $uid' : '发笔记、关注需登录',
                              style: const TextStyle(fontSize: 11, color: S.faint, height: 1.4),
                            ),
                          ],
                        ),
                      ),
                      GestureDetector(
                        onTap: loggedIn ? () => _onLogout(context) : () => requireLogin(context, from: 'settings'),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                          decoration: BoxDecoration(
                            color: loggedIn ? const Color(0xFFFDE8E8) : slam.theme.accent,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            loggedIn ? '退出登录' : '去登录',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: loggedIn ? S.danger : slam.theme.accentInk,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // ── 关于与协议 ──
            SlamCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('关于', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: S.ink)),
                  const SizedBox(height: 4),
                  _linkRow(context, '隐私政策', () => Navigator.pushNamed(context, '/legal-privacy')),
                  _linkRow(context, '用户协议', () => Navigator.pushNamed(context, '/legal-terms')),
                  const SizedBox(height: 8),
                  const Text('Build $appBuildTag', style: TextStyle(fontSize: 10, color: Color(0xFFB0B7C0))),
                  const SizedBox(height: 2),
                  const Text('API $apiBaseUrl', style: TextStyle(fontSize: 10, color: Color(0xFFB0B7C0))),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _linkRow(BuildContext context, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            Expanded(child: Text(label, style: const TextStyle(fontSize: 14, color: S.ink))),
            const Icon(Icons.chevron_right, size: 18, color: S.faint),
          ],
        ),
      ),
    );
  }
}

/// 大满贯主题 chip（对齐 .slam-chip；swatch 为 courtA→courtB 条纹渐变）
class _SlamChip extends StatelessWidget {
  const _SlamChip({required this.theme, required this.selected, this.onTap});

  final SlamTheme theme;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 66,
        padding: const EdgeInsets.fromLTRB(9, 0, 9, 10),
        decoration: BoxDecoration(
          // swatch：42% / 58% 处切换出一条浅色场带
          gradient: LinearGradient(
            colors: [theme.courtA, theme.courtA, theme.courtB, theme.courtB, theme.courtA, theme.courtA],
            stops: const [0, 0.42, 0.42, 0.58, 0.58, 1],
          ),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: selected ? Colors.white : Colors.transparent, width: 1.5),
          boxShadow: selected
              ? [BoxShadow(color: Colors.white.withValues(alpha: 0.35), spreadRadius: 2)]
              : null,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.end,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(theme.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.white)),
            const SizedBox(height: 3),
            Text(theme.hint, style: const TextStyle(fontSize: 11, color: Colors.white70)),
          ],
        ),
      ),
    );
  }
}
