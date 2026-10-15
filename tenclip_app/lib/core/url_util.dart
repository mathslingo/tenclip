import '../config.dart';

/// 相对路径 → 绝对 URL（对齐 social_api.js absUrl）
String absUrl(String path) {
  var p = path.trim();
  if (p.isEmpty) return '';
  if (RegExp(r'^https?://', caseSensitive: false).hasMatch(p)) return p;
  if (p.startsWith('//')) return 'https:$p';
  final base = apiBaseUrl.replaceAll(RegExp(r'/$'), '');
  if (!p.startsWith('/')) p = '/$p';
  return '$base$p';
}

/// 可跨端展示的头像；本地临时路径返回空，需先上传（对齐 usableAvatarUrl）
String usableAvatarUrl(String path) {
  final p = path.trim();
  if (p.isEmpty) return '';
  if (RegExp(r'^(wxfile|file)://', caseSensitive: false).hasMatch(p)) return '';
  if (RegExp(r'^https?://tmp/', caseSensitive: false).hasMatch(p)) return '';
  if (RegExp(r'^https?://', caseSensitive: false).hasMatch(p)) return p;
  if (p.startsWith('/')) return absUrl(p);
  return '';
}

/// 头像是否需要先上传（对齐 needsAvatarUpload）
bool needsAvatarUpload(String path) {
  final p = path.trim();
  if (p.isEmpty) return false;
  if (RegExp(r'^(wxfile|file)://', caseSensitive: false).hasMatch(p)) return true;
  if (RegExp(r'^https?://tmp/', caseSensitive: false).hasMatch(p)) return true;
  if (RegExp(r'^https?://', caseSensitive: false).hasMatch(p)) return false;
  if (p.startsWith('/static/')) return false;
  return true;
}
