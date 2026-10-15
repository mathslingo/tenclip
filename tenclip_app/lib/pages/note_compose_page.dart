import 'dart:io';

import 'package:flutter/material.dart';
import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../api/social_api.dart';
import '../core/api_client.dart';
import '../main.dart' show requireLogin;
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 发笔记 / 发场地 / 收场地（对齐 miniprogram pages/note-compose）
class NoteComposePage extends StatefulWidget {
  const NoteComposePage({super.key, this.kind = 'note'});

  /// note（发笔记）/ offer（发场地）/ seek（收场地）
  final String kind;

  @override
  State<NoteComposePage> createState() => _NoteComposePageState();
}

class _NoteComposePageState extends State<NoteComposePage> {
  late final String _kind = switch (widget.kind) {
    'offer' || 'seek' => widget.kind,
    _ => 'note',
  };

  bool get _required => _kind != 'note';
  String get _kindLabel => _kind == 'offer' ? '发场地' : (_kind == 'seek' ? '收场地' : '');
  String get _navTitle => _required ? _kindLabel : '发笔记';
  String get _titlePlaceholder => _kind == 'offer'
      ? '场地名称 / 片区（可选）'
      : (_kind == 'seek' ? '想找的场地类型（可选）' : '标题（可选）');
  String get _bodyPlaceholder => _kind == 'offer'
      ? '说明空场信息：室内外、硬地/红土、几片、价格、是否可约灯、注意事项…'
      : (_kind == 'seek'
          ? '说明需求：室内外、硬地/红土、几人、预算、水平、希望的时间地点…'
          : '分享你的网球日常、训练心得…');

  final TextEditingController _titleCtrl = TextEditingController();
  final TextEditingController _bodyCtrl = TextEditingController();
  final TextEditingController _locNameCtrl = TextEditingController();
  final ImagePicker _picker = ImagePicker();

  List<String> _images = [];
  bool _busy = false;
  int _imageDone = 0;
  int _imageTotal = 0;
  PublishLimits _limits = const PublishLimits();

  bool _locationEnabled = false;
  String _locationAddress = '';
  double? _latitude;
  double? _longitude;
  bool _locating = false;

  bool _timeEnabled = false;
  DateTime? _startAt;
  DateTime? _endAt;
  bool _timeTouched = false;
  bool _endTouched = false;

  AppState get _app => context.read<AppState>();
  SocialApi get _social => context.read<SocialApi>();

