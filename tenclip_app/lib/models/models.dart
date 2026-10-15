/// 数据模型（对齐 miniprogram utils 各 normalize 函数的输出结构）
library;

// ── Feed / 笔记 ──

class FeedItem {
  FeedItem({
    required this.id,
    this.title = '',
    this.summary = '',
    this.cover = '',
    this.coverRatio = 1.0,
    this.coverFailed = false,
    this.coverIsMock = false,
    this.authorName = '',
    this.authorInitial = 'U',
    this.authorAvatar = '',
    this.likeCount = 0,
    this.tags = const [],
    this.channel = '推荐',
    this.mediaType = 'image',
    this.url = '',
    this.publishedAt = '',
    this.kind = 'news',
    this.userId = '',
    this.images = const [],
    this.body = '',
    this.score = 0,
    this.distanceM,
    this.distanceBadge = '',
    this.tourBadge = '',
    this.isLocalNote = false,
    this.locationName = '',
    this.locationAddress = '',
    this.latitude,
    this.longitude,
    this.createdAt = 0,
    this.commentCount = 0,
  });

  final String id;
  String title;
  String summary;
  String cover;
  double coverRatio;
  bool coverFailed;
  bool coverIsMock;
  String authorName;
  String authorInitial;
  String authorAvatar;
  int likeCount;
  List<String> tags;
  String channel;
  String mediaType;
  String url;
  String publishedAt;
  String kind; // 'news' | 'note'
  String userId;
  List<String> images;
  String body;
  double score;
  double? distanceM;
  String distanceBadge;
  String tourBadge;
  bool isLocalNote;
  String locationName;
  String locationAddress;
  double? latitude;
  double? longitude;
  int createdAt;
  int commentCount;

  bool get isNote => kind == 'note' || id.startsWith('note-');
}

class FeedPage {
  const FeedPage({
    required this.items,
    required this.offset,
    required this.nextOffset,
    required this.reachedEnd,
    required this.total,
    required this.source,
  });

  final List<FeedItem> items;
  final int offset;
  final int nextOffset;
  final bool reachedEnd;
  final int total;

  /// api / api-empty / mock / mock-fallback / nearby / nearby-denied / nearby-empty / nearby-noloc / nearby-error
  final String source;
}

// ── 球场 ──

class BookingOption {
  const BookingOption({
    required this.name,
    required this.type,
    this.appId = '',
    this.phone = '',
    this.path = '',
    this.shortLink = '',
  });

  final String name;
  final String type; // miniprogram | phone
  final String appId;
  final String phone;
  final String path;
  final String shortLink;

  factory BookingOption.fromJson(Map<String, dynamic> j) => BookingOption(
        name: j['name']?.toString() ?? '',
        type: j['type']?.toString() ?? '',
        appId: j['appId']?.toString() ?? j['app_id']?.toString() ?? '',
        phone: j['phone']?.toString() ?? '',
        path: j['path']?.toString() ?? '',
        shortLink: j['shortLink']?.toString() ?? '',
      );
}

class ExtSource {
  const ExtSource({required this.name, this.icon = '', this.keyword = ''});

  final String name;
  final String icon;
  final String keyword;

  factory ExtSource.fromJson(Map<String, dynamic> j) => ExtSource(
        name: j['name']?.toString() ?? '',
        icon: j['icon']?.toString() ?? '',
        keyword: j['keyword']?.toString() ?? '',
      );
}

class Court {
  Court({
    required this.id,
    this.name = '',
    this.lat = 0,
    this.lng = 0,
    this.address = '',
    this.distance = 0,
    this.distanceText = '',
    this.rating = -1,
    this.ratingStars = const [],
    this.priceRange = '',
    this.indoorCourts = -1,
    this.outdoorCourts = -1,
    this.totalCourts = -1,
    this.courtType = '',
    this.facilities = const [],
    this.photos = const [],
    this.cover = '',
    this.coverFailed = false,
    this.phone = '',
    this.hours = '',
    this.bookingOptions = const [],
    this.extSources = const [],
  });

  final String id;
  String name;
  double lat;
  double lng;
  String address;
  double distance;
  String distanceText;
  double rating;
  List<String> ratingStars; // full / half / empty ×5
  String priceRange;
  int indoorCourts;
  int outdoorCourts;
  int totalCourts;
  String courtType;
  List<String> facilities;
  List<String> photos;
  String cover;
  bool coverFailed;
  String phone;
  String hours;
  List<BookingOption> bookingOptions;
  List<ExtSource> extSources;
}

class CourtSearchResult {
  const CourtSearchResult({
    required this.courts,
    required this.total,
    required this.source,
  });

  final List<Court> courts;
  final int total;
  final String source; // courts.db / mock / mock-fallback
}

// ── 社交 ──

class SocialUser {
  SocialUser({
    required this.userId,
    this.nickname = '网球爱好者',
    this.avatarUrl = '',
    this.bio = '',
    this.following = 0,
    this.followers = 0,
    this.isFollowing = false,
    this.notesCount = 0,
    this.tags = const [],
    this.tennisLevel = '',
  });

