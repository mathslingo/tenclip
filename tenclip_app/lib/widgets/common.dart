import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../theme/slam_theme.dart';

/// 读取当前主题（Provider）
SlamTheme slamOf(BuildContext context) => context.read<SlamController>().theme;

/// 设计系统常量（对齐 styles/common.wxss；750rpx≈375pt，rpx/2≈逻辑像素）
class S {
  S._();

  static const ink = Color(0xFF151821); // 主文字
  static const sub = Color(0xFF415360); // 次文字
  static const muted = Color(0xFF6E7582); // 弱文字
  static const faint = Color(0xFF9AA3AF); // 提示文字
  static const line = Color(0xFFEEF1F4); // 卡片内分割线
  static const border = Color(0xFFE5E7EB); // 输入框边
  static const cardBg = Colors.white;
  static const fieldBg = Color(0xFFFBFCFE);
  static const green = Color(0xFF13D8A8);
  static const danger = Color(0xFFB42318);

  static BoxDecoration card({double radius = 12}) => BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(radius),
        boxShadow: const [
          BoxShadow(color: Color(0x0F000000), blurRadius: 6, offset: Offset(0, 1)),
        ],
      );
}

/// 页面容器：主题渐变底（对齐 page-meta page-style 的球场条纹）
class ThemedPage extends StatelessWidget {
  const ThemedPage({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = context.watch<SlamController>().theme;
    return Container(
      decoration: BoxDecoration(gradient: theme.pageGradient),
      child: child,
    );
  }
}

/// 主题 AppBar（对齐 navigationBarBackgroundColor / textStyle:white）
PreferredSizeWidget themedAppBar(
  BuildContext context, {
  String title = '',
  List<Widget>? actions,
  bool centerTitle = true,
  Widget? leading,
}) {
  final theme = context.watch<SlamController>().theme;
  return AppBar(
    backgroundColor: theme.nav,
    foregroundColor: theme.front,
    elevation: 0,
    centerTitle: centerTitle,
    leading: leading,
    title: title.isEmpty
        ? null
        : Text(
            title,
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: theme.front),
          ),
    actions: actions,
  );
}

/// 头像：有图显示图，否则首字母（渐变底，对齐 .avatar）
class Avatar extends StatelessWidget {
  const Avatar({super.key, this.url = '', this.initial = '球', this.size = 36, this.onTap});

  final String url;
  final String initial;
  final double size;
  final VoidCallback? onTap;