  @override
  void initState() {
    super.initState();
    // 场地类必带地点与时间段（对齐 onLoad 中 offer/seek 的初始化）
    _locationEnabled = _required;
    _timeEnabled = _required;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (!_app.isLoggedIn) {
        requireLogin(context, from: 'note-compose');
      }
      _refreshLimits();
    });
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _bodyCtrl.dispose();
    _locNameCtrl.dispose();
    super.dispose();
  }

  Future<void> _refreshLimits() async {
    final cfg = await _social.fetchPublishLimits();
    if (!mounted) return;
    setState(() => _limits = cfg);
  }

  static String _fmtDt(DateTime dt) {
    String p2(int v) => v.toString().padLeft(2, '0');
    return '${dt.year}-${p2(dt.month)}-${p2(dt.day)} ${p2(dt.hour)}:00';
  }

  // ── 图片（对齐 chooseMedia：相册/拍摄，上限 maxImages）──

  Future<void> _onAddImages() async {
    final remain = _limits.maxImages - _images.length;
    if (remain <= 0) {
      showToast(context, '最多 ${_limits.maxImages} 张图片');
      return;
    }
    final source = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: const Text('拍照', textAlign: TextAlign.center),
              onTap: () => Navigator.pop(ctx, 'camera'),
            ),
            ListTile(
              title: const Text('从相册选择', textAlign: TextAlign.center),
              onTap: () => Navigator.pop(ctx, 'album'),
            ),
            ListTile(
              title: const Text('取消', textAlign: TextAlign.center),
              onTap: () => Navigator.pop(ctx),
            ),
          ],
        ),
      ),
    );
    if (source == null || !mounted) return;
    try {
      if (source == 'camera') {
        final x = await _picker.pickImage(source: ImageSource.camera);
        if (x != null && mounted) {
          setState(() => _images = [..._images, x.path]);
        }
      } else {
        final xs = await _picker.pickMultiImage(limit: remain);
        if (xs.isNotEmpty && mounted) {
          setState(() {
            _images = [..._images, for (final x in xs) x.path];
            if (_images.length > _limits.maxImages) {
              _images = _images.sublist(0, _limits.maxImages);
            }
          });
        }
      }
    } catch (_) {}
  }

  void _onRemoveImage(int index) {
    if (index < 0 || index >= _images.length) return;
    setState(() => _images = [..._images]..removeAt(index));
  }

  void _onPreviewImage(int index) {
    if (_images.isEmpty) return;
    showDialog<void>(
      context: context,
      barrierColor: Colors.black,
      builder: (_) => _LocalImagePreview(paths: _images, initial: index),
    );
  }

  // ── 地点（wx.chooseLocation → iOS v1 获取当前位置 + 手动输入地点名）──

  void _onToggleLocation(bool on) {
    if (!on) {
      setState(() {
        _locationEnabled = false;
        _locNameCtrl.clear();
        _locationAddress = '';
        _latitude = null;
        _longitude = null;
      });
      return;
    }
    setState(() => _locationEnabled = true);
    if (_locNameCtrl.text.isEmpty && _locationAddress.isEmpty) {
      _onGetLocation();
    }
  }

  Future<void> _onGetLocation() async {
    if (_locating) return;
    setState(() => _locating = true);
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
        if (mounted) showToast(context, '请允许位置权限后重试');
        return;
      }
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.medium,
          timeLimit: Duration(seconds: 10),
        ),
      );
      // 反解地名（对齐 chooseLocation 的 name/address）
      var name = '';
      var addr = '';
      try {
        final marks = await placemarkFromCoordinates(pos.latitude, pos.longitude);
        if (marks.isNotEmpty) {
          final m = marks.first;
          name = (m.name ?? '').trim();
          final parts = <String>{
            (m.administrativeArea ?? '').trim(),
            (m.locality ?? '').trim(),
            (m.subLocality ?? '').trim(),
            (m.thoroughfare ?? '').trim(),
          }..removeWhere((e) => e.isEmpty);
          addr = parts.join();
        }
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _locationEnabled = true;
        _latitude = pos.latitude;
        _longitude = pos.longitude;
        _locationAddress = addr;
        _locNameCtrl.text = name.isNotEmpty ? name : (addr.isNotEmpty ? addr : '已选位置');
      });
    } catch (_) {
      if (mounted) showToast(context, '定位失败，请重试');
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  void _onClearLocation() {
    setState(() {
      _locNameCtrl.clear();
      _locationAddress = '';
      _latitude = null;
      _longitude = null;
    });
  }

  // ── 时间（multiSelector 年/月/日/时 → 系统日期+时间选择器，按小时精度）──

  void _onToggleTime(bool on) {
    if (!on) {
      setState(() => _timeEnabled = false);
      return;
    }
    setState(() {
      _timeEnabled = true;
      _startAt ??= DateTime.now();
    });
  }

  Future<DateTime?> _pickDateTime(DateTime initial) async {
    final now = DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(now.year - 1, 1, 1),
      lastDate: DateTime(now.year + 2, 12, 31),
    );
    if (d == null || !mounted) return null;
    final t = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initial),
    );
    if (t == null || !mounted) return null;
    return DateTime(d.year, d.month, d.day, t.hour);
  }

  Future<void> _pickStart() async {
    final picked = await _pickDateTime(_startAt ?? DateTime.now());
    if (picked == null || !mounted) return;
    setState(() {
      _startAt = picked;
      _timeTouched = true;
    });
  }

  Future<void> _pickEnd() async {
    final base = _endAt ?? (_startAt ?? DateTime.now()).add(const Duration(hours: 1));
    final picked = await _pickDateTime(base);
    if (picked == null || !mounted) return;
    setState(() {
      _endAt = picked;
      _endTouched = true;
    });
  }

  // ── 发布（对齐 onPublish 校验与 payload 组装）──

  Future<void> _onPublish() async {
    if (_busy) return;
    if (!requireLogin(context, from: 'note-compose')) return;
    final body = _bodyCtrl.text.trim();
    if (body.isEmpty && _images.isEmpty) {
      showToast(context, '请填写正文或添加图片');
      return;
    }
    if (_required) {
      final hasLocText = _locNameCtrl.text.trim().isNotEmpty || _locationAddress.isNotEmpty;
      if (!hasLocText || _latitude == null || _longitude == null) {
        showToast(context, '请先选择地点');
        return;
      }
      if (!_timeTouched || _startAt == null) {
        showToast(context, '请先选择开始时间');
        return;
      }
      if (!_endTouched || _endAt == null) {
        showToast(context, '请先选择结束时间');
        return;
      }
      if (!_endAt!.isAfter(_startAt!)) {
        showToast(context, '结束时间需晚于开始时间');
        return;
      }
    }
    if (_locationEnabled && _locNameCtrl.text.trim().isEmpty && _locationAddress.isEmpty) {
      showToast(context, '请获取当前位置或输入地点名，或关闭地点');
      return;
    }
    final remaining = _limits.notesRemainingToday;
    if (remaining != null && remaining <= 0) {
      showToast(context, '今日发布已达上限');
      return;
    }

    var title = _titleCtrl.text;
    if (_required) {
      final base = title.trim().isNotEmpty ? title.trim() : _locNameCtrl.text.trim();
      title = '【$_kindLabel】$base';
      if (title.length > 40) title = title.substring(0, 40);
    }
    var sendBody = body;
    if (_required) {
      final s = _fmtDt(_startAt!);
      final e = _fmtDt(_endAt!);
      final endShort = s.substring(0, 10) == e.substring(0, 10) ? e.substring(11) : e;
      sendBody = '时间：$s ~ $endShort${body.isNotEmpty ? '\n$body' : ''}';
    }

    setState(() {
      _busy = true;
      _imageDone = 0;
      _imageTotal = _images.length;
    });
    try {
      try {
        await _social.upsertMe();
      } catch (_) {}
      await _social.publishNote(
        title: title,
        body: sendBody,
        imagePaths: _images,
        locationName: _locationEnabled ? _locNameCtrl.text.trim() : '',
        locationAddress: _locationEnabled ? _locationAddress : '',
        latitude: _locationEnabled ? _latitude : null,
        longitude: _locationEnabled ? _longitude : null,
        eventAt: _timeEnabled && _startAt != null ? _startAt!.millisecondsSinceEpoch ~/ 1000 : null,
        onImageProgress: (done, total) {
          if (mounted) {
            setState(() {
              _imageDone = done;
              _imageTotal = total;
            });
          }
        },
      );
      if (!mounted) return;
      showToast(context, '已发布');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      showToast(context, e is ApiException && e.message.isNotEmpty ? e.message : '发布失败');
    }
  }

  // ── 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: themedAppBar(context, title: _navTitle),
      body: ThemedPage(
        child: ListView(
          padding: EdgeInsets.fromLTRB(12, 12, 12, 24 + MediaQuery.of(context).padding.bottom),
          children: [
            _buildTextCard(),
            const SizedBox(height: 10),
            _buildImageCard(),
            const SizedBox(height: 10),
            _buildLocationCard(),
            const SizedBox(height: 10),
            _buildTimeCard(),
            const SizedBox(height: 6),
            AccentButton(
              label: _required ? '发布$_kindLabel' : '发布',
              loading: _busy,
              onPressed: _onPublish,
            ),
            if (_busy && _imageTotal > 0) ...[
              const SizedBox(height: 8),
              Center(
                child: Text(
                  '图片上传中 $_imageDone/$_imageTotal…',
                  style: const TextStyle(fontSize: 11, color: S.faint),
                ),
              ),
            ],
            const SizedBox(height: 10),
            Center(
              child: Text(
                '${_limits.dayHint} · 笔记会出现在「发现」和「我的 · 作品」。',
                style: const TextStyle(fontSize: 11, color: S.faint),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 标题 + 正文 + 字数（对齐 .card 输入区）
  Widget _buildTextCard() {
    return SlamCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _titleCtrl,
            maxLength: 40,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: S.ink),
            cursorColor: S.green,
            decoration: InputDecoration(
              hintText: _titlePlaceholder,
              hintStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: S.faint),
              counterText: '',
              isDense: true,
              contentPadding: const EdgeInsets.only(bottom: 10),
              border: const UnderlineInputBorder(borderSide: BorderSide(color: S.line)),
              enabledBorder: const UnderlineInputBorder(borderSide: BorderSide(color: S.line)),
              focusedBorder: const UnderlineInputBorder(borderSide: BorderSide(color: S.line)),
            ),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _bodyCtrl,
            minLines: 5,
            maxLines: null,
            maxLength: 1000,
            onChanged: (_) => setState(() {}),
            style: const TextStyle(fontSize: 14, color: Color(0xFF333333), height: 1.6),
            cursorColor: S.green,
            decoration: InputDecoration(
              hintText: _bodyPlaceholder,
              hintStyle: const TextStyle(fontSize: 14, color: S.faint),
              counterText: '',
              isDense: true,
              border: InputBorder.none,
            ),
          ),
          Align(
            alignment: Alignment.centerRight,
            child: Text(
              '${_bodyCtrl.text.length}/1000',
              style: const TextStyle(fontSize: 11, color: S.faint),
            ),
          ),
        ],
      ),
    );
  }

  // 图片九宫格（对齐 .img-grid，cell 200rpx→100）
  Widget _buildImageCard() {
    return SlamCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('图片', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink)),
              Text(_limits.imageHint, style: const TextStyle(fontSize: 11, color: S.faint)),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (var i = 0; i < _images.length; i++) _imageCell(i),
              if (_images.length < _limits.maxImages) _addImageCell(),
            ],
          ),
        ],
      ),
    );
  }

  Widget _imageCell(int index) {
    return SizedBox(
      width: 100,
      height: 100,
      child: Stack(
        children: [
          Positioned.fill(
            child: GestureDetector(
              onTap: () => _onPreviewImage(index),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.file(File(_images[index]), fit: BoxFit.cover),
              ),
            ),
          ),
          Positioned(
            top: 4,
            right: 4,
            child: GestureDetector(
              onTap: () => _onRemoveImage(index),
              child: Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.55),
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: const Text('×', style: TextStyle(color: Colors.white, fontSize: 14, height: 1)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _addImageCell() {
    return GestureDetector(
      onTap: _onAddImages,
      child: Container(
        width: 100,
        height: 100,
        decoration: BoxDecoration(
          color: const Color(0xFFFAFBFC),
          borderRadius: BorderRadius.circular(8),
          // Flutter 无边框虚线样式，用细实线近似 dashed #d0d5dd
          border: Border.all(color: const Color(0xFFD0D5DD)),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('＋', style: TextStyle(fontSize: 24, height: 1, color: slamOf(context).accent)),
            const SizedBox(height: 3),
            const Text('添加', style: TextStyle(fontSize: 11, color: Color(0xFF8A8A8A))),
          ],
        ),
      ),
    );
  }

  // 地点卡片（对齐 .loc-box；iOS v1 为获取当前位置 + 手动输入）
  Widget _buildLocationCard() {
    final theme = slamOf(context);
    final hasLoc = _locNameCtrl.text.isNotEmpty || _locationAddress.isNotEmpty;
    return SlamCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('地图选点', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink)),
                    const SizedBox(height: 3),
                    Text(
                      _required ? '必填 · 场地所在位置' : '分享打球地点（可选）',
                      style: const TextStyle(fontSize: 11, color: S.faint),
                    ),
                  ],
                ),
              ),
              if (!_required)
                Switch(
                  value: _locationEnabled,
                  activeColor: theme.accent,
                  onChanged: _onToggleLocation,
                ),
            ],
          ),
          if (_locationEnabled) ...[
            const SizedBox(height: 10),
            GestureDetector(
              onTap: _locating ? null : _onGetLocation,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 10),
                decoration: BoxDecoration(
                  color: const Color(0xFFF7FAF9),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.location_on, size: 18, color: theme.accent),
                    const SizedBox(width: 7),
                    Expanded(
                      child: _locating
                          ? const Text(
                              '定位中…',
                              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: Color(0xFF5C6570)),
                            )
                          : hasLoc
                              ? Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _locNameCtrl.text,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w600,
                                        color: S.ink,
                                      ),
                                    ),
                                    if (_locationAddress.isNotEmpty) ...[
                                      const SizedBox(height: 2),
                                      Text(
                                        _locationAddress,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(fontSize: 11, color: S.faint),
                                      ),
                                    ],
                                  ],
                                )
                              : const Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '点击获取当前位置',
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w500,
                                        color: Color(0xFF5C6570),
                                      ),
                                    ),
                                    SizedBox(height: 2),
                                    Text('定位后附带地址一起发布', style: TextStyle(fontSize: 11, color: S.faint)),
                                  ],
                                ),
                    ),
                    if (_locating)
                      const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    else
                      const Text('›', style: TextStyle(fontSize: 18, height: 1, color: Color(0xFFC0C5CE))),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            SlamTextField(
              controller: _locNameCtrl,
              hint: '手动输入地点名（可选）',
              onChanged: (_) => setState(() {}),
            ),
            if (hasLoc)
              Padding(
                padding: const EdgeInsets.only(left: 2, top: 8),
                child: Row(
                  children: [
                    GestureDetector(
                      onTap: _locating ? null : _onGetLocation,
                      child: Text('重新定位', style: TextStyle(fontSize: 12, color: theme.accent)),
                    ),
                    const SizedBox(width: 14),
                    GestureDetector(
                      onTap: _onClearLocation,
                      child: const Text('清除', style: TextStyle(fontSize: 12, color: S.faint)),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }

  // 时间卡片（对齐 时间段/附带时间 picker）
  Widget _buildTimeCard() {
    final startText = _startAt != null ? _fmtDt(_startAt!) : '';
    final endText = _endAt != null ? _fmtDt(_endAt!) : '';
    return SlamCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _required ? '时间段' : '附带时间',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: S.ink),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      _required ? '必填 · 场地可用的起止时间' : '活动 / 约球时间（可选）',
                      style: const TextStyle(fontSize: 11, color: S.faint),
                    ),
                  ],
                ),
              ),
              if (!_required)
                Switch(
                  value: _timeEnabled,
                  activeColor: slamOf(context).accent,
                  onChanged: _onToggleTime,
                ),
            ],
          ),
          if (_timeEnabled) ...[
            const SizedBox(height: 10),
            _timeBox(
              label: _required ? '开始时间' : '选择时间',
              value: _required && !_timeTouched ? '请选择开始时间' : startText,
              onTap: _pickStart,
            ),
            if (_required) ...[
              const SizedBox(height: 8),
              _timeBox(
                label: '结束时间',
                value: _endTouched ? endText : '请选择结束时间',
                onTap: _pickEnd,
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _timeBox({required String label, required String value, VoidCallback? onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 10),
        decoration: BoxDecoration(
          color: const Color(0xFFF7FAF9),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Text(label, style: const TextStyle(fontSize: 13, color: S.muted)),
            const SizedBox(width: 7),
            Expanded(
              child: Text(
                value,
                textAlign: TextAlign.right,
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF0D3D32)),
              ),
            ),
            const SizedBox(width: 7),
            const Text('›', style: TextStyle(fontSize: 18, height: 1, color: Color(0xFFC0C5CE))),
          ],
        ),
      ),
    );
  }
}

