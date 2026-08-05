import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api/tenclip_api.dart';
import '../widgets/upload_card.dart';

class AnalyzePage extends StatefulWidget {
  const AnalyzePage({super.key});

  @override
  State<AnalyzePage> createState() => _AnalyzePageState();
}

class _AnalyzePageState extends State<AnalyzePage> {
  final _api = TenclipApi();
  final _picker = ImagePicker();

  File? _video;
  String? _videoLabel;
  String _perfMode = 'eco';
  bool _busy = false;
  double _progress = 0;
  String _phase = '';
  String _message = '';
  String? _error;
  String? _guidance;
  Timer? _poll;

  static const _perfOptions = [
    ('eco', '省显存'),
    ('balanced', '平衡'),
    ('quality', '高质量'),
  ];

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _pick() async {
    final x = await _picker.pickVideo(source: ImageSource.gallery);
    if (x == null) return;
    final f = File(x.path);
    final mb = await f.length() / (1024 * 1024);
    setState(() {
      _video = f;
      _videoLabel = '${x.name} · ${mb.toStringAsFixed(1)} MB';
      _error = null;
      _guidance = null;
    });
  }

  Future<void> _submit() async {
    final video = _video;
    if (video == null || _busy) return;
    setState(() {
      _busy = true;
      _progress = 0.05;
      _phase = '上传中…';
      _message = '正在上传到服务器';
      _error = null;
      _guidance = null;
    });
    try {
      final submit = await _api.submitAnalyze(
        video: video,
        perfMode: _perfMode,
        onSendProgress: (sent, total) {
          if (total <= 0) return;
          setState(() {
            _progress = 0.05 + 0.45 * (sent / total);
            _phase = '上传中 ${(100 * sent / total).round()}%';
            _message =
                '${(sent / (1024 * 1024)).toStringAsFixed(1)} / ${(total / (1024 * 1024)).toStringAsFixed(1)} MB';
          });
        },
      );
      setState(() {
        _phase = '分析中…';
        _message = '上传完成，模型分析中（可能需数分钟）';
        _progress = 0.55;
      });
      _startPoll(submit.taskId);
    } catch (e) {
      setState(() {
        _busy = false;
        _error = e.toString();
        _phase = '失败';
      });
    }
  }

  void _startPoll(String taskId) {
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(seconds: 2), (_) async {
      try {
        final task = await _api.getAnalyzeTask(taskId);
        if (!mounted) return;
        setState(() {
          _progress = 0.55 + 0.45 * task.progressFrac.clamp(0, 1);
          _phase = _statusLabel(task.status);
          _message = task.progressMessage;
        });
        if (task.status == 'succeeded') {
          _poll?.cancel();
          setState(() {
            _busy = false;
            _progress = 1;
            _guidance = _extractGuidance(task);
          });
        } else if (task.status == 'failed') {
          _poll?.cancel();
          setState(() {
            _busy = false;
            _error = task.error ?? '任务失败';
          });
        }
      } catch (_) {}
    });
  }

  String _extractGuidance(TaskStatus task) {
    final raw = task.guidance ?? task.summary ?? '';
    if (raw.isEmpty) return '（无指导正文，请稍后在网页版核对任务结果）';
    const sep = '\n\n---\n\n';
    final i = raw.indexOf(sep);
    if (i == -1) return raw.trim();
    return raw.substring(i + sep.length).trim();
  }

  String _statusLabel(String s) {
    switch (s) {
      case 'queued':
        return '排队中';
      case 'running':
        return '分析中…';
      case 'succeeded':
        return '完成';
      case 'failed':
        return '失败';
      default:
        return s;
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        children: [
          const Text('动作分析'),
          const SizedBox(height: 8),
          Text(
            '上传网球视频，由 AI 生成中文动作指导。',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: const Color(0xFF415360),
                ),
          ),
          const SizedBox(height: 20),
          UploadCard(
            label: _videoLabel ?? '点击选择视频',
            onTap: _busy ? null : _pick,
          ),
          const SizedBox(height: 16),
          Text('性能模式', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              for (final o in _perfOptions)
                ChoiceChip(
                  label: Text(o.$2),
                  selected: _perfMode == o.$1,
                  onSelected: _busy
                      ? null
                      : (_) => setState(() => _perfMode = o.$1),
                ),
            ],
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: (_video == null || _busy) ? null : _submit,
            child: Text(_busy ? _phase : '开始分析'),
          ),
          if (_busy || _phase.isNotEmpty) ...[
            const SizedBox(height: 20),
            LinearProgressIndicator(value: _busy ? _progress.clamp(0.05, 1) : null),
            const SizedBox(height: 8),
            Text(_message, style: Theme.of(context).textTheme.bodySmall),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Color(0xFFB42318))),
          ],
          if (_guidance != null) ...[
            const SizedBox(height: 20),
            Text('指导意见', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            SelectableText(_guidance!),
          ],
        ],
      ),
    );
  }
}
