import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:gal/gal.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:video_player/video_player.dart';

import '../api/mobile_api.dart';
import '../config.dart';
import '../core/api_client.dart';
import '../core/storage.dart';
import '../core/video_picker.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 击球剪辑（对齐 miniprogram pages/stroke-extract）
///
/// 选视频 → 压缩 → 上传 → 轮询 → 结果（预览/保存/复制/分享）。
/// detect_mode 固定 spike、vlm_filter 固定 false（小程序 WXML 已无对应 UI）。
class StrokeExtractPage extends StatefulWidget {
  const StrokeExtractPage({super.key});

  @override
  State<StrokeExtractPage> createState() => _StrokeExtractPageState();
}

class _StrokeExtractPageState extends State<StrokeExtractPage> with WidgetsBindingObserver {
  PickedVideo? _video;
  String _videoName = '';
  String _videoSizeText = '';
  String _videoDurationText = '';
  double _motionPercentile = defaultMotionPercentile;

  bool _busy = false;
  String _taskId = '';
  String _status = '';
  int _queueSize = 0;
  int _progressPercent = 0;
  String _progressText = '处理中…';
  String _progressMessage = '';
  String _errorText = '';

  String _summary = '';
  String _downloadUrl = '';
  String _previewPath = '';
  bool _saving = false;

  TaskPoller? _poller;
  int _uploadStartMs = 0;
  VideoPlayerController? _previewController;

