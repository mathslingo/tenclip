import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../api/auth_api.dart';
import '../api/social_api.dart';
import '../core/api_client.dart';
import '../core/url_util.dart';
import '../main.dart' show requireLogin;
import '../state/app_state.dart';
import '../widgets/common.dart';

/// 编辑资料（对齐 miniprogram pages/profile-edit）
///
/// 昵称 / 头像 / 简介 / 标签 / 性别以外字段 + 网球水平（持拍手、NTRP、
/// Tennis123、打法风格、场地偏好、发球/正手/反手分级）。
/// 头像走相册选择，本地图先上传 /api/social/uploads 再保存。
const _handOpts = ['右手', '左手', '双手'];
const _styleOpts = ['底线型', '发球上网', '全能型', '防守反击', '力量型'];
const _surfaceOpts = ['硬地', '红土', '草地', '室内'];
const _ntrpOpts = ['1.0', '1.5', '2.0', '2.5', '3.0', '3.5', '4.0', '4.5', '5.0', '5.0+'];
const _skillOpts = ['入门', '初级', '中级', '进阶', '高级'];
const _oldLevelToNtrp = {'入门': '1.5', '初级': '2.0', '进阶': '2.5', '中级': '3.0', '高级': '3.5', '竞赛': '4.0'};

int _indexOfOr(List<String> list, String value, int fallback) {
  final i = list.indexOf(value);
  return i >= 0 ? i : fallback;
}

/// 对齐 normalizeNtrp：旧中文等级映射 + 数字解析，默认 2.0
String _normalizeNtrp(String raw) {
  final v = raw.trim();
  if (v.isEmpty) return _ntrpOpts[2];
  if (_ntrpOpts.contains(v)) return v;
  final mapped = _oldLevelToNtrp[v];
  if (mapped != null) return mapped;
  final m = RegExp(r'(\d+(?:\.\d+)?)\+?').firstMatch(v);
  if (m != null) {
    final n = double.tryParse(m.group(1)!) ?? 0;
    if (n >= 5) return '5.0+';
    final key = n.toStringAsFixed(1);
    if (_ntrpOpts.contains(key)) return key;
  }
  return _ntrpOpts[2];
}

/// 对齐 normalizeSkill：默认「入门」
String _normalizeSkill(String raw) {
  final v = raw.trim();
  if (_skillOpts.contains(v)) return v;
  if (v == '竞赛') return '高级';
  return _skillOpts[0];
}

class ProfileEditPage extends StatefulWidget {
  const ProfileEditPage({super.key});

  @override
  State<ProfileEditPage> createState() => _ProfileEditPageState();
}

class _ProfileEditPageState extends State<ProfileEditPage> {
  final _nickCtrl = TextEditingController();
  final _bioCtrl = TextEditingController();
  final _tagsCtrl = TextEditingController();

  String _avatarUrl = ''; // 远端 url 或本地文件路径（保存时按需上传）
  String _nickHint = '';
  bool _saving = false;
  bool _touched = false; // 用户已改动后不再被 fetchMe 覆盖

