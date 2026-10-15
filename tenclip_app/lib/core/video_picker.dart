import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:video_compress/video_compress.dart';
import 'package:video_player/video_player.dart';

import '../config.dart';
import '../models/models.dart';

/// 视频选择与压缩（对齐 miniprogram api.js 的 chooseTennisVideo / prepareVideoForUpload）
class VideoPicker {
  VideoPicker._();

  static final _picker = ImagePicker();

  /// 相册选视频（对齐 pickFromAlbumCompressed）
  static Future<PickedVideo?> pickFromAlbum() async {
    final x = await _picker.pickVideo(source: ImageSource.gallery);
    if (x == null) return null;
    return _enrich(PickedVideo(filePath: x.path, size: await x.length()));
  }

  /// 拍摄（最长 60s，对齐 CHOOSE_VIDEO_MAX_SEC）
  static Future<PickedVideo?> pickFromCamera() async {
    final x = await _picker.pickVideo(
      source: ImageSource.camera,
      maxDuration: const Duration(seconds: chooseVideoMaxSec),
    );
    if (x == null) return null;
    return _enrich(PickedVideo(filePath: x.path, size: await x.length()));
  }

  /// 底部弹窗：相册 / 拍摄
  static Future<PickedVideo?> chooseTennisVideo(BuildContext context) async {
    final source = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('从相册选择'),
              onTap: () => Navigator.pop(ctx, 'album'),
            ),
            ListTile(
              leading: const Icon(Icons.videocam_outlined),
              title: const Text('拍摄（最长 60 秒）'),
              onTap: () => Navigator.pop(ctx, 'camera'),
            ),
          ],
        ),
      ),
    );
    if (source == null) return null;
    final video = source == 'album' ? await pickFromAlbum() : await pickFromCamera();
    if (video == null || !context.mounted) return video;
    final ok = await showLongVideoGuidance(context, video);
    return ok ? video : null;
  }

  /// 补齐时长信息（对齐 enrichVideoFile）
  static Future<PickedVideo> _enrich(PickedVideo video) async {
    if (video.durationSec > 0) return video;
    final duration = await getVideoDuration(video.filePath);
    return PickedVideo(
      filePath: video.filePath,
      size: video.size,
      durationSec: duration,
    );
  }

  /// 用 video_player 读时长（秒）；失败返回 0
  static Future<double> getVideoDuration(String filePath) async {
    VideoPlayerController? controller;
    try {
      controller = VideoPlayerController.file(File(filePath));
      await controller.initialize();
      return controller.value.duration.inMilliseconds / 1000.0;
    } catch (_) {
      return 0;
    } finally {
      await controller?.dispose();
    }
  }

  /// 长视频/大文件提示（对齐 showLongVideoGuidance），返回是否继续
  static Future<bool> showLongVideoGuidance(BuildContext context, PickedVideo video) async {
    final sizeMb = video.size / (1024 * 1024);
    final dur = video.durationSec;
    final needWarn = sizeMb > uploadWarnSizeMb || dur > uploadWarnDurationSec;
    if (!needWarn) return true;
    final durText = dur > 0 ? formatDurationShort(dur) : '未知时长';
    final estCompress = dur >= uploadWarnDurationSec ? '3～8 分钟' : '1～3 分钟';
    final estUpload = sizeMb >= 80
        ? '5～15 分钟'
        : sizeMb >= 30
            ? '3～10 分钟'
            : '2～5 分钟';
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(dur >= uploadWarnDurationSec ? '长视频提示' : '大文件提示'),
        content: Text(
          '约 $durText / ${sizeMb > 0 ? '${sizeMb.toStringAsFixed(0)} MB' : '大小未知'}\n\n'
          '将自动压缩（约 $estCompress）并分片上传（约 $estUpload）。'
          '请使用 WiFi，保持屏幕常亮，不要退出 App。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('换视频'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('继续上传'),
          ),
        ],
      ),
    );
    return result ?? false;
  }

  /// 上传前压缩（对齐 prepareVideoForUpload + compressionProfile）
  ///
  /// 小文件直接跳过；压缩失败回退原文件。
  static Future<PickedVideo> prepareForUpload(
    PickedVideo video, {
    void Function(String status)? onStatus,
    void Function(int percent, String message)? onCompressProgress,
  }) async {
    final threshold = (uploadCompressAboveMb * 1024 * 1024).round();
    if (video.size <= 0 || video.size < threshold) {
      onCompressProgress?.call(12, '视频较小，跳过压缩，准备上传…');
      return video;
    }
    onStatus?.call('compressing');
    final sizeMb = video.size / (1024 * 1024);
    onCompressProgress?.call(4, '正在读取并压缩视频（约 ${sizeMb.toStringAsFixed(0)} MB），请稍候…');

    final aggressive = sizeMb >= uploadCompressAggressiveMb ||
        video.durationSec >= uploadCompressAggressiveSec;
    final quality = aggressive ? VideoQuality.LowQuality : VideoQuality.MediumQuality;

    Subscription? sub;
    var lastReported = 4;
    try {
      sub = VideoCompress.compressProgress$.subscribe((progress) {
        // video_compress 进度 0~100，映射到 5~22（对齐小程序模拟进度区间）
        final mapped = 5 + (progress / 100 * 17).round();
        if (mapped > lastReported) {
          lastReported = mapped;
          onCompressProgress?.call(
            mapped,
            '压缩进行中（约 $mapped%），长视频可能需要 1～3 分钟…',
          );
        }
      });
      final info = await VideoCompress.compressVideo(
        video.filePath,
        quality: quality,
        deleteOrigin: false,
        includeAudio: true,
      );
      sub.unsubscribe();
      final outPath = info?.file?.path;
      if (info == null || outPath == null) {
        onCompressProgress?.call(20, '压缩跳过，将上传原视频…');
        return video;
      }
      final newSize = info.filesize != null && info.filesize! > 0
          ? info.filesize!
          : await File(outPath).length();
      onCompressProgress?.call(24, '压缩完成，正在准备上传…');
      return PickedVideo(
        filePath: outPath,
        size: newSize,
        durationSec: video.durationSec,
      );
    } catch (_) {
      sub?.unsubscribe();
      onCompressProgress?.call(20, '压缩跳过，将上传原视频…');
      return video;
    }
  }

  /// 上传进度文案（对齐 formatUploadProgress）
  static String formatUploadProgress(int percent, int sent, int total, int startMs) {
    var msg = '正在上传视频（$percent%）';
    if (total > 0) {
      msg += ' · ${(sent / 1048576).toStringAsFixed(1)}/${(total / 1048576).toStringAsFixed(1)} MB';
    }
    final sec = (DateTime.now().millisecondsSinceEpoch - startMs) / 1000;
    if (sent > 0 && sec >= 2) {
      final speed = sent / sec;
      msg += ' · ${(speed / 1048576).toStringAsFixed(1)} MB/s';
      if (total > sent) {
        final remainSec = ((total - sent) / (speed > 1 ? speed : 1)).round();
        if (remainSec >= 5) {
          msg += ' · 约剩 ${(remainSec / 60).ceil() < 1 ? 1 : (remainSec / 60).ceil()} 分钟';
        }
      }
    }
    return msg;
  }
}
