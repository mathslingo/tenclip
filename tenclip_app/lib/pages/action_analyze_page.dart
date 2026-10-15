import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';

import '../api/mobile_api.dart';
import '../core/api_client.dart';
import '../core/storage.dart';
import '../core/video_picker.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 动作分析（对齐 miniprogram pages/action-analyze）
///
/// 选视频 → 压缩 → 上传 → 轮询 → 展示 AI 指导意见。
class ActionAnalyzePage extends StatefulWidget {
  const ActionAnalyzePage({super.key});

  @override
  State<ActionAnalyzePage> createState() => _ActionAnalyzePageState();
}

class _ActionAnalyzePageState extends State<ActionAnalyzePage> with WidgetsBindingObserver {
  static const _perfOptions = <(String, String)>[
    ('eco', '省显存'),
    ('balanced', '平衡'),
    ('quality', '质量优先'),
  ];
  static const _promptOptions = <(String, String)>[
    ('default', '标准'),
    ('compact', '精简'),
    ('step_by_step', '分步'),
    ('step_by_step_v2', '分步v2'),
    ('motion_deep', '深度'),
  ];

  PickedVideo? _video;
  String _videoName = '';
  String _videoSizeText = '';
  String _perfMode = 'eco';
  String _promptProfile = 'default';

  bool _busy = false;
  String _taskId = '';
  String _status = '';
  int _queueSize = 0;
  int _progressPercent = 0;
  String _progressText = '分析中…';
  String _progressMessage = '';
  String _errorText = '';

  String _guidanceBody = '';
  String _guidanceMeta = '';
  bool _showMeta = false;

  TaskPoller? _poller;
  int _uploadStartMs = 0;

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

  void _addStats({int analyzeCount = 0, int points = 0}) {
    try {
      final storage = context.read<Storage>();
      final stats = storage.getMap('tenclip_user_stats');
      stats['clipCount'] = (stats['clipCount'] as num?)?.toInt() ?? 0;
      stats['analyzeCount'] = ((stats['analyzeCount'] as num?)?.toInt() ?? 0) + analyzeCount;
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
    final sizeMb = picked.size > 0 ? (picked.size / (1024 * 1024)).toStringAsFixed(1) : '';
    setState(() {
      _video = picked;
      final name = p.basename(picked.filePath);
      _videoName = name.isNotEmpty ? name : '已选视频';
      _videoSizeText = sizeMb.isNotEmpty ? '$sizeMb MB' : '';
      _guidanceBody = '';
      _guidanceMeta = '';
      _showMeta = false;
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

  // ── 复制指导意见（对齐 onCopyGuidance）──

  Future<void> _onCopyGuidance() async {
    final parts = <String>[_guidanceBody];
    if (_guidanceMeta.isNotEmpty) {
      parts.add('\n\n---\n\n$_guidanceMeta');
    }
    final text = parts.join().trim();
    if (text.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    showToast(context, '已复制');
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
          content: const Text('登录后才能使用 AI 教练功能'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
            TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('去登录')),
          ],
        ),
      );
      if (go == true && mounted) {
        Navigator.pushNamed(context, '/login', arguments: {'from': 'action-analyze'});
      }
      return;
    }

    _poller?.stop();
    _poller = null;
    setState(() {
      _busy = true;
      _status = 'queued';
      _queueSize = 0;
      _progressPercent = 0;
      _progressText = '准备中…';
      _progressMessage = '正在处理视频，请勿离开页面';
      _errorText = '';
      _guidanceBody = '';
      _guidanceMeta = '';
      _showMeta = false;
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
        _progressMessage = uploadMb.isNotEmpty ? '压缩完成（约 $uploadMb MB），正在上传…' : '正在上传…';
        _progressPercent = 26;
      });
      _uploadStartMs = DateTime.now().millisecondsSinceEpoch;
      final submit = await _api.submitAnalyze(
        filePath: prepared.filePath,
        fileSize: prepared.size,
        durationSec: video.durationSec,
        perfMode: _perfMode,
        promptProfile: _promptProfile,
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
        _progressMessage = '上传完成，排队等待分析（可息屏）';
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
        _progressMessage = isUpload ? '上传失败，请换 WiFi 或选较短视频' : '提交失败';
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
      fetchTask: () => _api.getAnalyzeTask(taskId),
      onUpdate: _applyTask,
      onDone: (task, err) {
        _poller = null;
        if (!mounted) return;
        if (err != null) {
          setState(() {
            _busy = false;
            _status = 'failed';
            _errorText = err.toString();
          });
          return;
        }
        setState(() {
          _busy = false;
          _progressText = '开始分析';
        });
        if (task != null && task.succeeded) {
          _addStats(analyzeCount: 1, points: 80);
          _applyTask(task);
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
    var guidanceBody = _guidanceBody;
    var guidanceMeta = _guidanceMeta;
    if (task.status == 'succeeded' && (task.guidance ?? '').isNotEmpty) {
      final formatted = _formatGuidance(task.guidance!);
      guidanceBody = formatted.body;
      guidanceMeta = formatted.meta;
    }
    final pollPct = switch (task.status) {
      'queued' => 62,
      'running' => math.max(65, math.min(98, 60 + (frac * 0.38).round())),
      'succeeded' => 100,
      _ => frac,
    };
    setState(() {
      _status = task.status;
      _queueSize = task.queueSize;
      _progressPercent = pollPct;
      _progressMessage = task.status == 'failed'
          ? (task.progressMessage.isNotEmpty ? task.progressMessage : '分析失败')
          : (task.progressMessage.isNotEmpty
              ? task.progressMessage
              : switch (task.status) {
                  'queued' => '排队等待中…',
                  'running' => '正在分析…',
                  _ => '',
                });
      _errorText = task.status == 'failed' ? (task.error ?? '分析失败') : '';
      _guidanceBody = guidanceBody;
      _guidanceMeta = guidanceMeta;
    });
  }

  // ── UI ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: themedAppBar(context, title: '动作分析'),
      body: ThemedPage(
        child: Stack(
          children: [
            ListView(
              padding: EdgeInsets.fromLTRB(12, 12, 12, 24 + MediaQuery.of(context).padding.bottom),
              children: [
                _buildHero(),
                _buildChooseCard(),
                if (_status.isNotEmpty) _buildStatusCard(),
                if (_guidanceBody.isNotEmpty) _buildGuidanceCard(),
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
      child: const Align(
        alignment: Alignment.centerLeft,
        child: Text(
          'UChance 动作分析',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: S.ink),
        ),
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
            '支持相册或拍摄；较长视频将自动压缩后上传，请保持 WiFi。',
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
          const Padding(
            padding: EdgeInsets.only(top: 12, bottom: 6),
            child: Text('性能模式', style: TextStyle(fontSize: 12, color: S.muted)),
          ),
          _chipRow(_perfOptions, _perfMode, (v) => setState(() => _perfMode = v)),
          const Padding(
            padding: EdgeInsets.only(top: 12, bottom: 6),
            child: Text('分析提示词', style: TextStyle(fontSize: 12, color: S.muted)),
          ),
          _chipRow(_promptOptions, _promptProfile, (v) => setState(() => _promptProfile = v)),
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: AccentButton(
              label: _busy ? _progressText : '开始分析',
              onPressed: (_busy || _video == null) ? null : _onSubmit,
            ),
          ),
        ],
      ),
    );
  }

  /// 选项 chip（对齐 .chip / .chip.active）
  Widget _chipRow(List<(String, String)> options, String current, ValueChanged<String> onTap) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final o in options)
          GestureDetector(
            onTap: _busy ? null : () => onTap(o.$1),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: current == o.$1 ? const Color(0xFF121722) : Colors.white,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(
                  color: current == o.$1 ? const Color(0xFF121722) : const Color(0xFFE5E9F0),
                ),
              ),
              child: Text(
                o.$2,
                style: TextStyle(
                  fontSize: 13,
                  color: current == o.$1 ? Colors.white : const Color(0xFF374152),
                ),
              ),
            ),
          ),
      ],
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

