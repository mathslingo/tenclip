import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/auth_api.dart';
import '../core/api_client.dart';
import '../state/app_state.dart';
import '../theme/slam_theme.dart';
import '../widgets/common.dart';

/// 登录页（对齐 miniprogram pages/login）
///
/// iOS 端去掉「微信一键登录」，保留：
/// - 昵称 + 6 位数字密码 注册 / 登录（guest_register / guest_login）
/// - 「先逛逛（无账号）」游客浏览（AppState.enterGuest）
/// - 协议勾选（《隐私政策》/《用户协议》）
/// - 昵称可用性检查（AuthApi.checkNickname）
class LoginPage extends StatefulWidget {
  const LoginPage({super.key, this.from = ''});

  /// 来源标记（对齐 query.from）；非空时登录成功 pop(context, true)
  final String from;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  String _mode = 'register'; // register | login（小程序 wechat 模式在 iOS 下线）
  bool _loading = false;
  bool _agreed = false;
  String _nickHint = '';
  bool _nickOk = false;

  final _nickCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _pwd2Ctrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    // 已登录时打开登录页无需停留（对齐 onLoad 的 isLoggedIn 分支）
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (context.read<AppState>().isLoggedIn) _leave(ok: true);
    });
  }

  @override
  void dispose() {
    _nickCtrl.dispose();
    _pwdCtrl.dispose();
    _pwd2Ctrl.dispose();
    super.dispose();
  }

  AppState get _app => context.read<AppState>();

  /// 离开登录页（对齐 _leaveToBrowse / _afterLogin 的返回语义）
  void _leave({bool ok = false}) {
    final nav = Navigator.of(context);
    if (!nav.canPop()) return;
    if (widget.from.isNotEmpty) {
      nav.pop(ok ? true : null);
    } else {
      nav.pop();
    }
  }

  void _switchMode(String mode) {
    if (_mode == mode) return;
    setState(() {
      _mode = mode;
      _nickHint = '';
      _nickOk = false;
    });
  }

  /// 昵称失焦检查（对齐 onBlurGuestNick，仅注册模式）
  Future<void> _checkNickname() async {
    if (_mode != 'register') return;
    final nick = _nickCtrl.text.trim();
    if (nick.isEmpty) return;
    if (nick.length < 2) {
      setState(() {
        _nickHint = '昵称至少 2 个字符';
        _nickOk = false;
      });
      return;
    }
    try {
      final available = await context.read<AuthApi>().checkNickname(nick);
      if (!mounted) return;
      setState(() {
        _nickHint = available ? '昵称可用' : '昵称已被占用';
        _nickOk = available;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _nickHint = '';
        _nickOk = false;
      });
    }
  }

  bool _checkAgreement() {
    if (_agreed) return true;
    showToast(context, '请先阅读并同意《隐私政策》和《用户协议》');
    return false;
  }

  String _errMsg(Object e, String fallback) => e is ApiException ? e.message : fallback;

  Future<void> _onRegister() async {
    if (_loading) return;
    final nick = _nickCtrl.text.trim();
    final pwd = _pwdCtrl.text.trim();
    final pwd2 = _pwd2Ctrl.text.trim();
    if (nick.length < 2) {
      showToast(context, '请填写昵称（至少2字）');
      return;
    }
    if (!RegExp(r'^\d{6}$').hasMatch(pwd)) {
      showToast(context, '密码须为6位数字');
      return;
    }
    if (pwd != pwd2) {
      showToast(context, '两次密码不一致');
      return;
    }
    if (!_checkAgreement()) return;
    setState(() => _loading = true);
    try {
      await _app.register(nick, pwd);
      if (!mounted) return;
      _leave(ok: true);
    } catch (e) {
      if (!mounted) return;
      showToast(context, _errMsg(e, '注册失败'));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _onLogin() async {
    if (_loading) return;
    final nick = _nickCtrl.text.trim();
    final pwd = _pwdCtrl.text.trim();
    if (nick.isEmpty) {
      showToast(context, '请填写昵称');
      return;
    }
    if (!RegExp(r'^\d{6}$').hasMatch(pwd)) {
      showToast(context, '密码须为6位数字');
      return;
    }
    if (!_checkAgreement()) return;
    setState(() => _loading = true);
    try {
      await _app.login(nick, pwd);
      if (!mounted) return;
      _leave(ok: true);
    } catch (e) {
      if (!mounted) return;
      showToast(context, _errMsg(e, '登录失败'));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// 先逛逛：游客浏览模式（对齐 onGuestEnter）
  void _onGuestEnter() {
    _app.enterGuest();
    _leave();
  }

  @override
  Widget build(BuildContext context) {
    final theme = context.watch<SlamController>().theme;
    final isRegister = _mode == 'register';
    return Scaffold(
      appBar: themedAppBar(context, title: '登录'),
      body: ThemedPage(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 24, 24, 30),
            children: [
              // ── 品牌 ──
              const Text('🎾', textAlign: TextAlign.center, style: TextStyle(fontSize: 50)),
              const SizedBox(height: 10),
              Text(
                'UChance',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: theme.ink, letterSpacing: 2),
              ),
              const SizedBox(height: 7),
              Text('网球 · 剪辑 · AI 教练 · 找球场',
                  textAlign: TextAlign.center, style: TextStyle(fontSize: 13, color: theme.muted)),
              const SizedBox(height: 28),

              // ── 模式切换（iOS 去掉微信登录 tab）──
              Row(
                children: [
                  _modeTab('register', '游客注册'),
                  const SizedBox(width: 6),
                  _modeTab('login', '游客登录'),
                ],
              ),
              const SizedBox(height: 12),

              // ── 表单卡片 ──
              Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(16, 18, 16, 14),
                decoration: S.card(radius: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isRegister ? '游客注册' : '游客登录',
                      style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32)),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      isRegister ? '设置唯一昵称与 6 位数字密码，获得正式 user_id' : '用昵称和密码回到同一游客身份',
                      style: const TextStyle(fontSize: 12, color: S.faint),
                    ),
                    const SizedBox(height: 12),
                    const _FieldLabel('昵称'),
                    Focus(
                      onFocusChange: (has) {
                        if (!has) _checkNickname();
                      },
                      child: SlamTextField(
                        controller: _nickCtrl,
                        hint: '2–20 个字符，全局唯一',
                        maxLength: 20,
                        onChanged: (_) => setState(() {
                          _nickHint = '';
                          _nickOk = false;
                        }),
                      ),
                    ),
                    if (_nickHint.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          _nickHint,
                          style: TextStyle(fontSize: 11, color: _nickOk ? const Color(0xFF0D6B52) : S.danger),
                        ),
                      ),
                    const SizedBox(height: 12),
                    const _FieldLabel('登录密码'),
                    SlamTextField(
                      controller: _pwdCtrl,
                      hint: '6 位数字',
                      obscure: true,
                      keyboardType: TextInputType.number,
                      maxLength: 6,
                    ),
                    if (isRegister) ...[
                      const SizedBox(height: 12),
                      const _FieldLabel('确认密码'),
                      SlamTextField(
                        controller: _pwd2Ctrl,
                        hint: '再次输入 6 位数字',
                        obscure: true,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                      ),
                    ],
                    const SizedBox(height: 12),
                    _agreementRow(),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // ── 主按钮 ──
              AccentButton(
                label: isRegister ? '注册并登录' : '游客登录',
                loading: _loading,
                onPressed: isRegister ? _onRegister : _onLogin,
              ),
              const SizedBox(height: 10),

              // ── 游客先逛逛 ──
              GestureDetector(
                onTap: _onGuestEnter,
                child: Container(
                  height: 44,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: S.cardBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFD5DDE5)),
                  ),
                  child: const Text('先逛逛（无账号）',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: S.sub)),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '先逛逛仅可浏览；发笔记、关注、编辑资料请注册/登录',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 11, color: S.faint, height: 1.4),
              ),

              const SizedBox(height: 18),
              Center(
                child: GestureDetector(
                  onTap: () => _leave(),
                  child: const Text(
                    '返回上一页',
                    style: TextStyle(fontSize: 12, color: S.faint, decoration: TextDecoration.underline),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _modeTab(String mode, String label) {
    final on = _mode == mode;
    return Expanded(
      child: GestureDetector(
        onTap: () => _switchMode(mode),
        child: Container(
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: on ? S.cardBg : Colors.black.withValues(alpha: 0.32),
            borderRadius: BorderRadius.circular(8),
            boxShadow: on
                ? const [BoxShadow(color: Color(0x0F000000), blurRadius: 5, offset: Offset(0, 1))]
                : null,
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: on ? const Color(0xFF0D3D32) : slamOf(context).ink,
            ),
          ),
        ),
      ),
    );
  }

  /// 协议勾选行（隐私政策 / 用户协议入口）
  Widget _agreementRow() {
    const linkStyle = TextStyle(fontSize: 11, color: Color(0xFF0D6B52), fontWeight: FontWeight.w600);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GestureDetector(
          onTap: () => setState(() => _agreed = !_agreed),
          child: Container(
            width: 16,
            height: 16,
            margin: const EdgeInsets.only(top: 1),
            decoration: BoxDecoration(
              color: _agreed ? S.green : S.cardBg,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: _agreed ? S.green : S.border),
            ),
            child: _agreed ? const Icon(Icons.check, size: 12, color: Colors.white) : null,
          ),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: Wrap(
            children: [
              const Text('我已阅读并同意', style: TextStyle(fontSize: 11, color: S.muted)),
              GestureDetector(
                onTap: () => Navigator.pushNamed(context, '/legal-privacy'),
                child: const Text('《隐私政策》', style: linkStyle),
              ),
              const Text('和', style: TextStyle(fontSize: 11, color: S.muted)),
              GestureDetector(
                onTap: () => Navigator.pushNamed(context, '/legal-terms'),
                child: const Text('《用户协议》', style: linkStyle),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _FieldLabel extends StatelessWidget {
  const _FieldLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Text(text, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: S.sub)),
    );
  }
}
