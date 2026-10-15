import 'package:flutter/material.dart';

import '../core/storage.dart';

/// 四大满贯主题（对齐 miniprogram config.js 的 SLAM_THEMES）。
///
/// WXSS 中的 CSS 变量在此一一对应：
/// --court-a / --court-b / --line / --accent / --accent-ink / --ink / --muted
class SlamTheme {
  const SlamTheme({
    required this.id,
    required this.name,
    required this.hint,
    required this.nav,
    required this.front,
    required this.accent,
    required this.accentInk,
    required this.courtA,
    required this.courtB,
    required this.line,
    required this.ink,
    required this.muted,
  });

  final String id;
  final String name;
  final String hint;

  /// 导航栏 / 顶栏底色
  final Color nav;

  /// 导航栏前景（文字/图标）
  final Color front;

  /// 强调色（按钮、选中态）
  final Color accent;

  /// 强调色上的文字色
  final Color accentInk;

  /// 页面渐变底色 A/B（球场条纹）
  final Color courtA;
  final Color courtB;

  /// 分割线 / 次要线
  final Color line;

  /// 主文字（深色底上）
  final Color ink;

  /// 次要文字
  final Color muted;

  /// 页面背景渐变（对应小程序 page-style 的球场条纹渐变）
  LinearGradient get pageGradient => LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [courtA, courtB],
      );

  /// 页面纯色底（列表页等大面积使用）
  Color get pageBg => courtA;

  static const wimbledon = SlamTheme(
    id: 'wimbledon',
    name: '温网草地',
    hint: '绿草条纹',
    nav: Color(0xFF0C3B2E),
    front: Color(0xFFFFFFFF),
    accent: Color(0xFF3DFFB0),
    accentInk: Color(0xFF042018),
    courtA: Color(0xFF0C3B2E),
    courtB: Color(0xFF145C40),
    line: Color(0xFF9DFFE0),
    ink: Color(0xFFE8FFF4),
    muted: Color(0xFF9DFFE0),
  );

  static const roland = SlamTheme(
    id: 'roland',
    name: '法网红土',
    hint: '陶土球场',
    nav: Color(0xFF7A341F),
    front: Color(0xFFFFFFFF),
    accent: Color(0xFFFFE14A),
    accentInk: Color(0xFF3A140C),
    courtA: Color(0xFF8D4030),
    courtB: Color(0xFFC4623E),
    line: Color(0xFFFFE7C2),
    ink: Color(0xFFFFF6EC),
    muted: Color(0xFFFFE7C2),
  );

  static const australian = SlamTheme(
    id: 'australian',
    name: '澳网硬地',
    hint: '蓝色硬地',
    nav: Color(0xFF0A3D86),
    front: Color(0xFFFFFFFF),
    accent: Color(0xFF7EE0FF),
    accentInk: Color(0xFF042033),
    courtA: Color(0xFF0D4EA3),
    courtB: Color(0xFF1A6FD4),
    line: Color(0xFFC9F4FF),
    ink: Color(0xFFEEF9FF),
    muted: Color(0xFFC9F4FF),
  );

  static const usopen = SlamTheme(
    id: 'usopen',
    name: '美网夜场',
    hint: '深蓝夜场',
    nav: Color(0xFF071428),
    front: Color(0xFFFFFFFF),
    accent: Color(0xFFF5C16C),
    accentInk: Color(0xFF1A1206),
    courtA: Color(0xFF071833),
    courtB: Color(0xFF12305F),
    line: Color(0xFFD7E4FF),
    ink: Color(0xFFF4F7FF),
    muted: Color(0xFFD7E4FF),
  );

  static const List<SlamTheme> all = [wimbledon, roland, australian, usopen];

  static SlamTheme byId(String? id) {
    for (final t in all) {
      if (t.id == id) return t;
    }
    return wimbledon;
  }
}

/// 主题控制器：全局持有当前主题，持久化选择（对齐 slamSetTheme）
class SlamController extends ChangeNotifier {
  SlamController(this._storage);

  static const _storageKey = 'tenclip_slam_theme';

  final Storage _storage;
  SlamTheme _theme = SlamTheme.wimbledon;

  SlamTheme get theme => _theme;

  void load() {
    _theme = SlamTheme.byId(_storage.getString(_storageKey));
  }

  void setTheme(String id) {
    final next = SlamTheme.byId(id);
    if (next.id == _theme.id) return;
    _theme = next;
    _storage.setString(_storageKey, next.id);
    notifyListeners();
  }

  /// 给 H5 链接带上当前球场风格 ?court=（对齐 slamWithCourt）
  String withCourt(String url) {
    if (url.isEmpty) return url;
    if (RegExp(r'[?&]court=').hasMatch(url)) {
      return url.replaceAllMapped(
        RegExp(r'([?&]court=)[^&]*'),
        (m) => '${m[1]}${_theme.id}',
      );
    }
    return url + (url.contains('?') ? '&' : '?') + 'court=${_theme.id}';
  }
}
