import 'dart:async';

import '../config.dart';
import '../core/api_client.dart';
import '../models/models.dart';

/// 击球剪辑 / 动作分析任务 API（对齐 miniprogram api.js 上传部分 + poll.js）
class MobileApi {
  MobileApi(this._client);

  final ApiClient _client;

  // ── 击球剪辑 ──

  Future<TaskStatus> submitStrokeExtract({
    required String filePath,
    required int fileSize,
    double durationSec = 0,
    String detectMode = 'combined',
    double motionPercentile = defaultMotionPercentile,
    bool vlmFilter = false,
    void Function(UploadProgress)? onProgress,
    void Function(int attempt, int maxAttempts)? onRetry,
  }) async {
    final form = <String, String>{
      'detect_mode': detectMode,
      'motion_percentile': motionPercentile.toString(),
      'vlm_filter': vlmFilter ? '1' : '0',
    };
    final body = await _client.routeVideoUpload(
      filePath: filePath,
      fileSize: fileSize,
      durationSec: durationSec,
      purpose: 'stroke',
      formData: form,
      onProgress: onProgress,
      onRetry: onRetry,
      smallUpload: () => _client.uploadMultipart(
        path: '/api/mobile/stroke-extract/submit',
        filePath: filePath,
        fieldName: 'video',
        formData: form,
        onProgress: onProgress,
        onRetry: onRetry,
      ),
    );
    return TaskStatus.fromJson(body, apiBase: apiBaseUrl);
  }

  Future<TaskStatus> getStrokeTask(String taskId) async {
    final body = await _client.request('/api/mobile/stroke-extract/tasks/$taskId', auth: false);
    return TaskStatus.fromJson(Map<String, dynamic>.from(body as Map), taskId: taskId, apiBase: apiBaseUrl);
  }

  String strokeDownloadUrl(String taskId) =>
      '$apiBaseUrl/api/mobile/stroke-extract/tasks/$taskId/download';

  Future<String> downloadStrokeResult(String taskId, {void Function(int percent)? onProgress}) {
    return _client.downloadToTemp(strokeDownloadUrl(taskId), onProgress: onProgress);
  }

  // ── 动作分析 ──

  Future<TaskStatus> submitAnalyze({
    required String filePath,
    required int fileSize,
    double durationSec = 0,
    String perfMode = 'eco',
    String promptProfile = 'default',
    void Function(UploadProgress)? onProgress,
    void Function(int attempt, int maxAttempts)? onRetry,
  }) async {
    final form = <String, String>{
      'perf_mode': perfMode,
      'prompt_profile': promptProfile,
    };
    final body = await _client.routeVideoUpload(
      filePath: filePath,
      fileSize: fileSize,
      durationSec: durationSec,
      purpose: 'analyze',
      formData: form,
      onProgress: onProgress,
      onRetry: onRetry,
      smallUpload: () => _client.uploadMultipart(
        path: '/api/mobile/analyze-video/submit',
        filePath: filePath,
        fieldName: 'video',
        formData: form,
        onProgress: onProgress,
        onRetry: onRetry,
      ),
    );
    return TaskStatus.fromJson(body, apiBase: apiBaseUrl);
  }

  Future<TaskStatus> getAnalyzeTask(String taskId) async {
    final body = await _client.request('/api/mobile/analyze-video/tasks/$taskId', auth: false);
    final map = Map<String, dynamic>.from(body as Map);
    if (map['guidance'] == null && map['result'] is String) {
      map['guidance'] = map['result'];
    }
    if (map['guidance'] == null && map['result'] is Map) {
      final r = map['result'] as Map;
      map['guidance'] = r['guidance'] ?? r['markdown'] ?? r['text'];
    }
    return TaskStatus.fromJson(map, taskId: taskId, apiBase: apiBaseUrl);
  }
}

/// 任务轮询（对齐 poll.js startTaskPoll）
///
/// ```dart
/// final poller = TaskPoller(
///   fetchTask: () => api.getStrokeTask(id),
///   onUpdate: (t) => ...,
///   onDone: (t, err) => ...,
/// );
/// poller.start();
/// ...
/// poller.stop();
/// ```
class TaskPoller {
  TaskPoller({
    required this.fetchTask,
    required this.onUpdate,
    required this.onDone,
    this.interval = const Duration(seconds: 2),
    this.maxTransientErrors = 120,
  });

  final Future<TaskStatus> Function() fetchTask;
  final void Function(TaskStatus task) onUpdate;
  final void Function(TaskStatus? task, Object? error) onDone;
  final Duration interval;
  final int maxTransientErrors;

  Timer? _timer;
  int _errorStreak = 0;
  bool _stopped = true;
  bool _ticking = false;

  void start() {
    _stopped = false;
    _tick();
    _timer = Timer.periodic(interval, (_) => _tick());
  }

  void stop() {
    _stopped = true;
    _timer?.cancel();
    _timer = null;
  }

  /// 息屏恢复后手动补一次（对齐 stop.resume）
  void resume() {
    if (!_stopped) _tick();
  }

  Future<void> _tick() async {
    if (_stopped || _ticking) return;
    _ticking = true;
    try {
      final task = await fetchTask();
      _errorStreak = 0;
      onUpdate(task);
      if (task.isDone) {
        stop();
        onDone(task, null);
      }
    } catch (err) {
      final msg = err.toString();
      if (msg.contains('任务不存在')) {
        stop();
        onDone(null, err);
        return;
      }
      if (ApiClient.isTransient(err) && _errorStreak < maxTransientErrors) {
        _errorStreak += 1;
        onUpdate(TaskStatus(
          taskId: '',
          status: 'running',
          pollRetry: true,
          progressMessage: _pollRetryMessage(err, _errorStreak),
        ));
        return;
      }
      stop();
      onDone(null, err);
    } finally {
      _ticking = false;
    }
  }

  static String _pollRetryMessage(Object err, int streak) {
    final msg = err.toString().toLowerCase();
    if (msg.contains('interrupted')) {
      return '分析仍在服务器进行，可暂时息屏；亮屏后会自动继续…';
    }
    return '网络波动，继续等待…（$streak）';
  }
}