  static const _gradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFBAF5E8), S.green],
  );

  @override
  Widget build(BuildContext context) {
    final letter = initial.isNotEmpty ? initial[0] : '球';
    final child = url.isNotEmpty
        ? CachedNetworkImage(
            imageUrl: url,
            width: size,
            height: size,
            fit: BoxFit.cover,
            placeholder: (_, __) => _letter(letter),
            errorWidget: (_, __, ___) => _letter(letter),
          )
        : _letter(letter);
    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(size / 2),
        child: SizedBox(width: size, height: size, child: child),
      ),
    );
  }

  Widget _letter(String letter) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(gradient: _gradient),
      alignment: Alignment.center,
      child: Text(
        letter,
        style: TextStyle(
          color: const Color(0xFF0D3D32),
          fontSize: size * 0.4,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

/// 网络封面图（固定宽高比，失败回退字母块，对齐 .cover-wrap padding-bottom 技巧）
class CoverImage extends StatelessWidget {
  const CoverImage({
    super.key,
    required this.url,
    required this.ratio,
    this.fallbackLetter = 'U',
    this.onError,
  });

  final String url;

  /// 高/宽（cover_ratio）
  final double ratio;
  final String fallbackLetter;
  final VoidCallback? onError;

  @override
  Widget build(BuildContext context) {
    final fallback = Container(
      color: const Color(0xFFE8FAF4),
      alignment: Alignment.center,
      child: Text(
        fallbackLetter.isNotEmpty ? fallbackLetter[0] : 'U',
        style: const TextStyle(color: S.green, fontSize: 30, fontWeight: FontWeight.w700),
      ),
    );
    final img = url.isEmpty
        ? fallback
        : CachedNetworkImage(
            imageUrl: url,
            fit: BoxFit.cover,
            placeholder: (_, __) => fallback,
            errorWidget: (_, __, ___) {
              onError?.call();
              return fallback;
            },
          );
    return AspectRatio(aspectRatio: 1 / ratio.clamp(0.3, 3.0), child: img);
  }
}

/// 空态
class EmptyHint extends StatelessWidget {
  const EmptyHint(this.text, {super.key, this.sub = '', this.cta = '', this.onCta});

  final String text;
  final String sub;
  final String cta;
  final VoidCallback? onCta;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 56, horizontal: 24),
      child: Column(
        children: [
          Text(text, style: const TextStyle(color: S.sub, fontSize: 15, fontWeight: FontWeight.w600)),
          if (sub.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(sub, style: const TextStyle(color: S.faint, fontSize: 12), textAlign: TextAlign.center),
          ],
          if (cta.isNotEmpty) ...[
            const SizedBox(height: 18),
            GestureDetector(
              onTap: onCta,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 9),
                decoration: BoxDecoration(
                  color: slamOf(context).accent,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  cta,
                  style: TextStyle(color: slamOf(context).accentInk, fontSize: 13, fontWeight: FontWeight.w600),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// 列表底部状态（对齐 .feed-footer）
class ListFooter extends StatelessWidget {
  const ListFooter({super.key, this.loading = false, this.reachedEnd = false, this.hint = ''});

  final bool loading;
  final bool reachedEnd;
  final String hint;

  @override
  Widget build(BuildContext context) {
    String text;
    if (loading) {
      text = '加载中…';
    } else if (hint.isNotEmpty) {
      text = hint;
    } else if (reachedEnd) {
      text = '已经到底了';
    } else {
      text = '';
    }
    if (text.isEmpty) return const SizedBox(height: 24);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 18),
      child: Center(child: Text(text, style: const TextStyle(color: S.faint, fontSize: 12))),
    );
  }
}

/// 主题色主按钮（圆角胶囊，对齐 .action-btn.primary 风格）
class AccentButton extends StatelessWidget {
  const AccentButton({super.key, required this.label, this.onPressed, this.loading = false, this.icon});

  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final theme = slamOf(context);
    return SizedBox(
      width: double.infinity,
      height: 46,
      child: FilledButton(
        onPressed: loading ? null : onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: theme.accent,
          foregroundColor: theme.accentInk,
          disabledBackgroundColor: theme.accent.withValues(alpha: 0.5),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(23)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
        child: loading
            ? SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: theme.accentInk))
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (icon != null) ...[Icon(icon, size: 18), const SizedBox(width: 6)],
                  Text(label),
                ],
              ),
      ),
    );
  }
}

/// 浅色输入框（白底卡片体系）
class SlamTextField extends StatelessWidget {
  const SlamTextField({
    super.key,
    this.controller,
    this.hint = '',
    this.maxLines = 1,
    this.maxLength,
    this.obscure = false,
    this.keyboardType,
    this.onChanged,
    this.autofocus = false,
  });

  final TextEditingController? controller;
  final String hint;
  final int maxLines;
  final int? maxLength;
  final bool obscure;
  final TextInputType? keyboardType;
  final ValueChanged<String>? onChanged;
  final bool autofocus;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      maxLines: maxLines,
      maxLength: maxLength,
      obscureText: obscure,
      keyboardType: keyboardType,
      onChanged: onChanged,
      autofocus: autofocus,
      style: const TextStyle(color: S.ink, fontSize: 15),
      cursorColor: S.green,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: S.faint, fontSize: 14),
        counterStyle: const TextStyle(color: S.faint, fontSize: 11),
        filled: true,
        fillColor: S.fieldBg,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: S.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: S.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: S.green, width: 1.2),
        ),
      ),
    );
  }
}

/// 白色卡片
class SlamCard extends StatelessWidget {
  const SlamCard({super.key, required this.child, this.padding = const EdgeInsets.all(14), this.onTap});

  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: padding,
        decoration: S.card(),
        child: child,
      ),
    );
  }
}

/// Toast 轻提示（对齐 wx.showToast icon:none）
void showToast(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(message, textAlign: TextAlign.center),
        behavior: SnackBarBehavior.floating,
        backgroundColor: Colors.black.withValues(alpha: 0.82),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.symmetric(horizontal: 60, vertical: 20),
        duration: const Duration(seconds: 2),
      ),
    );
}

/// 确认弹窗（对齐 wx.showModal）
Future<bool> showConfirm(
  BuildContext context, {
  required String title,
  String content = '',
  String confirmText = '确定',
  String cancelText = '取消',
  bool danger = false,
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: content.isEmpty ? null : Text(content),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(cancelText)),
        TextButton(
          onPressed: () => Navigator.pop(ctx, true),
          child: Text(confirmText, style: const TextStyle(color: S.danger)),
        ),
      ],
    ),
  );
  return result ?? false;
}

