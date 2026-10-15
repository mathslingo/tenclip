import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';
import 'package:path/path.dart' as p;

import '../config.dart';
import 'session.dart';

/// API 异常（对齐小程序 normalizeError 后的语义）
class ApiException implements Exception {
  ApiException(this.message, {this.statusCode = 0, this.transient = false});

  final String message;
  final int statusCode;

  /// 息屏/切后台/弱网导致的可恢复错误（轮询/上传应重试而非判失败）
  final bool transient;

  @override
  String toString() => message;
}

class UploadProgress {
  const UploadProgress({required this.percent, required this.sent, required this.total});

  final int percent;
  final int sent;
  final int total;
}

/// 统一网络层（对齐 miniprogram/utils/api.js）
class ApiClient {
  ApiClient(this._session)
      : _dio = Dio(BaseOptions(
          baseUrl: apiBaseUrl,
          connectTimeout: const Duration(seconds: 20),
          receiveTimeout: const Duration(milliseconds: requestTimeoutMs),
        ));

  final Session _session;
  final Dio _dio;

  Map<String, String> authHeaders([Map<String, String>? extra]) {
    final h = <String, String>{'content-type': 'application/json'};
    if (extra != null) h.addAll(extra);
    final t = _session.token;
    if (t.isNotEmpty) h['Authorization'] = 'Bearer $t';
    return h;
  }

  // ── 错误分类（对齐 isTimeoutError / isTransientNetworkError 等）──

  static bool _isTimeout(DioException e) =>
      e.type == DioExceptionType.connectionTimeout ||
      e.type == DioExceptionType.sendTimeout ||
      e.type == DioExceptionType.receiveTimeout;

  static bool isTransient(Object err) {
    if (err is ApiException) return err.transient;
    if (err is DioException) {
      if (_isTimeout(err)) return true;
      if (err.type == DioExceptionType.connectionError) return true;
      final msg = (err.message ?? '').toLowerCase();
      return msg.contains('network') ||
          msg.contains('connection') ||
          msg.contains('reset') ||
          msg.contains('abort');
    }
    if (err is SocketException) return true;
    if (err is TimeoutException) return true;
    final msg = err.toString().toLowerCase();
    return msg.contains('timeout') ||
        msg.contains('timed out') ||
        msg.contains('connection') ||
        msg.contains('reset') ||
        msg.contains('网络') ||
        msg.contains('断开');
  }

  static bool _isConnectionReset(DioException e) {
    final msg = '${e.message} ${e.error}'.toLowerCase();
    return msg.contains('connection_reset') ||
        msg.contains('connection reset') ||
        msg.contains('err_connection_reset');
  }

  /// 服务端尚未部署分片上传接口（404）时回退普通上传
  static bool isChunkApiUnavailable(Object err) {
    if (err is ApiException && err.statusCode == 404) return true;
    final msg = err.toString().toLowerCase();
    return msg.contains('404') ||
        msg.contains('not found') ||
        msg.contains('upload-sessions');
  }

  ApiException _normalize(Object err, [String fallback = '网络错误']) {
    if (err is ApiException) return err;
    if (err is DioException) {
      if (_isTimeout(err)) {
        return ApiException(
          '上传超时：长视频请用 WiFi、保持在本页等待；若仍失败可先剪短再传或换时段重试',
          transient: true,
        );
      }
      if (_isConnectionReset(err)) {
        return ApiException(
          '连接被中断（ERR_CONNECTION_RESET）。请换 WiFi 重试；大视频请先压缩或选较短片段。',
          transient: true,
        );
      }
      if (err.type == DioExceptionType.connectionError) {
        return ApiException(
          '无法连接 API\n当前地址：$apiBaseUrl\n请检查手机网络与后端服务是否在运行。',
          transient: true,
        );
      }
      final res = err.response;
      if (res != null) {
        return ApiException(
          _parseDetail(res.data, '请求失败 (${res.statusCode})'),
          statusCode: res.statusCode ?? 0,
        );
      }
      return ApiException(err.message ?? fallback, transient: true);
    }
    return ApiException(err.toString());
  }

  /// 对齐 parseApiDetail：FastAPI detail 可能是字符串或校验错误数组
  static String _parseDetail(dynamic body, String fallback) {
    if (body == null) return fallback;
    if (body is String) return body.isEmpty ? fallback : body;
    if (body is Map) {
      final detail = body['detail'] ?? body['error'];
      if (detail is String) return detail;
      if (detail is List) {
        return detail
            .map((d) => d is Map ? (d['msg']?.toString() ?? d.toString()) : d.toString())
            .join('; ');
      }
    }
    return fallback;
  }

  // ── 基础 JSON 请求 ──