  int _handIndex = 0;
  int _ntrpIndex = 2;
  int _t123Index = 2;
  int _styleIndex = 0;
  int _surfaceIndex = 0;
  int _serveIndex = 0;
  int _foreIndex = 0;
  int _backIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _init());
  }

  @override
  void dispose() {
    _nickCtrl.dispose();
    _bioCtrl.dispose();
    _tagsCtrl.dispose();
    super.dispose();
  }

  Future<void> _init() async {
    if (!mounted) return;
    _applyForm(null); // 先用本地资料填充（对齐 _applyForm 的 getProfile 回退）
    if (!context.read<AppState>().isLoggedIn) {
      requireLogin(context, from: 'profile-edit');
    }
    try {
      final u = await context.read<AuthApi>().fetchMe();
      if (!mounted || _touched) return;
      _applyForm(u);
    } catch (_) {}
  }

  String _serverOr(Map<String, dynamic>? u, String key, String local) {
    final v = u?[key]?.toString() ?? '';
    return v.isNotEmpty ? v : local;
  }

  /// 对齐 _applyForm：服务端优先、本地 meProfile 兜底，并做归一化
  void _applyForm(Map<String, dynamic>? u) {
    final p = context.read<AppState>().meProfile;
    String pv(String key) => p[key]?.toString() ?? '';

    final nick = _serverOr(u, 'nickname', pv('nickname'));
    final bio = (u != null && u['bio'] != null) ? u['bio'].toString() : pv('bio');
    final tags = (u != null && u['tags'] is List)
        ? (u['tags'] as List).map((e) => e.toString()).toList()
        : ((p['tags'] as List?) ?? const []).map((e) => e.toString()).toList();
    final avatar = usableAvatarUrl(_serverOr(u, 'avatar_url', pv('avatarUrl')));
    final handRaw = _serverOr(u, 'tennis_hand', pv('tennisHand'));
    final hand = handRaw.isEmpty ? _handOpts[0] : handRaw;
    final level = _normalizeNtrp(_serverOr(u, 'tennis_level', pv('tennisLevel')));
    final t123 = _normalizeNtrp(_serverOr(u, 'tennis_123_level', pv('tennis123Level')));
    final styleRaw = _serverOr(u, 'tennis_style', pv('tennisStyle'));
    final style = styleRaw.isEmpty ? _styleOpts[0] : styleRaw;
    final surfaceRaw = _serverOr(u, 'preferred_surface', pv('preferredSurface'));
    final surface = surfaceRaw.isEmpty ? _surfaceOpts[0] : surfaceRaw;
    final serve = _normalizeSkill(_serverOr(u, 'tennis_serve_level', pv('tennisServeLevel')));
    final fore = _normalizeSkill(_serverOr(u, 'tennis_forehand_level', pv('tennisForehandLevel')));
    final back = _normalizeSkill(_serverOr(u, 'tennis_backhand_level', pv('tennisBackhandLevel')));

    setState(() {
      _nickCtrl.text = nick;
      _bioCtrl.text = bio;
      _tagsCtrl.text = tags.join(',');
      _avatarUrl = avatar;
      _handIndex = _indexOfOr(_handOpts, hand, 0);
      _ntrpIndex = _indexOfOr(_ntrpOpts, level, 2);
      _t123Index = _indexOfOr(_ntrpOpts, t123, 2);
      _styleIndex = _indexOfOr(_styleOpts, style, 0);
      _surfaceIndex = _indexOfOr(_surfaceOpts, surface, 0);
      _serveIndex = _indexOfOr(_skillOpts, serve, 0);
      _foreIndex = _indexOfOr(_skillOpts, fore, 0);
      _backIndex = _indexOfOr(_skillOpts, back, 0);
    });
  }

  // ── 头像 ──

  Future<void> _pickAvatar() async {
    try {
      final x = await ImagePicker().pickImage(
        source: ImageSource.gallery,
        maxWidth: 512,
        imageQuality: 85,
      );
      if (x != null && mounted) {
        setState(() {
          _avatarUrl = x.path;
          _touched = true;
        });
      }
    } catch (_) {
      if (mounted) showToast(context, '无法打开相册');
    }
  }

  // ── 昵称检查（对齐 onBlurNick）──

  Future<void> _checkNick() async {
    final nick = _nickCtrl.text.trim();
    if (nick.length < 2) {
      setState(() => _nickHint = '昵称至少 2 个字符');
      return;
    }
    try {
      final available = await context.read<AuthApi>().checkNickname(nick);
      if (!mounted) return;
      setState(() => _nickHint = available ? '昵称可用' : '昵称已被占用');
    } catch (_) {}
  }

  // ── 底部选择器（对齐 picker mode="selector"）──

  Future<void> _showPicker(
    String title,
    List<String> options,
    int index,
    ValueChanged<int> onPick,
  ) async {
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: S.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 340),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  child: Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: S.ink)),
                ),
                const Divider(height: 1, color: S.line),
                Flexible(
                  child: ListView(
                    shrinkWrap: true,
                    children: [
                      for (var i = 0; i < options.length; i++)
                        ListTile(
                          title: Text(
                            options[i],
                            style: TextStyle(
                              fontSize: 15,
                              color: S.ink,
                              fontWeight: i == index ? FontWeight.w700 : FontWeight.w400,
                            ),
                          ),
                          trailing: i == index ? const Icon(Icons.check, size: 18, color: S.green) : null,
                          onTap: () {
                            Navigator.pop(ctx);
                            onPick(i);
                          },
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ── 保存（对齐 onSave：本地 saveProfile → updateAuthProfile，失败回退 upsertMe）──

  Future<void> _onSave() async {
    if (_saving) return;
    final nick = _nickCtrl.text.trim();
    if (nick.length < 2) {
      showToast(context, '请填写有效昵称');
      return;
    }
    final bio = _bioCtrl.text.trim();
    final tags = _tagsCtrl.text
        .split(RegExp(r'[,，\s]+'))
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .take(6)
        .toList();

    final hand = _handOpts[_handIndex];
    final level = _normalizeNtrp(_ntrpOpts[_ntrpIndex]);
    final t123 = _normalizeNtrp(_ntrpOpts[_t123Index]);
    final style = _styleOpts[_styleIndex];
    final surface = _surfaceOpts[_surfaceIndex];
    final serve = _normalizeSkill(_skillOpts[_serveIndex]);
    final fore = _normalizeSkill(_skillOpts[_foreIndex]);
    final back = _normalizeSkill(_skillOpts[_backIndex]);

    setState(() => _saving = true);
    try {
      // 头像：本地图先上传（对齐 needsAvatarUpload → uploadNoteImage）
      String avatar = '';
      final local = _avatarUrl.trim();
      if (local.isEmpty) {
        avatar = '';
      } else if (needsAvatarUpload(local)) {
        final body = await context.read<ApiClient>().uploadMultipart(
              path: '/api/social/uploads',
              filePath: local,
              fieldName: 'file',
              maxAttempts: 2,
            );
        avatar = usableAvatarUrl(body['url']?.toString() ?? '');
        if (avatar.isEmpty) throw ApiException('头像上传失败，请重新选择头像');
      } else {
        avatar = usableAvatarUrl(local);
        if (avatar.isEmpty) throw ApiException('头像无效，请重新选择头像');
      }
      if (!mounted) return;

      context.read<AppState>().saveMeProfile({
        'nickname': nick,
        'bio': bio,
        'tags': tags,
        'avatarUrl': avatar,
        'tennisHand': hand,
        'tennisLevel': level,
        'tennis123Level': t123,
        'tennisStyle': style,
        'preferredSurface': surface,
        'tennisServeLevel': serve,
        'tennisForehandLevel': fore,
        'tennisBackhandLevel': back,
      });
      setState(() => _avatarUrl = avatar);

      try {
        await context.read<AuthApi>().updateProfile(
              nickname: nick,
              avatarUrl: avatar,
              bio: bio,
              tags: tags,
              tennisHand: hand,
              tennisLevel: level,
              tennis123Level: t123,
              tennisStyle: style,
              preferredSurface: surface,
              tennisServeLevel: serve,
              tennisForehandLevel: fore,
              tennisBackhandLevel: back,
            );
      } catch (e) {
        // 昵称冲突类错误直接抛；其余回退 upsertMe（对齐小程序）
        if (e.toString().contains('昵称')) rethrow;
        await context.read<SocialApi>().upsertMe();
      }
      if (!mounted) return;
      showToast(context, '已保存');
      await Future<void>.delayed(const Duration(milliseconds: 400));
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e is ApiException ? e.message : '保存失败');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  // ── UI ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: themedAppBar(context, title: '编辑资料'),
      body: ThemedPage(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 20),
          children: [
            // ── 基础资料 ──
            SlamCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const _FormLabel('头像'),
                      GestureDetector(onTap: _pickAvatar, child: _avatarPreview()),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const _FormLabel('昵称（全局唯一）'),
                  Focus(
                    onFocusChange: (has) {
                      if (!has) _checkNick();
                    },
                    child: SlamTextField(
                      controller: _nickCtrl,
                      hint: '填写昵称',
                      maxLength: 20,
                      onChanged: (_) => setState(() {
                        _nickHint = '';
                        _touched = true;
                      }),
                    ),
                  ),
                  if (_nickHint.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(_nickHint, style: const TextStyle(fontSize: 11, color: S.muted)),
                    ),
                  const SizedBox(height: 16),
                  const _FormLabel('简介'),
                  SlamTextField(
                    controller: _bioCtrl,
                    hint: '介绍一下自己',
                    maxLines: 4,
                    maxLength: 80,
                    onChanged: (_) => _touched = true,
                  ),
                  const SizedBox(height: 16),
                  const _FormLabel('兴趣标签（逗号分隔）'),
                  SlamTextField(
                    controller: _tagsCtrl,
                    hint: '例如：正手，发球，资讯',
                    maxLength: 40,
                    onChanged: (_) => _touched = true,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // ── 网球水平 ──
            SlamCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('网球水平',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32))),
                  const SizedBox(height: 4),
                  const Text('按 NTRP / Tennis123 自评，并补充发正反手能力',
                      style: TextStyle(fontSize: 11, color: Color(0xFF8A93A0), height: 1.4)),
                  const SizedBox(height: 12),
                  const _FormLabel('NTRP 分级'),
                  _pickerRow('NTRP ${_ntrpOpts[_ntrpIndex]}',
                      () => _showPicker('NTRP 分级', _ntrpOpts, _ntrpIndex, (i) => setState(() {
                            _ntrpIndex = i;
                            _touched = true;
                          }))),
                  const SizedBox(height: 16),
                  const _FormLabel('Tennis123 分级'),
                  _pickerRow('Tennis123 ${_ntrpOpts[_t123Index]}',
                      () => _showPicker('Tennis123 分级', _ntrpOpts, _t123Index, (i) => setState(() {
                            _t123Index = i;
                            _touched = true;
                          }))),
                  const SizedBox(height: 16),
                  const _FormLabel('发球水平'),
                  _pickerRow(_skillOpts[_serveIndex],
                      () => _showPicker('发球水平', _skillOpts, _serveIndex, (i) => setState(() {
                            _serveIndex = i;
                            _touched = true;
                          }))),
                  const SizedBox(height: 16),
                  const _FormLabel('正手水平'),
                  _pickerRow(_skillOpts[_foreIndex],
                      () => _showPicker('正手水平', _skillOpts, _foreIndex, (i) => setState(() {
                            _foreIndex = i;
                            _touched = true;
                          }))),
                  const SizedBox(height: 16),
                  const _FormLabel('反手水平'),
                  _pickerRow(_skillOpts[_backIndex],
                      () => _showPicker('反手水平', _skillOpts, _backIndex, (i) => setState(() {
                            _backIndex = i;
                            _touched = true;
                          }))),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // ── 网球风格 ──
            SlamCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('网球风格',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32))),
                  const SizedBox(height: 12),
                  const _FormLabel('持拍手'),
                  _pickerRow(_handOpts[_handIndex],
                      () => _showPicker('持拍手', _handOpts, _handIndex, (i) => setState(() {
                            _handIndex = i;
                            _touched = true;
                          }))),
                  const SizedBox(height: 16),
                  const _FormLabel('打法风格'),
                  _pickerRow(_styleOpts[_styleIndex],
                      () => _showPicker('打法风格', _styleOpts, _styleIndex, (i) => setState(() {
                            _styleIndex = i;
                            _touched = true;
                          }))),
                  const SizedBox(height: 16),
                  const _FormLabel('偏好场地'),
                  _pickerRow(_surfaceOpts[_surfaceIndex],
                      () => _showPicker('偏好场地', _surfaceOpts, _surfaceIndex, (i) => setState(() {
                            _surfaceIndex = i;
                            _touched = true;
                          }))),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // ── 操作按钮 ──
            Row(
              children: [
                Expanded(
                  child: _actionButton('取消', ghost: true, onTap: _saving ? null : () => Navigator.pop(context)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _actionButton(_saving ? '保存中…' : '保存', onTap: _saving ? null : _onSave),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _avatarPreview() {
    Widget child;
    if (_avatarUrl.isNotEmpty && needsAvatarUpload(_avatarUrl)) {
      child = Image.file(
        File(_avatarUrl),
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => _avatarPlaceholder(),
      );
    } else {
      final url = usableAvatarUrl(_avatarUrl);
      if (url.isNotEmpty) {
        child = CachedNetworkImage(
          imageUrl: url,
          fit: BoxFit.cover,
          placeholder: (_, __) => _avatarPlaceholder(),
          errorWidget: (_, __, ___) => _avatarPlaceholder(),
        );
      } else {
        child = _avatarPlaceholder();
      }
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(30),
      child: Container(width: 60, height: 60, color: const Color(0xFFF0FAF6), child: child),
    );
  }

  Widget _avatarPlaceholder() {
    return const Center(
      child: Text('选头像', style: TextStyle(fontSize: 12, color: Color(0xFF0D6B52))),
    );
  }

  Widget _pickerRow(String value, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 44,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          color: const Color(0xFFF5F7F9),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Expanded(child: Text(value, style: const TextStyle(fontSize: 14, color: S.ink))),
            const Icon(Icons.keyboard_arrow_down, size: 18, color: S.faint),
          ],
        ),
      ),
    );
  }

  Widget _actionButton(String label, {bool ghost = false, VoidCallback? onTap}) {
    final theme = slamOf(context);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 44,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: ghost ? const Color(0xFFEEF2F5) : theme.accent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: ghost ? S.sub : theme.accentInk,
          ),
        ),
      ),
    );
  }
}

class _FormLabel extends StatelessWidget {
  const _FormLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(text, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: S.ink)),
    );
  }
}