/// 本地图片全屏预览（对齐 wx.previewImage）
class _LocalImagePreview extends StatefulWidget {
  const _LocalImagePreview({required this.paths, this.initial = 0});

  final List<String> paths;
  final int initial;

  @override
  State<_LocalImagePreview> createState() => _LocalImagePreviewState();
}

class _LocalImagePreviewState extends State<_LocalImagePreview> {
  late final PageController _ctrl = PageController(initialPage: widget.initial);
  late int _index = widget.initial;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Dialog.fullscreen(
      backgroundColor: Colors.black,
      child: Stack(
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: PageView.builder(
              controller: _ctrl,
              itemCount: widget.paths.length,
              onPageChanged: (i) => setState(() => _index = i),
              itemBuilder: (_, i) => InteractiveViewer(
                maxScale: 4,
                child: Center(child: Image.file(File(widget.paths[i]), fit: BoxFit.contain)),
              ),
            ),
          ),
          if (widget.paths.length > 1)
            Positioned(
              left: 0,
              right: 0,
              bottom: 24,
              child: Center(
                child: Text(
                  '${_index + 1}/${widget.paths.length}',
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                ),
              ),
            ),
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            right: 12,
            child: IconButton(
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(Icons.close, color: Colors.white, size: 26),
            ),
          ),
        ],
      ),
    );
  }
}