/// 时间格式化（对齐 note-detail formatCommentTime 类逻辑）
String formatFeedTime(int createdAtSec) {
  if (createdAtSec <= 0) return '';
  final dt = DateTime.fromMillisecondsSinceEpoch(
    createdAtSec > 9999999999 ? createdAtSec : createdAtSec * 1000,
  );
  final now = DateTime.now();
  final diff = now.difference(dt);
  if (diff.inMinutes < 1) return '刚刚';
  if (diff.inHours < 1) return '${diff.inMinutes} 分钟前';
  if (diff.inDays < 1) return '${diff.inHours} 小时前';
  if (diff.inDays < 7) return '${diff.inDays} 天前';
  return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
}

/// FeedItem 跳转详情（对齐 feed/index.js onOpenDetail）
void openFeedItem(BuildContext context, FeedItem item) {
  final id = item.id;
  if (id.isEmpty) return;
  if (item.isNote) {
    Navigator.pushNamed(context, '/note-detail', arguments: {'id': id});
  } else {
    Navigator.pushNamed(context, '/feed-detail', arguments: {'id': id});
  }
}

/// 瀑布流分两列（对齐 splitWaterfall：按 cover_ratio 累高分配到矮列）
({List<FeedItem> left, List<FeedItem> right}) splitWaterfall(List<FeedItem> items) {
  final left = <FeedItem>[];
  final right = <FeedItem>[];
  var leftH = 0.0;
  var rightH = 0.0;
  for (final it in items) {
    final h = it.coverRatio;
    if (leftH <= rightH) {
      left.add(it);
      leftH += h;
    } else {
      right.add(it);
      rightH += h;
    }
  }
  return (left: left, right: right);
}

/// 交替落列（对齐 feed 页：按推荐序 1→2→3… 左右交替）
void appendAlternating(List<FeedItem> left, List<FeedItem> right, List<FeedItem> items) {
  final base = left.length + right.length;
  for (var i = 0; i < items.length; i++) {
    if ((base + i) % 2 == 0) {
      left.add(items[i]);
    } else {
      right.add(items[i]);
    }
  }
}

/// 瀑布流卡片（对齐 .note-card；feed/profile/user 共用）
class NoteCard extends StatelessWidget {
  const NoteCard({super.key, required this.item, this.showAuthor = true, this.onTap});

  final FeedItem item;
  final bool showAuthor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap ?? () => openFeedItem(context, item),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        decoration: S.card(radius: 10),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                CoverImage(
                  url: item.cover,
                  ratio: item.coverRatio,
                  fallbackLetter: item.authorInitial,
                ),
                if (item.mediaType == 'video')
                  const Positioned(
                    right: 6,
                    top: 6,
                    child: CircleAvatar(
                      radius: 10,
                      backgroundColor: Colors.black54,
                      child: Text('▶', style: TextStyle(color: Colors.white, fontSize: 9)),
                    ),
                  ),
                if (item.tourBadge.isNotEmpty)
                  Positioned(
                    left: 6,
                    top: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.black54,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(item.tourBadge, style: const TextStyle(color: Colors.white, fontSize: 9)),
                    ),
                  ),
                if (item.distanceBadge.isNotEmpty)
                  Positioned(
                    left: 6,
                    bottom: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.black54,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(item.distanceBadge, style: const TextStyle(color: Colors.white, fontSize: 9)),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title.isNotEmpty ? item.title : item.summary,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: S.ink, height: 1.3),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      if (showAuthor) ...[
                        Avatar(url: item.authorAvatar, initial: item.authorInitial, size: 16),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            item.authorName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 11, color: S.faint),
                          ),
                        ),
                      ] else
                        const Spacer(),
                      Text('♡ ${item.likeCount}', style: const TextStyle(fontSize: 11, color: S.faint)),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 双列瀑布流
class Waterfall extends StatelessWidget {
  const Waterfall({super.key, required this.left, required this.right, this.showAuthor = true});

  final List<FeedItem> left;
  final List<FeedItem> right;
  final bool showAuthor;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Column(children: [for (final it in left) NoteCard(item: it, showAuthor: showAuthor)])),
        const SizedBox(width: 10),
        Expanded(child: Column(children: [for (final it in right) NoteCard(item: it, showAuthor: showAuthor)])),
      ],
    );
  }
}
