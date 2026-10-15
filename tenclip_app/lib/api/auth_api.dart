import '../core/api_client.dart';
import '../core/session.dart';

/// 认证 API（对齐 miniprogram/utils/auth_api.js）
///
/// iOS 端用「昵称 + 密码」账号体系（/api/auth/guest/*），
/// 替代小程序的 wx.login；接口与后端 services/wechat_auth.py 完全一致。
class AuthApi {
  AuthApi(this._client, this._session);

  final ApiClient _client;
  final Session _session;

  bool get isLoggedIn => _session.isLoggedIn;
  bool get isGuest => _session.isGuest;
  String get token => _session.token;

  void enterGuest() => _session.enterGuest();

  /// 注册（昵称 + 密码）
  Future<Map<String, dynamic>> registerGuest(String nickname, String password) async {
    final body = await _client.request(
      '/api/auth/guest/register',
      method: 'POST',
      auth: false,
      data: {
        'nickname': nickname.trim(),
        'password': password.trim(),
        'device_hint': 'ios',
      },
    );
    final map = Map<String, dynamic>.from(body as Map);
    _session.saveSession(map);
    return map;
  }

  /// 登录（昵称 + 密码）
  Future<Map<String, dynamic>> loginGuest(String nickname, String password) async {
    final body = await _client.request(
      '/api/auth/guest/login',
      method: 'POST',
      auth: false,
      data: {
        'nickname': nickname.trim(),
        'password': password.trim(),
        'device_hint': 'ios',
      },
    );
    final map = Map<String, dynamic>.from(body as Map);
    _session.saveSession(map);
    return map;
  }

  /// 昵称是否可用
  Future<bool> checkNickname(String nickname) async {
    final body = await _client.request(
      '/api/auth/nickname/check',
      query: {'nickname': nickname.trim()},
    );
    if (body is Map) {
      return body['available'] == true || body['ok'] == true;
    }
    return false;
  }

  /// 拉取当前用户（对齐 fetchMe）
  Future<Map<String, dynamic>> fetchMe() async {
    final body = await _client.request('/api/auth/me');
    final user = Map<String, dynamic>.from(body as Map);
    _session.applyUserToLocal(user);
    return user;
  }

  Future<void> logout() async {
    if (_session.token.isNotEmpty) {
      try {
        await _client.request('/api/auth/logout', method: 'POST');
      } catch (_) {}
    }
    _session.clearSession();
  }

  /// 更新资料（对齐 updateAuthProfile）
  Future<Map<String, dynamic>> updateProfile({
    String nickname = '',
    String avatarUrl = '',
    String bio = '',
    List<String> tags = const [],
    String location = '',
    String tennisHand = '',
    String tennisLevel = '',
    String tennis123Level = '',
    String tennisStyle = '',
    String preferredSurface = '',
    String tennisServeLevel = '',
    String tennisForehandLevel = '',
    String tennisBackhandLevel = '',
  }) async {
    final body = await _client.request(
      '/api/auth/profile',
      method: 'POST',
      data: {
        'nickname': nickname,
        'avatar_url': avatarUrl,
        'bio': bio,
        'tags': tags,
        'location': location,
        'tennis_hand': tennisHand,
        'tennis_level': tennisLevel,
        'tennis_123_level': tennis123Level,
        'tennis_style': tennisStyle,
        'preferred_surface': preferredSurface,
        'tennis_serve_level': tennisServeLevel,
        'tennis_forehand_level': tennisForehandLevel,
        'tennis_backhand_level': tennisBackhandLevel,
      },
    );
    final user = Map<String, dynamic>.from(body as Map);
    _session.applyUserToLocal(user);
    return user;
  }
}
