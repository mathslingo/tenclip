import '../core/api_client.dart';
import '../core/session.dart';
import '../core/url_util.dart';
import '../models/models.dart';

/// 社交 API（对齐 miniprogram/utils/social_api.js）
class SocialApi {
  SocialApi(this._client, this._session);

  final ApiClient _client;
  final Session _session;

  String _ensureUserId() {
    if (!_session.isLoggedIn) throw ApiException('请先登录');
    final uid = _session.userId;
    if (uid.isEmpty) throw ApiException('请先登录');
    return uid;
  }

  // ── 用户 ──

  Future<void> upsertMe() async {
    final p = _session.localProfile;
    final uid = _ensureUserId();
    await _client.request(
      '/api/social/users/upsert',
      method: 'POST',
      data: {
        'user_id': uid,
        'nickname': p['nickname']!.isEmpty ? '网球爱好者' : p['nickname'],
        'avatar_url': p['avatar_url'],
        'bio': p['bio'],
      },
    );
  }

  Future<SocialUser> fetchUser(String userId, {String viewerId = ''}) async {
    final body = await _client.request(
      '/api/social/users/${Uri.encodeComponent(userId)}',
      query: viewerId.isEmpty ? null : {'viewer_id': viewerId},
    );
    final user = SocialUser.fromJson(Map<String, dynamic>.from(body as Map));
    user.avatarUrl = usableAvatarUrl(user.avatarUrl);
    return user;
  }

  Future<void> follow(String followeeId) async {
    final uid = _ensureUserId();
    await _client.request(
      '/api/social/follow',
      method: 'POST',
      data: {'follower_id': uid, 'followee_id': followeeId},
    );
  }

  Future<void> unfollow(String followeeId) async {
    final uid = _ensureUserId();
    await _client.request(
      '/api/social/unfollow',
      method: 'POST',
      data: {'follower_id': uid, 'followee_id': followeeId},
    );
  }