  MobileApi get _api => context.read<MobileApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _pingHealth());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _poller?.stop();
    _previewController?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // 息屏/切后台恢复后手动补一次轮询（对齐 onShow 的 stop.resume）
    if (state == AppLifecycleState.resumed) _poller?.resume();
  }

  // ── 探活（对齐 app.js onLaunch 的 pingHealth）──

  Future<void> _pingHealth() async {
    try {
      await context.read<ApiClient>().pingHealth();
    } catch (err) {
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('无法连接后端'),
          content: Text(err.toString()),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('知道了')),
          ],
        ),
      );
    }
  }

  // ── 本地统计（对齐 addStats；目前 App 内暂无读取方，保持与小程序同 key 写入）──

  void _addStats({int clipCount = 0, int points = 0}) {
    try {
      final storage = context.read<Storage>();
      final stats = storage.getMap('tenclip_user_stats');
      stats['clipCount'] = ((stats['clipCount'] as num?)?.toInt() ?? 0) + clipCount;
      stats['analyzeCount'] = (stats['analyzeCount'] as num?)?.toInt() ?? 0;
      stats['points'] = ((stats['points'] as num?)?.toInt() ?? 0) + points;
      storage.setJson('tenclip_user_stats', stats);
    } catch (_) {}
  }

  // ── 选视频（对齐 onChooseVideo）──

  Future<void> _onChooseVideo() async {
    if (_busy) return;
    PickedVideo? video;
    try {
      video = await VideoPicker.chooseTennisVideo(context);
    } catch (err) {
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('选择视频失败'),
          content: Text(err.toString()),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('确定')),
          ],
        ),
      );
      return;
    }
    final picked = video;
    if (picked == null || !mounted) return;
    await _disposePreview();
    if (!mounted) return;
    final sizeMb = picked.size > 0 ? (picked.size / (1024 * 1024)).toStringAsFixed(1) : '';
    setState(() {
      _video = picked;
      final name = p.basename(picked.filePath);
      _videoName = name.isNotEmpty ? name : '已选视频';
      _videoSizeText = sizeMb.isNotEmpty ? '$sizeMb MB' : '';
      _videoDurationText = picked.durationSec > 0 ? formatDurationShort(picked.durationSec) : '';
      _summary = '';
      _downloadUrl = '';
      _previewPath = '';
      _errorText = '';
      _status = '';
    });
  }

  // ── 选视频说明（对齐 showChooseVideoHelp；文案按 iOS 相册读入改写，微信无对应交互）──

  void _onShowChooseHelp() {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('为什么选择后很慢？'),
        content: const Text(
          '从相册选择大视频后，App 需要读入视频文件，iCloud 上的视频还需先下载到本机，'
          '可能需要 1～3 分钟，属于正常现象，并非 App 报错。\n\n请耐心等待，不要重复点击或退出。',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('知道了')),
        ],
      ),
    );
  }

  // ── 复制网页版链接（对齐 copyStrokeLink）──

  Future<void> _onCopyWebLink() async {
    await Clipboard.setData(const ClipboardData(text: webStrokeUrl));
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('链接已复制'),
        content: const Text(
          '网页版击球剪辑地址已复制。\n\n大视频请用系统浏览器打开（iPhone 推荐 Safari / Chrome），'
          '支持分片断点续传：粘贴到浏览器地址栏打开。\n\n上传期间请勿切出浏览器。',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('知道了')),
        ],
      ),
    );
  }

  // ── 提交（对齐 onSubmit）──

  Future<void> _onSubmit() async {
    final video = _video;
    if (video == null || _busy) return;

    // 登录检查（对齐 isAuthDone 弹窗）
    if (!context.read<AppState>().isLoggedIn) {
      final go = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('请先登录'),
          content: const Text('登录后才能使用视频剪辑功能'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
            TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('去登录')),
          ],
        ),
      );
      if (go == true && mounted) {
        Navigator.pushNamed(context, '/login', arguments: {'from': 'stroke-extract'});
      }
      return;
    }

    _poller?.stop();
    _poller = null;
    await _disposePreview();
    if (!mounted) return;
    setState(() {
      _busy = true;
      _status = 'queued';
      _queueSize = 0;
      _progressPercent = 0;
      _progressText = '准备中…';
      _progressMessage = '正在处理视频，请勿离开页面';
      _errorText = '';
      _summary = '';
      _downloadUrl = '';
      _previewPath = '';
    });

    try {
      final prepared = await VideoPicker.prepareForUpload(
        video,
        onCompressProgress: (pct, msg) {
          if (!mounted) return;
          setState(() {
            _progressText = '压缩中…';
            _progressMessage = msg;
            _progressPercent = pct;
          });
        },
      );
      if (!mounted) return;
      final uploadMb = prepared.size > 0 ? (prepared.size / (1024 * 1024)).toStringAsFixed(1) : '';
      setState(() {
        _progressText = '上传中…';
        _progressMessage =
            uploadMb.isNotEmpty ? '压缩完成（约 $uploadMb MB），正在上传…' : '正在上传到服务器…';
        _progressPercent = 26;
      });
      _uploadStartMs = DateTime.now().millisecondsSinceEpoch;
      final submit = await _api.submitStrokeExtract(
        filePath: prepared.filePath,
        fileSize: prepared.size,
        durationSec: video.durationSec,
        detectMode: defaultDetectMode,
        motionPercentile: _motionPercentile,
        vlmFilter: false,
        onProgress: (ev) {
          if (!mounted) return;
          setState(() {
            _progressText = '上传中 ${ev.percent}%';
            _progressMessage =
                VideoPicker.formatUploadProgress(ev.percent, ev.sent, ev.total, _uploadStartMs);
            _progressPercent = _mapUploadProgressPercent(ev.percent);
          });
        },
        onRetry: (attempt, maxAttempts) {
          if (!mounted) return;
          _uploadStartMs = DateTime.now().millisecondsSinceEpoch;
          setState(() {
            _progressText = '重试上传…';
            _progressMessage = '网络中断，正在第 $attempt/$maxAttempts 次重试…';
          });
        },
      );
      if (!mounted) return;
      setState(() {
        _taskId = submit.taskId;
        _queueSize = submit.queueSize;
        _progressText = '分析中…';
        _progressMessage = '上传完成，正在分析（可息屏，亮屏后自动继续）';
        _progressPercent = 60;
      });
      _startPoll(submit.taskId);
    } catch (err) {
      if (!mounted) return;
      final msg = err.toString();
      final isUpload =
          RegExp(r'uploadfile|connection_reset|上传|err_connection', caseSensitive: false)
              .hasMatch(msg);
      setState(() {
        _busy = false;
        _status = 'failed';
        _progressMessage = isUpload
            ? '上传失败：请用 WiFi，长视频压缩+上传约 10～20 分钟，勿切后台'
            : '提交失败';
        _errorText = msg;
      });
    }
  }

  /// 对齐 mapUploadProgressPercent：上传进度映射到 22～58 区间
  int _mapUploadProgressPercent(int pct) =>
      math.min(58, math.max(22, 22 + (pct * 0.36).round()));

  // ── 轮询（对齐 _startPoll / _applyTask）──

  void _startPoll(String taskId) {
    _poller = TaskPoller(
      fetchTask: () => _api.getStrokeTask(taskId),
      onUpdate: _applyTask,
      onDone: (task, err) {
        _poller = null;
        if (!mounted) return;
        if (err != null) {
          setState(() {
            _busy = false;
            _status = 'failed';
            _progressMessage = '查询进度失败';
            _errorText = err.toString();
          });
          return;
        }
        setState(() {
          _busy = false;
          _progressText = '开始提取';
        });
        if (task != null && task.succeeded) {
          _addStats(clipCount: 1, points: 50);
          _loadPreview(taskId);
        }
      },
    )..start();
  }

  void _applyTask(TaskStatus task) {
    if (!mounted) return;
    if (task.pollRetry) {
      setState(() => _progressMessage = task.progressMessage);
      return;
    }
    final frac = (task.progressFrac * 100).round();
    setState(() {
      _status = task.status;
      _queueSize = task.queueSize;
      _progressPercent = math.max(
        60,
        task.status == 'running' ? 60 + (frac * 0.38).round() : frac,
      );
      _progressMessage = task.status == 'failed'
          ? (task.progressMessage.isNotEmpty ? task.progressMessage : '分析失败')
          : task.progressMessage;
      _errorText = task.status == 'failed' ? (task.error ?? '分析失败') : '';
      _summary = task.summary ?? '';
      if (task.succeeded) {
        _downloadUrl =
            (task.downloadUrl != null && task.downloadUrl!.isNotEmpty)
                ? task.downloadUrl!
                : _api.strokeDownloadUrl(task.taskId);
      }
    });
  }

  // ── 结果预览（对齐 _loadPreview：下载到临时文件后用播放器展示）──

  Future<void> _loadPreview(String taskId) async {
    setState(() => _progressMessage = '正在下载集锦预览…');
    try {
      final path = await _api.downloadStrokeResult(taskId, onProgress: (pct) {
        if (!mounted) return;
        setState(() => _progressMessage = '下载预览 $pct%');
      });
      if (!mounted) return;
      setState(() {
        _previewPath = path;
        _progressMessage = '';
      });
      await _initPreview(path);
    } catch (err) {
      if (!mounted) return;
      setState(() {
        _progressMessage = '';
        _errorText = err.toString();
      });
    }
  }

  Future<void> _initPreview(String path) async {
    await _disposePreview();
    final controller = VideoPlayerController.file(File(path));
    _previewController = controller;
    try {
      await controller.initialize();
      if (!mounted || _previewController != controller) {
        await controller.dispose();
        return;
      }
      controller.addListener(_onPreviewTick);
      setState(() {});
    } catch (_) {
      // 预览初始化失败不阻断保存/复制
    }
  }

  void _onPreviewTick() {
    if (mounted) setState(() {});
  }

  Future<void> _disposePreview() async {
    final controller = _previewController;
    _previewController = null;
    if (controller != null) {
      controller.removeListener(_onPreviewTick);
      await controller.dispose();
    }
  }

  // ── 保存 / 复制 / 分享 ──

  Future<void> _onSaveVideo() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      var path = _previewPath;
      if (path.isEmpty) {
        if (_taskId.isEmpty) return;
        path = await _api.downloadStrokeResult(_taskId);
      }
      await Gal.putVideo(path);
      if (!mounted) return;
      showToast(context, '已保存到相册');
    } catch (_) {
      if (!mounted) return;
      // 对齐小程序 saveVideoToPhotosAlbum fail：提示相册权限
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('需要相册权限'),
          content: const Text('请在设置中允许保存到相册后重试。'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('确定')),
          ],
        ),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _onCopyDownloadLink() async {
    if (_downloadUrl.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: _downloadUrl));
    if (!mounted) return;
    showToast(context, '链接已复制');
  }

  Future<void> _onShare() async {
    if (_downloadUrl.isEmpty) return;
    try {
      await Share.shareUri(Uri.parse(_downloadUrl));
    } catch (_) {}
  }

  // ── UI ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: themedAppBar(context, title: '击球剪辑'),
      body: ThemedPage(
        child: Stack(
          children: [
            ListView(
              padding: EdgeInsets.fromLTRB(12, 12, 12, 24 + MediaQuery.of(context).padding.bottom),
              children: [
                _buildHero(),
                _buildChooseCard(),
                if (_status.isNotEmpty) _buildStatusCard(),
                if (_summary.isNotEmpty) _buildResultCard(),
              ],
            ),
            if (_busy) _buildUploadOverlay(),
          ],
        ),
      ),
    );
  }

  Widget _buildHero() {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFBAF5E8), Color(0xFFD4FFF4)],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'UChance 击球剪辑',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: S.ink),
          ),
          SizedBox(height: 6),
          Text(
            '上传网球视频，自动剪掉换边与等待，保留击球/回合画面。',
            style: TextStyle(fontSize: 12, color: S.sub, height: 1.55),
          ),
        ],
      ),
    );
  }

  Widget _buildChooseCard() {
    return SlamCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('选择视频', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: S.ink)),
          const SizedBox(height: 4),
          const Text(
            '支持相册或拍摄；超过 10 分钟将自动强压缩并分片上传，请用 WiFi 并保持在本页。',
            style: TextStyle(fontSize: 12, color: S.muted),
          ),
          const SizedBox(height: 10),
          GestureDetector(
            onTap: _onChooseVideo,
            child: CustomPaint(
              foregroundPainter: _DashedBorderPainter(color: const Color(0xFFD8DEE8), radius: 10),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 18),
                decoration: BoxDecoration(
                  color: S.fieldBg,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: _videoName.isEmpty
                    ? const Column(
                        children: [
                          Text('＋', style: TextStyle(fontSize: 24, color: S.green, height: 1)),
                          SizedBox(height: 4),
                          Text('点击选择视频', style: TextStyle(fontSize: 13, color: S.muted)),
                        ],
                      )
                    : Column(
                        children: [
                          Text(
                            _videoName,
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink),
                          ),
                          if (_videoDurationText.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text('时长 $_videoDurationText',
                                style: const TextStyle(fontSize: 12, color: S.muted)),
                          ],
                          if (_videoSizeText.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(_videoSizeText, style: const TextStyle(fontSize: 12, color: S.muted)),
                          ],
                          const SizedBox(height: 4),
                          const Text('重新选择', style: TextStyle(fontSize: 12, color: S.muted)),
                        ],
                      ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFF4F8FB),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFE3EAF2), width: 0.5),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '从相册选择大视频后，读入文件可能需要 1～3 分钟（iCloud 视频需先下载），请耐心等待，并非程序出错。',
                  style: TextStyle(fontSize: 11, color: Color(0xFF5C6773), height: 1.55),
                ),
                const SizedBox(height: 5),
                GestureDetector(
                  onTap: _onShowChooseHelp,
                  child: const Text(
                    '查看说明',
                    style: TextStyle(
                      fontSize: 11,
                      color: Color(0xFF0D7A62),
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            height: 42,
            child: OutlinedButton(
              onPressed: _onCopyWebLink,
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: S.green),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                backgroundColor: Colors.white,
                foregroundColor: const Color(0xFF0D3D32),
                textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
              ),
              child: const Text('视频超 10 分钟？复制链接到 Chrome / Safari 上传'),
            ),
          ),
          const SizedBox(height: 5),
          const Center(
            child: Text('浏览器上传支持分片断点续传，大文件更稳',
                style: TextStyle(fontSize: 12, color: S.faint)),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 12, bottom: 6),
            child: Text(
              '尖峰灵敏度 ${_motionPercentile.round()}（越低检出越多击球，每段约 2～4 秒）',
              style: const TextStyle(fontSize: 12, color: S.muted),
            ),
          ),
          Slider(
            min: 60,
            max: 92,
            divisions: 32,
            value: _motionPercentile,
            activeColor: S.green,
            inactiveColor: const Color(0xFFE5E9F0),
            onChanged: _busy ? null : (v) => setState(() => _motionPercentile = v),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: AccentButton(
              label: _busy ? _progressText : '开始提取',
              onPressed: (_busy || _video == null) ? null : _onSubmit,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusCard() {
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: SlamCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('处理状态',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: S.ink)),
            const SizedBox(height: 6),
            Row(
              children: [
                _statusBadge(_status),
                if (_queueSize > 0) ...[
                  const SizedBox(width: 8),
                  Text('排队 $_queueSize', style: const TextStyle(fontSize: 12, color: S.muted)),
                ],
              ],
            ),
            if (_busy) ...[
              const SizedBox(height: 6),
              ClipRRect(
                borderRadius: BorderRadius.circular(3),
                child: LinearProgressIndicator(
                  value: _progressPercent / 100,
                  minHeight: 6,
                  color: S.green,
                  backgroundColor: const Color(0xFFE5E9F0),
                ),
              ),
            ],
            if (_progressMessage.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(_progressMessage, style: const TextStyle(fontSize: 12, color: S.sub)),
            ],
            if (_errorText.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(_errorText, style: const TextStyle(fontSize: 13, color: S.danger)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _statusBadge(String status) {
    Color bg;
    Color fg;
    switch (status) {
      case 'queued':
      case 'running':
        bg = const Color(0xFFE8FAF4);
        fg = const Color(0xFF0D6B52);
      case 'succeeded':
        bg = const Color(0xFFE8FAF4);
        fg = const Color(0xFF0D3D32);
      case 'failed':
        bg = const Color(0xFFFDECEC);
        fg = S.danger;
      default:
        bg = const Color(0xFFEEF2F6);
        fg = S.sub;
    }
    final label = switch (status) {
      'queued' => '排队中',
      'running' => '分析中',
      'succeeded' => '完成',
      'failed' => '失败',
      _ => status,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text(label, style: TextStyle(fontSize: 12, color: fg)),
    );
  }

  Widget _buildResultCard() {
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: SlamCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('提取结果',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: S.ink)),
            const SizedBox(height: 6),
            Text(_summary, style: const TextStyle(fontSize: 13, color: Color(0xFF1A1F26), height: 1.55)),
            if (_downloadUrl.isNotEmpty) ...[
              const SizedBox(height: 6),
              SelectableText(_downloadUrl, style: const TextStyle(fontSize: 11, color: S.faint)),
            ],
            if (_previewPath.isNotEmpty) _buildPreviewVideo(),
            if (_downloadUrl.isNotEmpty || _previewPath.isNotEmpty) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  _secondaryButton(
                    _saving ? '保存中…' : '保存到相册',
                    _saving ? null : _onSaveVideo,
                  ),
                  const SizedBox(width: 8),
                  _secondaryButton('复制链接', _onCopyDownloadLink),
                  const SizedBox(width: 8),
                  _secondaryButton('分享', _onShare),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _secondaryButton(String label, VoidCallback? onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 38,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: S.green),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text(label, style: const TextStyle(fontSize: 14, color: Color(0xFF0D3D32))),
        ),
      ),
    );
  }

  Widget _buildPreviewVideo() {
    final controller = _previewController;
    if (controller == null || !controller.value.isInitialized) {
      return Container(
        margin: const EdgeInsets.only(top: 10),
        height: 180,
        decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(8)),
        alignment: Alignment.center,
        child: const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Container(
          color: Colors.black,
          child: AspectRatio(
            aspectRatio: controller.value.aspectRatio > 0 ? controller.value.aspectRatio : 16 / 9,
            child: GestureDetector(
              onTap: () {
                setState(() {
                  controller.value.isPlaying ? controller.pause() : controller.play();
                });
              },
              child: Stack(
                alignment: Alignment.center,
                children: [
                  VideoPlayer(controller),
                  if (!controller.value.isPlaying)
                    const Icon(Icons.play_circle_fill, color: Colors.white70, size: 44),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// 长任务遮罩（对齐 .upload-overlay）
  Widget _buildUploadOverlay() {
    return Positioned.fill(
      child: Container(
        color: const Color(0x8C0F1820),
        alignment: Alignment.center,
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 310),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(18, 20, 18, 16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              boxShadow: const [
                BoxShadow(color: Color(0x2E000000), blurRadius: 24, offset: Offset(0, 8)),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _progressText.isNotEmpty ? _progressText : '处理中…',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      fontSize: 17, fontWeight: FontWeight.w600, color: Color(0xFF0D3D32)),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: _progressPercent / 100,
                          minHeight: 8,
                          color: S.green,
                          backgroundColor: const Color(0xFFE5E9F0),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '$_progressPercent%',
                      style: const TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w600, color: S.green),
                    ),
                  ],
                ),
                if (_progressMessage.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(
                    _progressMessage,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 13, color: S.sub, height: 1.55),
                  ),
                ],
                Container(
                  margin: const EdgeInsets.only(top: 12),
                  padding: const EdgeInsets.only(top: 10),
                  decoration: const BoxDecoration(
                    border: Border(top: BorderSide(color: Color(0xFFEEF2F5))),
                  ),
                  child: const Text(
                    '超过 10 分钟：压缩约 3～8 分钟 + 分片上传约 5～15 分钟，请保持 WiFi 与本页',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 11, color: Color(0xFF8A939F), height: 1.5),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 虚线圆角边框（对齐 .video-pick 的 dashed border；Flutter 无内置虚线）
class _DashedBorderPainter extends CustomPainter {
  _DashedBorderPainter({required this.color, this.radius = 10});

  final Color color;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    final path = Path()
      ..addRRect(RRect.fromRectAndRadius(Offset.zero & size, Radius.circular(radius)));
    const dash = 6.0;
    const gap = 4.0;
    for (final metric in path.computeMetrics()) {
      var dist = 0.0;
      while (dist < metric.length) {
        final end = math.min(dist + dash, metric.length);
        canvas.drawPath(metric.extractPath(dist, end), paint);
        dist = end + gap;
      }
    }
  }

  @override
  bool shouldRepaint(_DashedBorderPainter oldDelegate) =>
      oldDelegate.color != color || oldDelegate.radius != radius;
}
