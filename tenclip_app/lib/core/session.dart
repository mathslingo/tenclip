import 'storage.dart';

/// 登录会话与本地资料（对齐 miniprogram auth_api.js / user_id.js / me_store.js）
///
/// - token / userId / 用户资料缓存
/// - 游客浏览模式（未登录可浏览，写操作需登录）
/// - 赞过 / 收藏 列表（本地）
class Session {
  Session(this._s);

  final Storage _s;

  static const _tokenKey = 'tenclip_auth_token';
  static const _authDoneKey = 'tenclip_auth_done';
  static const _uidKey = 'tenclip_user_id';
  static const _userKey = 'tenclip_user_profile';
  static const _meProfileKey = 'tenclip_me_profile';
  static const _expiresKey = 'tenclip_auth_expires_at';
  static const _guestKey = 'tenclip_guest_mode';
  static const _likesKey = 'tenclip_me_likes';
  static const _bookmarksKey = 'tenclip_me_bookmarks';

  // ── Token / 登录态 ──

  String get token => _s.getString(_tokenKey);

  bool get isLoggedIn {
    final t = token;
    if (t.isEmpty) return false;
    final exp = _s.getInt(_expiresKey);
    if (exp > 0 && exp * 1000 < DateTime.now().millisecondsSinceEpoch) {
      clearSession();
      return false;
    }
    return true;
  }

  /// 仅浏览、无账号会话
  bool get isGuest {
    if (isLoggedIn) return false;
    return _s.getBool(_guestKey);
  }

  void enterGuest() {
    clearSession();
    _s.remove(_uidKey);
    _s.setBool(_guestKey, true);
  }

  void clearSession() {
    _s.remove(_tokenKey);
    _s.remove(_authDoneKey);
    _s.remove(_expiresKey);
  }

  /// 登录成功后保存（对齐 saveSession）
  void saveSession(Map<String, dynamic> body) {
    final token = body['token']?.toString() ?? '';
    if (token.isEmpty) throw Exception('登录失败：无 token');
    _s.remove(_guestKey);
    _s.setString(_tokenKey, token);
    _s.setBool(_authDoneKey, true);
    final expiresAt = body['expires_at'];
    if (expiresAt is num && expiresAt > 0) {
      _s.setInt(_expiresKey, expiresAt.toInt());
    }
    final user = body['user'];
    if (user is Map) {
      final uid = user['user_id']?.toString() ?? '';
      if (uid.isNotEmpty) _s.setString(_uidKey, uid);
      applyUserToLocal(Map<String, dynamic>.from(user));
    }
  }

  /// 服务端用户对象 → 本地缓存（对齐 applyUserToLocal）
  void applyUserToLocal(Map<String, dynamic> user) {
    final prev = _s.getMap(_userKey);
    _s.setJson(_userKey, {
      ...prev,
      'userId': user['user_id'] ?? prev['userId'],
      'nickName': user['nickname'] ?? prev['nickName'] ?? '网球爱好者',
      'avatarUrl': user['avatar_url'] ?? prev['avatarUrl'] ?? '',
    });
    final me = getMeProfileRaw();
    saveMeProfile({
      'uid': user['user_id'] ?? me['uid'],
      'nickname': user['nickname'] ?? me['nickname'] ?? '网球爱好者',
      'avatarUrl': user['avatar_url'] ?? me['avatarUrl'] ?? '',
      'bio': user['bio'] ?? me['bio'] ?? '',
      'tags': user['tags'] is List ? user['tags'] : me['tags'],
      'tennisHand': user['tennis_hand'] ?? me['tennisHand'] ?? '',
      'tennisLevel': user['tennis_level'] ?? me['tennisLevel'] ?? '',
      'tennis123Level': user['tennis_123_level'] ?? me['tennis123Level'] ?? '',
      'tennisStyle': user['tennis_style'] ?? me['tennisStyle'] ?? '',
      'preferredSurface':
          user['preferred_surface'] ?? me['preferredSurface'] ?? '',
      'tennisServeLevel':
          user['tennis_serve_level'] ?? me['tennisServeLevel'] ?? '',
      'tennisForehandLevel':
          user['tennis_forehand_level'] ?? me['tennisForehandLevel'] ?? '',
      'tennisBackhandLevel':
          user['tennis_backhand_level'] ?? me['tennisBackhandLevel'] ?? '',
      'accountType': user['account_type'] ?? me['accountType'] ?? '',
    });
  }

  // ── 用户 ID（对齐 user_id.js）──

  String get userId {
    final stored = _s.getString(_uidKey);
    if (stored.isNotEmpty) return stored;
    final p = _s.getMap(_userKey);
    final pid = p['userId']?.toString() ?? '';
    if (pid.isNotEmpty) {
      _s.setString(_uidKey, pid);
      return pid;
    }
    final me = _s.getMap(_meProfileKey);
    final mid = me['uid']?.toString() ?? '';
    if (mid.isNotEmpty && mid != '10086') {
      _s.setString(_uidKey, mid);
      return mid;
    }
    return '';
  }