  Widget _buildGuidanceCard() {
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: SlamCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('指导意见',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: S.ink)),
                GestureDetector(
                  onTap: _onCopyGuidance,
                  child: const Text(
                    '复制全文',
                    style: TextStyle(
                      fontSize: 12,
                      color: Color(0xFF0D6B52),
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ],
            ),
            Container(
              margin: const EdgeInsets.only(top: 8),
              constraints: BoxConstraints(
                maxHeight: MediaQuery.of(context).size.height * 0.55,
              ),
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: S.fieldBg,
                border: Border.all(color: const Color(0xFFE5E9F0)),
                borderRadius: BorderRadius.circular(12),
              ),
              child: SingleChildScrollView(
                child: SelectableText(
                  _guidanceBody,
                  style: const TextStyle(fontSize: 13, color: Color(0xFF1A1F26), height: 1.55),
                ),
              ),
            ),
            if (_guidanceMeta.isNotEmpty) ...[
              const SizedBox(height: 8),
              GestureDetector(
                onTap: () => setState(() => _showMeta = !_showMeta),
                child: Text(
                  '${_showMeta ? '收起' : '查看'}运行环境与参数',
                  style: const TextStyle(fontSize: 12, color: S.sub),
                ),
              ),
            ],
            if (_showMeta && _guidanceMeta.isNotEmpty)
              Container(
                margin: const EdgeInsets.only(top: 6),
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF4F6F9),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: SelectableText(
                  _guidanceMeta,
                  style: const TextStyle(fontSize: 11, color: S.sub, height: 1.5),
                ),
              ),
          ],
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
                    '视频较大时压缩与上传各需数分钟，请保持在本页等待',
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

/// 指导意见格式化（对齐 utils/guidance.js 的 formatGuidance）
({String body, String meta}) _formatGuidance(String raw) {
  final text = raw.trim();
  const sep = '\n\n---\n\n';
  final idx = text.indexOf(sep);
  var meta = '';
  var body = text;
  if (idx != -1) {
    meta = text.substring(0, idx).trim();
    body = text.substring(idx + sep.length).trim();
  }
  // plainBody：去掉常见 Markdown 符号
  var display = body.isEmpty ? text : body;
  display = display
      .replaceAll(RegExp(r'^#{1,6}\s+', multiLine: true), '')
      .replaceAllMapped(RegExp(r'\*\*(.+?)\*\*'), (m) => '${m[1]}')
      .replaceAllMapped(RegExp(r'\*(.+?)\*'), (m) => '${m[1]}')
      .replaceAllMapped(RegExp(r'`([^`]+)`'), (m) => '${m[1]}')
      .replaceAll(RegExp(r'^[-*]\s+', multiLine: true), '• ')
      .trim();
  if (display.isEmpty) display = '（模型未返回正文）';
  return (body: display, meta: meta);
}

/// 虚线圆角边框（对齐 .video-pick 的 dashed border；Flutter 无内置虚线）
class _DashedBorderPainter extends CustomPainter {
  _DashedBorderPainter({required this.color, this.radius = 10, this.strokeWidth = 1});

  final Color color;
  final double radius;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
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
      oldDelegate.color != color ||
      oldDelegate.radius != radius ||
      oldDelegate.strokeWidth != strokeWidth;
}
