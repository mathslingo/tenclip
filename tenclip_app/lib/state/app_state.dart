import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import '../api/auth_api.dart';
import '../api/social_api.dart';
import '../core/session.dart';

/// 全局状态：登录会话 + 我的资料 + 未读消息数 + 定位
class AppState extends ChangeNotifier {
  AppState(this._session, this._authApi, this._socialApi);

  final Session _session;
  final AuthApi _authApi;
  final SocialApi _socialApi;

  int _unreadCount = 0;
  int get unreadCount => _unreadCount;

  bool get isLoggedIn => _session.isLoggedIn;
  bool get isGuest => _session.isGuest;
  String get userId => _session.userId;

  Map<String, dynamic> get meProfile => _session.meProfile;

  List<String> get likedIds => _session.likedIds;
  List<String> get bookmarkedIds => _session.bookmarkedIds;
  bool isLiked(String id) => _session.isLiked(id);
  bool isBookmarked(String id) => _session.isBookmarked(id);

  bool toggleLike(String id) {
    final on = _session.toggleLike(id);
    notifyListeners();
    return on;
  }

  bool toggleBookmark(String id) {
    final on = _session.toggleBookmark(id);
    notifyListeners();
    return on;
  }

  Map<String, int> statsFromLists() => _session.statsFromLists();

  void saveMeProfile(Map<String, dynamic> patch) {
    _session.saveMeProfile(patch);
    notifyListeners();
  }

  void notifyProfileChanged() => notifyListeners();

  // ── 未读消息 ──

  Future<void> refreshUnread() async {
    try {
      _unreadCount = await _socialApi.fetchUnreadCount();
    } catch (_) {
      _unreadCount = 0;
    }
    notifyListeners();
  }

  void clearUnread() {
    _unreadCount = 0;
    notifyListeners();
  }

  // ── 登录 / 登出 ──

  Future<void> login(String nickname, String password) async {
    await _authApi.loginGuest(nickname, password);
    notifyListeners();
  }

  Future<void> register(String nickname, String password) async {
    await _authApi.registerGuest(nickname, password);
    notifyListeners();
  }

  Future<void> logout() async {
    await _authApi.logout();
    notifyListeners();
  }

  void enterGuest() {
    _session.enterGuest();
    notifyListeners();
  }

  // ── 定位（对齐 getFuzzyLocation；iOS 无模糊定位概念，用低精度）──

  Future<({double lat, double lng})?> getDeviceLocation() async {
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.denied ||
          perm == LocationPermission.deniedForever) {
        return null;
      }
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.low,
          timeLimit: Duration(seconds: 8),
        ),
      );
      return (lat: pos.latitude, lng: pos.longitude);
    } catch (_) {
      return null;
    }
  }
}