  Map<String, String> get localProfile {
    final me = _s.getMap(_meProfileKey);
    final user = _s.getMap(_userKey);
    return {
      'user_id': userId,
      'nickname':
          me['nickname']?.toString() ?? user['nickName']?.toString() ?? '网球爱好者',
      'avatar_url':
          me['avatarUrl']?.toString() ?? user['avatarUrl']?.toString() ?? '',
      'bio': me['bio']?.toString() ?? '',
    };
  }

  // ── 我的页资料（对齐 me_store.js getProfile/saveProfile）──

  static Map<String, dynamic> defaultProfile() => {
        'nickname': '网球爱好者',
        'uid': '10086',
        'bio': '热爱网球，记录每一次击球与进步 🎾',
        'location': '上海',
        'gender': '♂',
        'tags': <String>['正手', '发球', '资讯'],
        'following': 0,
        'followers': 0,
        'avatarUrl': '',
        'tennisHand': '',
        'tennisLevel': '',
        'tennis123Level': '',
        'tennisStyle': '',
        'preferredSurface': '',
        'tennisServeLevel': '',
        'tennisForehandLevel': '',
        'tennisBackhandLevel': '',
        'accountType': '',
      };

  Map<String, dynamic> getMeProfileRaw() => _s.getMap(_meProfileKey);

  Map<String, dynamic> get meProfile {
    final p = _s.getMap(_meProfileKey);
    final base = defaultProfile();
    if (p.isEmpty) return base;
    return {
      'nickname': p['nickname'] ?? base['nickname'],
      'uid': p['uid'] ?? base['uid'],
      'bio': p['bio'] ?? base['bio'],
      'location': p['location'] ?? base['location'],
      'gender': p['gender'] ?? base['gender'],
      'tags': (p['tags'] is List && (p['tags'] as List).isNotEmpty)
          ? p['tags']
          : base['tags'],
      'following': (p['following'] as num?)?.toInt() ?? 0,
      'followers': (p['followers'] as num?)?.toInt() ?? 0,
      'avatarUrl': p['avatarUrl'] ?? '',
      'tennisHand': p['tennisHand'] ?? '',
      'tennisLevel': p['tennisLevel'] ?? '',
      'tennis123Level': p['tennis123Level'] ?? '',
      'tennisStyle': p['tennisStyle'] ?? '',
      'preferredSurface': p['preferredSurface'] ?? '',
      'tennisServeLevel': p['tennisServeLevel'] ?? '',
      'tennisForehandLevel': p['tennisForehandLevel'] ?? '',
      'tennisBackhandLevel': p['tennisBackhandLevel'] ?? '',
      'accountType': p['accountType'] ?? '',
    };
  }

  Map<String, dynamic> saveMeProfile(Map<String, dynamic> patch) {
    final next = {...meProfile, ...patch};
    var tags = next['tags'];
    if (tags != null && tags is! List) {
      next['tags'] = tags
          .toString()
          .split(RegExp(r'[,，\s]+'))
          .map((t) => t.trim())
          .where((t) => t.isNotEmpty)
          .toList();
    }
    _s.setJson(_meProfileKey, next);
    return next;
  }

  // ── 赞过 / 收藏（本地 ID 列表）──

  List<String> _readIdList(String key) =>
      _s.getList(key).map((e) => e.toString()).where((e) => e.isNotEmpty).toList();

  List<String> get likedIds => _readIdList(_likesKey);
  List<String> get bookmarkedIds => _readIdList(_bookmarksKey);

  bool isLiked(String id) => likedIds.contains(id);
  bool isBookmarked(String id) => bookmarkedIds.contains(id);

  bool toggleLike(String id) {
    final ids = likedIds;
    final on = !ids.contains(id);
    if (on) {
      ids.insert(0, id);
    } else {
      ids.remove(id);
    }
    _s.setJson(_likesKey, ids.toSet().toList());
    return on;
  }

  bool toggleBookmark(String id) {
    final ids = bookmarkedIds;
    final on = !ids.contains(id);
    if (on) {
      ids.insert(0, id);
    } else {
      ids.remove(id);
    }
    _s.setJson(_bookmarksKey, ids.toSet().toList());
    return on;
  }

  /// 统计：关注 / 粉丝 / 赞与收藏
  Map<String, int> statsFromLists() {
    final p = meProfile;
    return {
      'following': (p['following'] as num?)?.toInt() ?? 0,
      'followers': (p['followers'] as num?)?.toInt() ?? 0,
      'likedCollect': likedIds.length + bookmarkedIds.length,
    };
  }
}