  Future<dynamic> request(
    String path, {
    String method = 'GET',
    dynamic data,
    Map<String, String>? query,
    Map<String, String>? headers,
    bool auth = true,
    int timeoutMs = 20000,
  }) async {
    try {
      final res = await _dio.request<dynamic>(
        path,
        data: data,
        queryParameters: query,
        options: Options(
          method: method,
          headers: auth ? authHeaders(headers) : headers,
          contentType: 'application/json',
          sendTimeout: Duration(milliseconds: timeoutMs),
          receiveTimeout: Duration(milliseconds: timeoutMs),
        ),
      );
      return res.data;
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _session.clearSession();
        throw ApiException('请先登录', statusCode: 401);
      }
      if (e.response?.statusCode == 404 && method == 'GET') {
        // 对齐 requestJson 的「任务不存在」语义由调用方判断
        throw ApiException(
          _parseDetail(e.response?.data, '请求失败 (404)'),
          statusCode: 404,
        );
      }
      throw _normalize(e);
    }
  }

  /// form-urlencoded POST（分片上传会话等）
  Future<dynamic> postForm(String path, Map<String, String> data) async {
    try {
      final res = await _dio.post<dynamic>(
        path,
        data: data,
        options: Options(
          contentType: 'application/x-www-form-urlencoded',
          sendTimeout: const Duration(milliseconds: uploadTimeoutMs),
          receiveTimeout: const Duration(milliseconds: uploadTimeoutMs),
        ),
      );
      return res.data;
    } on DioException catch (e) {
      throw _normalize(e, '网络错误');
    }
  }

  // ── 单文件 multipart 上传（带重试，对齐 uploadMultipartRetry）──

  Future<Map<String, dynamic>> uploadMultipart({
    required String path,
    required String filePath,
    required String fieldName,
    Map<String, String>? formData,
    void Function(UploadProgress)? onProgress,
    void Function(int attempt, int maxAttempts)? onRetry,
    int maxAttempts = 5,
  }) async {
    var attempt = 0;
    while (true) {
      attempt += 1;
      try {
        final name = p.basename(filePath);
        final form = FormData.fromMap({
          ...?formData,
          fieldName: await MultipartFile.fromFile(
            filePath,
            filename: name.isEmpty ? 'video.mp4' : name,
            contentType: MediaType('video', 'mp4'),
          ),
        });
        final res = await _dio.post<dynamic>(
          path,
          data: form,
          options: Options(
            headers: {
              if (_session.token.isNotEmpty)
                'Authorization': 'Bearer ${_session.token}',
            },
            sendTimeout: const Duration(milliseconds: uploadTimeoutMs),
            receiveTimeout: const Duration(milliseconds: uploadTimeoutMs),
          ),
          onSendProgress: (sent, total) {
            if (onProgress != null && total > 0) {
              onProgress(UploadProgress(
                percent: (sent / total * 100).round(),
                sent: sent,
                total: total,
              ));
            }
          },
        );
        final data = res.data;
        if (data is Map) return Map<String, dynamic>.from(data);
        if (data is String) return Map<String, dynamic>.from(jsonDecode(data) as Map);
        return <String, dynamic>{};
      } on DioException catch (e) {
        final normalized = _normalize(e, '上传失败');
        if (!normalized.transient || attempt >= maxAttempts) throw normalized;
        onRetry?.call(attempt, maxAttempts);
        await Future<void>.delayed(Duration(milliseconds: 1500 * attempt));
      }
    }
  }

  // ── 分片上传（对齐 chunkVideoUpload）──

  Future<Map<String, dynamic>> chunkVideoUpload({
    required String filePath,
    required int fileSize,
    required String purpose,
    Map<String, String>? formData,
    void Function(UploadProgress)? onProgress,
    void Function(int attempt, int maxAttempts)? onRetry,
  }) async {
    final totalChunks =
        fileSize <= 0 ? 1 : (fileSize + chunkSizeBytes - 1) ~/ chunkSizeBytes;
    final initData = <String, String>{
      ...?formData,
      'purpose': purpose,
      'file_size': '$fileSize',
      'filename': p.basename(filePath),
      'total_chunks': '$totalChunks',
      'chunk_size': '$chunkSizeBytes',
    };
    final sessionRes = await postForm('/api/mobile/upload-sessions', initData);
    final session = Map<String, dynamic>.from(sessionRes as Map);
    final sessionId = session['session_id']?.toString() ?? '';
    if (sessionId.isEmpty) {
      throw ApiException('分片上传会话创建失败');
    }
    final chunkSize = (session['chunk_size'] as num?)?.toInt() ?? chunkSizeBytes;
    final chunks = (session['total_chunks'] as num?)?.toInt() ?? totalChunks;

    final raf = await File(filePath).open();
    try {
      for (var index = 0; index < chunks; index++) {
        final offset = index * chunkSize;
        final length =
            offset + chunkSize <= fileSize ? chunkSize : fileSize - offset;
        await raf.setPosition(offset);
        final buffer = await raf.read(length);
        await _uploadChunkWithRetry(sessionId, index, buffer, onRetry);
        onProgress?.call(UploadProgress(
          percent: ((index + 1) / chunks * 99).round(),
          sent: (index + 1) * chunkSize > fileSize ? fileSize : (index + 1) * chunkSize,
          total: fileSize,
        ));
      }
    } finally {
      await raf.close();
    }

    final done = await postForm('/api/mobile/upload-sessions/$sessionId/complete', {});
    return Map<String, dynamic>.from(done as Map);
  }

  Future<void> _uploadChunkWithRetry(
    String sessionId,
    int chunkIndex,
    List<int> buffer,
    void Function(int attempt, int maxAttempts)? onRetry, {
    int maxAttempts = 5,
  }) async {
    var attempt = 0;
    while (true) {
      attempt += 1;
      try {
        await _dio.put<dynamic>(
          '/api/mobile/upload-sessions/$sessionId/chunks/$chunkIndex',
          data: buffer,
          options: Options(
            contentType: 'application/octet-stream',
            sendTimeout: const Duration(milliseconds: uploadTimeoutMs),
            receiveTimeout: const Duration(milliseconds: uploadTimeoutMs),
          ),
        );
        return;
      } on DioException catch (e) {
        final normalized = _normalize(e, '上传失败');
        if (!normalized.transient || attempt >= maxAttempts) throw normalized;
        onRetry?.call(attempt, maxAttempts);
        await Future<void>.delayed(Duration(milliseconds: 1500 * attempt));
      }
    }
  }

  /// 上传路由：大文件/长视频走分片，失败 404 时回退单文件（对齐 routeVideoUpload）
  Future<Map<String, dynamic>> routeVideoUpload({
    required String filePath,
    required int fileSize,
    required double durationSec,
    required String purpose,
    required Future<Map<String, dynamic>> Function() smallUpload,
    Map<String, String>? formData,
    void Function(UploadProgress)? onProgress,
    void Function(int attempt, int maxAttempts)? onRetry,
  }) async {
    final sizeBytes = fileSize > 0 ? fileSize : await File(filePath).length();
    final useChunk = sizeBytes > uploadLargeRouteMb * 1024 * 1024 ||
        durationSec > uploadChunkDurationSec;
    if (useChunk) {
      try {
        return await chunkVideoUpload(
          filePath: filePath,
          fileSize: sizeBytes,
          purpose: purpose,
          formData: formData,
          onProgress: onProgress,
          onRetry: onRetry,
        );
      } catch (e) {
        if (isChunkApiUnavailable(e)) {
          return smallUpload();
        }
        rethrow;
      }
    }
    return smallUpload();
  }

  // ── 下载 ──

  Future<String> downloadToTemp(
    String url, {
    void Function(int percent)? onProgress,
  }) async {
    final dir = await Directory.systemTemp.createTemp('tenclip_dl');
    final savePath = p.join(dir.path, 'download_${DateTime.now().millisecondsSinceEpoch}.mp4');
    try {
      await _dio.download(
        url,
        savePath,
        options: Options(
          receiveTimeout: const Duration(milliseconds: downloadTimeoutMs),
        ),
        onReceiveProgress: (received, total) {
          if (onProgress != null && total > 0) {
            onProgress((received / total * 100).round());
          }
        },
      );
      return savePath;
    } on DioException catch (e) {
      throw _normalize(e, '下载失败');
    }
  }

  // ── 探活 ──

  Future<Map<String, dynamic>> pingHealthOnce() async {
    try {
      final res = await _dio.get<dynamic>(
        '/api/mobile/health',
        options: Options(
          sendTimeout: const Duration(milliseconds: healthTimeoutMs),
          receiveTimeout: const Duration(milliseconds: healthTimeoutMs),
        ),
      );
      final data = res.data;
      if (res.statusCode == 200 && data is Map && data['ok'] == true) {
        return Map<String, dynamic>.from(data);
      }
      throw ApiException('后端未就绪 (HTTP ${res.statusCode})');
    } on DioException catch (e) {
      throw _normalize(e, '无法连接后端，请确认已启动 app.py');
    }
  }

  /// 多次探活（对齐 pingHealth）
  Future<Map<String, dynamic>> pingHealth([int maxAttempts = 5]) async {
    var attempt = 0;
    while (true) {
      attempt += 1;
      try {
        return await pingHealthOnce();
      } catch (e) {
        if (isTransient(e) && attempt < maxAttempts) {
          await Future<void>.delayed(Duration(milliseconds: 500 * attempt));
          continue;
        }
        rethrow;
      }
    }
  }
}
