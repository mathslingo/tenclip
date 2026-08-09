import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/tenclip_api.dart';
import '../config.dart';
import '../widgets/upload_card.dart';

class StrokePage extends StatefulWidget {
  const StrokePage({super.key});

  @override
  State<StrokePage> createState() => _StrokePageState();
}

class _StrokePageState extends State<StrokePage> {
  final _api = TenclipApi();
  final _picker = ImagePicker();

  File? _video;
  String? _videoLabel;
  double _motion = defaultMotionPercentile;
  bool _busy = false;
  double _progress = 0;
  String _phase = '';
  String _message = '';
  String? _error;
  String? _summary;
  String? _downloadUrl;
  Timer? _poll;

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
      _summary = null;
      _downloadUrl = null;
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
      _summary = null;
      _downloadUrl = null;
    });
    try {
      final submit = await _api.submitStroke(
        video: video,
        detectMode: defaultDetectMode,
        motionPercentile: _motion,
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
        _message = '上传完成，服务器处理中';
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
        final task = await _api.getStrokeTask(taskId);
        if (!mounted) return;
        setState(() {
          _progress = 0.55 + 0.45 * task.progressFrac.clamp(0, 1);
          _phase = _statusLabel(task.status);
          _message = task.progressMessage;
          if (task.queueSize > 0) {
            _message = '${task.progressMessage}（排队 ${task.queueSize}）';
          }
        });
        if (task.status == 'succeeded') {
          _poll?.cancel();
          setState(() {
            _busy = false;
            _progress = 1;
            _summary = task.summary ?? '提取完成';
            _downloadUrl = task.downloadUrl ?? _api.strokeDownloadUrl(taskId);
          });
        } else if (task.status == 'failed') {
          _poll?.cancel();
          setState(() {
            _busy = false;
            _error = task.error ?? '任务失败';
          });
        }
      } catch (e) {
        // 弱网继续轮询
      }
    });
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

  Future<void> _openDownload() async {
    final url = _downloadUrl;
    if (url == null) return;
    final uri = Uri.parse(url);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      setState(() => _error = '无法打开下载链接');
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        children: [
          const Text('击球剪辑'),
          const SizedBox(height: 8),
          Text(
            '上传网球视频，自动剪掉换边与等待，保留击球画面。',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: const Color(0xFF415360),
                ),
          ),
          const SizedBox(height: 20),
          UploadCard(
            label: _videoLabel ?? '点击选择视频',
            onTap: _busy ? null : _pick,
          ),
          const SizedBox(height: 20),
          Text('尖峰灵敏度 ${_motion.round()}'),
          Slider(
            min: 60,
            max: 92,
            divisions: 32,
            value: _motion,
            onChanged: _busy ? null : (v) => setState(() => _motion = v),
          ),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: (_video == null || _busy) ? null : _submit,
            child: Text(_busy ? _phase : '开始提取'),
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
          if (_summary != null) ...[
            const SizedBox(height: 16),
            Text(_summary!),
            if (_downloadUrl != null) ...[
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _openDownload,
                child: const Text('打开 / 下载集锦'),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
