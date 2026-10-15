import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// 本地存储封装（对齐小程序 wx.getStorageSync / setStorageSync）。
///
/// App 启动时 `await Storage.init()`，之后全部同步读取。
class Storage {
  Storage._(this._prefs);

  static Storage? _instance;
  final SharedPreferences _prefs;

  static Future<Storage> init() async {
    if (_instance != null) return _instance!;
    final prefs = await SharedPreferences.getInstance();
    _instance = Storage._(prefs);
    return _instance!;
  }

  static Storage get I {
    final inst = _instance;
    assert(inst != null, 'Storage.init() 必须在 runApp 前调用');
    return inst!;
  }

  String getString(String key, [String fallback = '']) {
    final v = _prefs.get(key);
    if (v == null) return fallback;
    if (v is String) return v;
    return jsonEncode(v);
  }

  bool getBool(String key, [bool fallback = false]) {
    final v = _prefs.get(key);
    if (v is bool) return v;
    if (v is String) return v == '1' || v == 'true';
    return fallback;
  }

  int getInt(String key, [int fallback = 0]) {
    final v = _prefs.get(key);
    if (v is int) return v;
    if (v is String) return int.tryParse(v) ?? fallback;
    return fallback;
  }

  /// 读取 JSON（Map / List），失败返回 fallback
  dynamic getJson(String key, [dynamic fallback]) {
    final raw = _prefs.get(key);
    if (raw == null) return fallback;
    if (raw is String) {
      if (raw.isEmpty) return fallback;
      try {
        return jsonDecode(raw);
      } catch (_) {
        return fallback;
      }
    }
    return raw;
  }

  Map<String, dynamic> getMap(String key) {
    final v = getJson(key);
    if (v is Map) return Map<String, dynamic>.from(v);
    return <String, dynamic>{};
  }

  List<dynamic> getList(String key) {
    final v = getJson(key);
    if (v is List) return List<dynamic>.from(v);
    return <dynamic>[];
  }

  void setString(String key, String value) {
    _prefs.setString(key, value);
  }

  void setBool(String key, bool value) {
    _prefs.setBool(key, value);
  }

  void setInt(String key, int value) {
    _prefs.setInt(key, value);
  }

  /// 与小程序一致：对象/数组以 JSON 字符串存储
  void setJson(String key, dynamic value) {
    _prefs.setString(key, jsonEncode(value));
  }

  void remove(String key) {
    _prefs.remove(key);
  }
}