  final String userId;
  String nickname;
  String avatarUrl;
  String bio;
  int following;
  int followers;
  bool isFollowing;
  int notesCount;
  List<String> tags;
  String tennisLevel;

  String get initial => nickname.isNotEmpty ? nickname[0] : '球';

  factory SocialUser.fromJson(Map<String, dynamic> j) => SocialUser(
        userId: j['user_id']?.toString() ?? j['id']?.toString() ?? '',
        nickname: j['nickname']?.toString() ?? j['author_name']?.toString() ?? '网球爱好者',
        avatarUrl: j['avatar_url']?.toString() ?? '',
        bio: j['bio']?.toString() ?? '',
        following: (j['following'] as num?)?.toInt() ?? 0,
        followers: (j['followers'] as num?)?.toInt() ?? 0,
        isFollowing: j['is_following'] == true || j['isFollowing'] == true,
        notesCount: (j['notes_count'] as num?)?.toInt() ?? 0,
        tags: (j['tags'] is List)
            ? (j['tags'] as List).map((e) => e.toString()).toList()
            : const [],
        tennisLevel: j['tennis_level']?.toString() ?? '',
      );
}

class NoteComment {
  NoteComment({
    required this.id,
    this.authorId = '',
    this.authorName = '球友',
    this.authorAvatar = '',
    this.body = '',
    this.createdAt = 0,
    this.parentId = '',
    this.timeText = '',
    List<NoteComment>? replies,
  }) : replies = replies ?? [];

  final String id;
  String authorId;
  String authorName;
  String authorAvatar;
  String body;
  int createdAt;
  String parentId;
  String timeText;
  final List<NoteComment> replies;

  String get initial => authorName.isNotEmpty ? authorName[0] : '球';
}

class AppNotification {
  AppNotification({
    required this.id,
    this.type = '',
    this.actorId = '',
    this.actorName = '球友',
    this.actorAvatar = '',
    this.noteId = '',
    this.noteTitle = '',
    this.body = '',
    this.createdAt = 0,
    this.read = false,
  });

  final String id;
  String type; // like / comment / follow / system
  String actorId;
  String actorName;
  String actorAvatar;
  String noteId;
  String noteTitle;
  String body;
  int createdAt;
  bool read;
}

class PublishLimits {
  const PublishLimits({
    this.maxImages = 10,
    this.maxNotesPerDay = 10,
    this.notesToday,
    this.notesRemainingToday,
    this.imageHint = '最多 10 张',
    this.dayHint = '每日最多 10 篇',
  });

  final int maxImages;
  final int maxNotesPerDay;
  final int? notesToday;
  final int? notesRemainingToday;
  final String imageHint;
  final String dayHint;
}

// ── 视频任务（击球剪辑 / 动作分析）──

class TaskStatus {
  TaskStatus({
    required this.taskId,
    required this.status,
    this.progressFrac = 0,
    this.progressMessage = '',
    this.queueSize = 0,
    this.error,
    this.summary,
    this.guidance,
    this.downloadUrl,
    this.pollRetry = false,
  });

  final String taskId;
  final String status; // queued | running | succeeded | failed
  final double progressFrac;
  final String progressMessage;
  final int queueSize;
  final String? error;
  final String? summary;
  final String? guidance;
  final String? downloadUrl;
  final bool pollRetry;

  bool get isDone => status == 'succeeded' || status == 'failed';
  bool get succeeded => status == 'succeeded';

  factory TaskStatus.fromJson(Map<String, dynamic> json, {String? taskId, String? apiBase}) {
    final id = taskId ?? json['task_id']?.toString() ?? '';
    String? guidance;
    final result = json['result'];
    if (result is Map) {
      guidance = result['guidance']?.toString() ??
          result['markdown']?.toString() ??
          result['text']?.toString();
    } else if (result is String) {
      guidance = result;
    }
    guidance ??= json['guidance']?.toString() ?? json['result_text']?.toString();

    String? download = json['download_url']?.toString();
    if (download != null && download.startsWith('/') && apiBase != null) {
      download = '$apiBase$download';
    }

    return TaskStatus(
      taskId: id,
      status: json['status']?.toString() ?? 'unknown',
      progressFrac: (json['progress_frac'] as num?)?.toDouble() ?? 0,
      progressMessage: json['progress_message']?.toString() ?? '',
      queueSize: (json['queue_size'] as num?)?.toInt() ?? 0,
      error: json['error']?.toString() ?? json['error_message']?.toString(),
      summary: json['summary']?.toString(),
      guidance: guidance,
      downloadUrl: download,
    );
  }
}

/// 选中的视频文件（对齐 chooseTennisVideo 返回）
class PickedVideo {
  const PickedVideo({
    required this.filePath,
    this.size = 0,
    this.durationSec = 0,
  });

  final String filePath;
  final int size;
  final double durationSec;
}