  /// kind: 'followers' | 'following'
  Future<List<SocialUser>> fetchFollowList(String userId, String kind) async {
    final path = kind == 'followers' ? 'followers' : 'following';
    final body = await _client.request('/api/social/users/${Uri.encodeComponent(userId)}/$path');
    final items = (body is Map ? body['items'] : null) as List? ?? [];
    return items
        .map((e) => SocialUser.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  // ── 笔记 ──

  /// 上传单张笔记图片，返回 url（对齐 uploadNoteImage）
  Future<String> uploadNoteImage(String filePath, int index, String key) async {
    final body = await _client.uploadMultipart(
      path: '/api/social/uploads',
      filePath: filePath,
      fieldName: 'file',
      formData: {'key': key, 'index': '$index'},
      maxAttempts: 2,
    );
    final url = body['url']?.toString() ?? '';
    if (url.isEmpty) throw ApiException('图片上传失败');
    return url;
  }

  /// 发布笔记（先串行传图再创建，对齐 publishNote）
  Future<Map<String, dynamic>> publishNote({
    String title = '',
    String body = '',
    List<String> imagePaths = const [],
    String locationName = '',
    String locationAddress = '',
    double? latitude,
    double? longitude,
    int? eventAt,
    void Function(int done, int total)? onImageProgress,
  }) async {
    final uid = _ensureUserId();
    final key = 'u${DateTime.now().millisecondsSinceEpoch.toRadixString(36)}';
    final urls = <String>[];
    for (var i = 0; i < imagePaths.length; i++) {
      final url = await uploadNoteImage(imagePaths[i], i, key);
      urls.add(url);
      onImageProgress?.call(i + 1, imagePaths.length);
    }
    final data = <String, dynamic>{
      'user_id': uid,
      'title': title.trim(),
      'body': body.trim(),
      'image_urls': urls,
    };
    if (locationName.isNotEmpty || locationAddress.isNotEmpty) {
      data['location_name'] = locationName;
      data['location_address'] = locationAddress;
      if (latitude != null && longitude != null) {
        data['latitude'] = latitude;
        data['longitude'] = longitude;
      }
    }
    if (eventAt != null && eventAt > 0) data['event_at'] = eventAt;
    final res = await _client.request('/api/social/notes', method: 'POST', data: data);
    return Map<String, dynamic>.from(res as Map);
  }

  Future<List<FeedItem>> listNotes({String userId = ''}) async {
    final body = await _client.request(
      '/api/social/notes',
      query: userId.isEmpty ? null : {'user_id': userId},
    );
    final items = (body is Map ? body['items'] : null) as List? ?? [];
    return items.map((e) => normalizeNote(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<List<FeedItem>> searchNotes(String keyword) async {
    final body = await _client.request(
      '/api/social/notes/search',
      query: {'q': keyword.trim()},
    );
    final items = (body is Map ? body['items'] : null) as List? ?? [];
    return items.map((e) => normalizeNote(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<List<FeedItem>> searchFeed(String keyword) async {
    final body = await _client.request(
      '/api/feed/search',
      query: {'q': keyword.trim()},
    );
    final items = (body is Map ? body['items'] : null) as List? ?? [];
    return items.map((e) => normalizeNote(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<FeedItem?> getNote(String noteId) async {
    final nid = noteId.replaceFirst(RegExp(r'^note-'), '');
    final body = await _client.request('/api/social/notes/${Uri.encodeComponent(nid)}');
    return normalizeNote(Map<String, dynamic>.from(body as Map));
  }

  Future<void> deleteNote(String noteId) async {
    final uid = _ensureUserId();
    final nid = noteId.replaceFirst(RegExp(r'^note-'), '');
    await _client.request(
      '/api/social/notes/${Uri.encodeComponent(nid)}',
      method: 'DELETE',
      query: {'user_id': uid},
    );
  }

  /// 笔记点赞（对齐 toggleNoteLikeRemote），返回服务端最新状态
  Future<Map<String, dynamic>> toggleNoteLikeRemote(String noteId) async {
    final nid = noteId.replaceFirst(RegExp(r'^note-'), '');
    final body = await _client.request(
      '/api/social/notes/${Uri.encodeComponent(nid)}/like',
      method: 'POST',
    );
    return Map<String, dynamic>.from(body as Map? ?? {});
  }

  /// 资讯反馈（对齐 sendNewsFeedback）
  Future<void> sendNewsFeedback(String articleId, String action) async {
    final uid = _session.userId.isEmpty ? 'guest' : _session.userId;
    await _client.postForm('/api/news/feedback', {
      'user_id': uid,
      'article_id': articleId,
      'action': action,
    });
  }

  // ── 评论 ──

  /// 拉取评论列表（平铺），由 nestComments 组装两层
  Future<List<NoteComment>> fetchComments(String noteId) async {
    final nid = noteId.replaceFirst(RegExp(r'^note-'), '');
    final body = await _client.request(
      '/api/social/notes/${Uri.encodeComponent(nid)}/comments',
      query: {'limit': '100'},
    );
    final items = (body is Map ? body['items'] : null) as List? ?? [];
    return items.map((e) {
      final j = Map<String, dynamic>.from(e as Map);
      return NoteComment(
        id: j['id']?.toString() ?? '',
        authorId: j['user_id']?.toString() ?? j['author_id']?.toString() ?? '',
        authorName: j['author_name']?.toString() ?? '球友',
        authorAvatar: usableAvatarUrl(j['author_avatar']?.toString() ?? ''),
        body: j['body']?.toString() ?? j['content']?.toString() ?? '',
        createdAt: (j['created_at'] as num?)?.toInt() ?? 0,
        parentId: j['parent_id']?.toString() ?? '',
      );
    }).toList();
  }

  /// 发表评论（body + 可选 parent_id；用户身份走 Bearer token）
  Future<NoteComment> postComment(String noteId, String body, {String parentId = ''}) async {
    final nid = noteId.replaceFirst(RegExp(r'^note-'), '');
    final res = await _client.request(
      '/api/social/notes/${Uri.encodeComponent(nid)}/comments',
      method: 'POST',
      data: {
        'body': body.trim(),
        if (parentId.isNotEmpty) 'parent_id': parentId,
      },
    );
    final j = Map<String, dynamic>.from(res as Map);
    return NoteComment(
      id: j['id']?.toString() ?? '',
      authorId: _session.userId,
      authorName: j['author_name']?.toString() ?? _session.localProfile['nickname'] ?? '我',
      authorAvatar: usableAvatarUrl(j['author_avatar']?.toString() ?? ''),
      body: j['body']?.toString() ?? body,
      createdAt: (j['created_at'] as num?)?.toInt() ?? 0,
      parentId: j['parent_id']?.toString() ?? parentId,
    );
  }

  Future<void> deleteComment(String noteId, String commentId) async {
    final nid = noteId.replaceFirst(RegExp(r'^note-'), '');
    await _client.request(
      '/api/social/notes/${Uri.encodeComponent(nid)}/comments/${Uri.encodeComponent(commentId)}',
      method: 'DELETE',
    );
  }

  /// 扁平评论 → 根评论 + replies（最多两层，对齐 nestComments）
  static ({List<NoteComment> comments, int total}) nestComments(
    List<NoteComment> items,
    String Function(int createdAt) formatTime,
  ) {
    final map = <String, NoteComment>{};
    final roots = <NoteComment>[];
    for (final c in items) {
      c.timeText = formatTime(c.createdAt);
      map[c.id] = c;
    }
    for (final c in items) {
      if (c.parentId.isNotEmpty && map.containsKey(c.parentId)) {
        map[c.parentId]!.replies.add(c);
      } else {
        roots.add(c);
      }
    }
    roots.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    for (final r in roots) {
      r.replies.sort((a, b) => a.createdAt.compareTo(b.createdAt));
    }
    return (comments: roots, total: items.length);
  }

  // ── 消息 ──

  Future<List<AppNotification>> fetchMessages({int limit = 50, int offset = 0}) async {
    final body = await _client.request(
      '/api/social/notifications',
      query: {'limit': '$limit', 'offset': '$offset'},
    );
    final items = (body is Map ? body['items'] : null) as List? ?? [];
    return items.map((e) {
      final j = Map<String, dynamic>.from(e as Map);
      return AppNotification(
        id: j['id']?.toString() ?? '',
        type: j['type']?.toString() ?? '',
        actorId: j['actor_id']?.toString() ?? '',
        actorName: j['actor_name']?.toString() ?? '球友',
        actorAvatar: usableAvatarUrl(j['actor_avatar']?.toString() ?? ''),
        noteId: j['note_id']?.toString() ?? '',
        noteTitle: j['note_title']?.toString() ?? '',
        body: j['body']?.toString() ?? j['content']?.toString() ?? '',
        createdAt: (j['created_at'] as num?)?.toInt() ?? 0,
        read: j['read'] == true || j['is_read'] == true,
      );
    }).toList();
  }

  Future<int> fetchUnreadCount() async {
    if (!_session.isLoggedIn) return 0;
    try {
      final body = await _client.request('/api/social/notifications/unread-count');
      return (body is Map ? (body['count'] as num?)?.toInt() : null) ?? 0;
    } catch (_) {
      return 0;
    }
  }

  Future<void> markAllMessagesRead() async {
    await _client.request('/api/social/notifications/read-all', method: 'POST');
  }

  // ── 发布限额 ──

  Future<PublishLimits> fetchPublishLimits() async {
    try {
      final body = await _client.request('/api/config/publish-limits');
      final j = Map<String, dynamic>.from(body as Map);
      final limits = Map<String, dynamic>.from(j['limits']?['note'] as Map? ?? {});
      final usage = j['usage'] is Map ? Map<String, dynamic>.from(j['usage'] as Map) : null;
      final maxImages = (limits['max_images_per_note'] as num?)?.toInt() ?? 10;
      final maxPerDay = (limits['max_notes_per_user_per_day'] as num?)?.toInt() ?? 10;
      final remaining = (usage?['notes_remaining_today'] as num?)?.toInt();
      return PublishLimits(
        maxImages: maxImages,
        maxNotesPerDay: maxPerDay,
        notesToday: (usage?['notes_today'] as num?)?.toInt(),
        notesRemainingToday: remaining,
        imageHint: '最多 $maxImages 张',
        dayHint: remaining != null ? '今日还可发 ${remaining < 0 ? 0 : remaining} 篇' : '每日最多 $maxPerDay 篇',
      );
    } catch (_) {
      return const PublishLimits();
    }
  }
}

/// 笔记 normalize（对齐 social_api.js normalizeNote）
FeedItem normalizeNote(Map<String, dynamic> n) {
  final images = ((n['images'] as List?) ?? [])
      .map((e) => absUrl(e.toString()))
      .where((e) => e.isNotEmpty)
      .toList();
  final cover = absUrl(
    n['image_url']?.toString() ?? n['cover']?.toString() ?? (images.isNotEmpty ? images.first : ''),
  );
  final authorName = n['author_name']?.toString() ?? n['source']?.toString() ?? '球友';
  final likeRaw = n['like_count'] ?? n['popularity'] ?? 0;
  return FeedItem(
    id: n['id']?.toString() ?? 'note-${n['note_id']}',
    kind: 'note',
    title: n['title']?.toString() ?? '',
    summary: n['body']?.toString() ?? n['summary']?.toString() ?? '',
    body: n['body']?.toString() ?? '',
    cover: cover,
    images: images,
    coverRatio: (n['cover_ratio'] as num?)?.toDouble() ?? 1.25,
    authorName: authorName,
    authorInitial: authorName.isNotEmpty ? authorName[0] : '球',
    authorAvatar: usableAvatarUrl(n['author_avatar']?.toString() ?? n['avatar_url']?.toString() ?? ''),
    likeCount: (likeRaw as num?)?.round() ?? 0,
    userId: n['user_id']?.toString() ?? '',
    locationName: n['location_name']?.toString() ?? '',
    locationAddress: n['location_address']?.toString() ?? '',
    latitude: (n['latitude'] as num?)?.toDouble(),
    longitude: (n['longitude'] as num?)?.toDouble(),
    createdAt: (n['created_at'] as num?)?.toInt() ?? 0,
    commentCount: (n['comment_count'] as num?)?.toInt() ?? 0,
    publishedAt: n['published_at']?.toString() ?? '',
    channel: n['channel']?.toString() ?? '推荐',
  );
}
