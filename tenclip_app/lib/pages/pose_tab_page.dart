import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../config.dart';
import '../theme/slam_theme.dart';
import '../widgets/common.dart';

/// 「有场」Tab：内嵌 H5 实时关键点检测（对齐 miniprogram pages/analyze
/// 跳转 pose-webview 的行为；App 内直接嵌 WebView，主题切换时带 ?court= 重载）
class PoseTabPage extends StatefulWidget {
  const PoseTabPage({super.key});

  @override
  State<PoseTabPage> createState() => _PoseTabPageState();
}

class _PoseTabPageState extends State<PoseTabPage> {
  late final WebViewController _controller;
  late String _loadedThemeId;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    final slam = context.read<SlamController>();
    _loadedThemeId = slam.theme.id;
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            if (mounted && _failed) setState(() => _failed = false);
          },
          onWebResourceError: (error) {
            if ((error.isForMainFrame ?? true) && mounted) {
              setState(() => _failed = true);
            }
          },
        ),
      )
      ..loadRequest(Uri.parse(slam.withCourt(webPoseUrl)));
  }

  void _reload(String url) {
    setState(() => _failed = false);
    _controller.loadRequest(Uri.parse(url));
  }

  @override
  Widget build(BuildContext context) {
    // 主题切换后重新带 ?court= 加载（对齐 slamWithCourt）
    final slam = context.watch<SlamController>();
    if (slam.theme.id != _loadedThemeId) {
      _loadedThemeId = slam.theme.id;
      final url = slam.withCourt(webPoseUrl);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _reload(url);
      });
    }
    return Scaffold(
      appBar: themedAppBar(context, title: '有场'),
      body: ThemedPage(
        child: _failed
            ? _PoseErrorView(onRetry: () => _reload(slam.withCourt(webPoseUrl)))
            : WebViewWidget(controller: _controller),
      ),
    );
  }
}

/// WebView 加载失败占位（主题渐变底上用主题前景色）
class _PoseErrorView extends StatelessWidget {
  const _PoseErrorView({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = slamOf(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '页面加载失败',
            style: TextStyle(color: theme.ink, fontSize: 15, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          Text('请检查网络后重试', style: TextStyle(color: theme.muted, fontSize: 12)),
          const SizedBox(height: 18),
          GestureDetector(
            onTap: onRetry,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 9),
              decoration: BoxDecoration(
                color: theme.accent,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '重试',
                style: TextStyle(color: theme.accentInk, fontSize: 13, fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
