import 'dart:io';

import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';
import 'package:path/path.dart' as p;

import '../config.dart';

class TaskStatus {
  TaskStatus({
    required this.taskId,
    required this.status,
    this.progressFrac = 0,
    this.progressMessage = '',
    this.queueSize = 0,
    this.error,
    this.summary,
    this.guidance,
    this.downloadUrl,
  });

  final String taskId;
  final String status;
  final double progressFrac;
  final String progressMessage;
  final int queueSize;
  final String? error;
  final String? summary;
  final String? guidance;
  final String? downloadUrl;

  bool get isDone => status == 'succeeded' || status == 'failed';

  factory TaskStatus.fromJson(Map<String, dynamic> json, {String? taskId}) {
    final id = taskId ?? json['task_id']?.toString() ?? '';
    String? guidance;
    final result = json['result'];
    if (result is Map) {
      guidance = result['guidance']?.toString() ?? result['text']?.toString();
    }
    guidance ??= json['guidance']?.toString() ?? json['result_text']?.toString();

    String? download = json['download_url']?.toString();
    if (download != null && download.startsWith('/')) {
      download = '$apiBaseUrl$download';
    }

    return TaskStatus(
      taskId: id,
      status: json['status']?.toString() ?? 'unknown',
      progressFrac: (json['progress_frac'] as num?)?.toDouble() ?? 0,
      progressMessage: json['progress_message']?.toString() ?? '',
      queueSize: (json['queue_size'] as num?)?.toInt() ?? 0,
      error: json['error']?.toString() ?? json['error_message']?.toString(),
      summary: json['summary']?.toString(),
      guidance: guidance,
      downloadUrl: download,
    );
  }
}

class TenclipApi {
  TenclipApi({Dio? dio})
      : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: apiBaseUrl,
                connectTimeout: const Duration(seconds: 30),
                receiveTimeout: const Duration(minutes: 10),
                sendTimeout: const Duration(minutes: 10),
              ),
            );

  final Dio _dio;

  Future<void> pingHealth() async {
    final res = await _dio.get('/api/mobile/health');
    if (res.statusCode != 200) {
      throw DioException(
        requestOptions: res.requestOptions,
        message: 'health HTTP ${res.statusCode}',
      );
    }
  }

  Future<TaskStatus> submitStroke({
    required File video,
    String detectMode = defaultDetectMode,
    double motionPercentile = defaultMotionPercentile,
    bool vlmFilter = false,
    void Function(int sent, int total)? onSendProgress,
  }) async {
    final name = p.basename(video.path);
    final form = FormData.fromMap({
      'detect_mode': detectMode,
      'motion_percentile': motionPercentile.toString(),
      'vlm_filter': vlmFilter ? '1' : '0',
      'video': await MultipartFile.fromFile(
        video.path,
        filename: name.isEmpty ? 'video.mp4' : name,
        contentType: MediaType('video', 'mp4'),
      ),
    });
    final res = await _dio.post(
      '/api/mobile/stroke-extract/submit',
      data: form,
      onSendProgress: onSendProgress,
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    return TaskStatus.fromJson(data);
  }

  Future<TaskStatus> getStrokeTask(String taskId) async {
    final res = await _dio.get('/api/mobile/stroke-extract/tasks/$taskId');
    return TaskStatus.fromJson(
      Map<String, dynamic>.from(res.data as Map),
      taskId: taskId,
    );
  }

  String strokeDownloadUrl(String taskId) =>
      '$apiBaseUrl/api/mobile/stroke-extract/tasks/$taskId/download';

  Future<TaskStatus> submitAnalyze({
    required File video,
    String perfMode = 'eco',
    String promptProfile = 'default',
    void Function(int sent, int total)? onSendProgress,
  }) async {
    final name = p.basename(video.path);
    final form = FormData.fromMap({
      'perf_mode': perfMode,
      'prompt_profile': promptProfile,
      'video': await MultipartFile.fromFile(
        video.path,
        filename: name.isEmpty ? 'video.mp4' : name,
        contentType: MediaType('video', 'mp4'),
      ),
    });
    final res = await _dio.post(
      '/api/mobile/analyze-video/submit',
      data: form,
      onSendProgress: onSendProgress,
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    return TaskStatus.fromJson(data);
  }

  Future<TaskStatus> getAnalyzeTask(String taskId) async {
    final res = await _dio.get('/api/mobile/analyze-video/tasks/$taskId');
    final map = Map<String, dynamic>.from(res.data as Map);
    // 动作分析结果字段因版本可能不同，尽量从常见键取出正文
    if (map['guidance'] == null && map['result'] is String) {
      map['guidance'] = map['result'];
    }
    if (map['guidance'] == null && map['result'] is Map) {
      final r = map['result'] as Map;
      map['guidance'] = r['guidance'] ?? r['markdown'] ?? r['text'];
    }
    return TaskStatus.fromJson(map, taskId: taskId);
  }
}
