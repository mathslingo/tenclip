import 'package:flutter/material.dart';

import '../theme/slam_theme.dart';

/// 自定义底栏（对齐 miniprogram custom-tab-bar）：
/// 找球场 📍 · 发现 ▣ · 中间网球球（发笔记）· 有场 🎾 · 我的 👤
class AppTabBar extends StatelessWidget {
  const AppTabBar({
    super.key,
    required this.theme,
    required this.selectedIndex,
    required this.onTap,
    required this.onAction,
  });

  final SlamTheme theme;

  /// 0=找球场 1=发现 2=有场 3=我的（中间球不占 index）
  final int selectedIndex;
  final ValueChanged<int> onTap;

  /// 中间网球球点击
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).padding.bottom;
    return Container(
      decoration: BoxDecoration(
        color: theme.nav,
        border: Border(
          top: BorderSide(color: Colors.white.withValues(alpha: 0.18), width: 0.5),
        ),
      ),
      padding: EdgeInsets.only(bottom: bottom),
      child: SizedBox(
        height: 54,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _TabItem(
              icon: '📍',
              text: '找球场',
              active: selectedIndex == 0,
              accent: theme.accent,
              onTap: () => onTap(0),
            ),
            _TabItem(
              icon: '▣',
              text: '发现',
              active: selectedIndex == 1,
              accent: theme.accent,
              onTap: () => onTap(1),
            ),
            _ActionBall(theme: theme, onTap: onAction),
            _TabItem(
              icon: '🎾',
              text: '有场',
              active: selectedIndex == 2,
              accent: theme.accent,
              onTap: () => onTap(2),
            ),
            _TabItem(
              icon: '👤',
              text: '我的',
              active: selectedIndex == 3,
              accent: theme.accent,
              onTap: () => onTap(3),
            ),
          ],
        ),
      ),
    );
  }
}

class _TabItem extends StatelessWidget {
  const _TabItem({
    required this.icon,
    required this.text,
    required this.active,
    required this.accent,
    required this.onTap,
  });

  final String icon;
  final String text;
  final bool active;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = active ? accent : const Color(0xFFB7E8D6);
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(icon, style: TextStyle(fontSize: 20, height: 1, color: color)),
            const SizedBox(height: 3),
            Text(text, style: TextStyle(fontSize: 11, height: 1, color: color)),
          ],
        ),
      ),
    );
  }
}

/// 中间网球球（对齐 .action-ball + 两条球缝）
class _ActionBall extends StatelessWidget {
  const _ActionBall({required this.theme, required this.onTap});

  final SlamTheme theme;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Transform.translate(
      offset: const Offset(0, -14),
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 52,
          height: 52,
          decoration: BoxDecoration(
            color: theme.accent,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.22),
                blurRadius: 11,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: CustomPaint(painter: _TennisSeamPainter(theme.accentInk)),
        ),
      ),
    );
  }
}

class _TennisSeamPainter extends CustomPainter {
  _TennisSeamPainter(this.inkColor);

  final Color inkColor;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.92)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;
    // 两条弧形球缝（近似小程序的 seam-left / seam-right）
    final c = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2;
    canvas.drawArc(
      Rect.fromCircle(center: c.translate(-r * 0.9, 0), radius: r * 1.1),
      -0.9,
      1.8,
      false,
      paint,
    );
    canvas.drawArc(
      Rect.fromCircle(center: c.translate(r * 0.9, 0), radius: r * 1.1),
      3.1416 - 0.9,
      1.8,
      false,
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
