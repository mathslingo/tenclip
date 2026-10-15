import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/court_api.dart';
import '../models/models.dart';
import '../widgets/common.dart';

/// 球场详情（对齐 miniprogram pages/court-detail）
///
/// 与小程序差异（iOS 限制）：
/// - 预约渠道 type=miniprogram（跳其它微信小程序）→ Toast 引导微信内搜索
/// - type=phone → url_launcher 拨号（保留拨打前确认弹窗）
/// - 底部「分享」按钮省略（依赖微信会话分享）；「地图」→ 打开 Apple 地图网页
/// - 大众点评 → 打开点评网页搜索；小红书 → 打开小红书网页搜索
class CourtDetailPage extends StatefulWidget {
  const CourtDetailPage({super.key, required this.courtId});

  final String courtId;

  @override
  State<CourtDetailPage> createState() => _CourtDetailPageState();
}

class _CourtDetailPageState extends State<CourtDetailPage> {
  Court? _court;
  bool _loading = true;
  String _errorText = '';
  int _coverIndex = 0;
  final _pageCtrl = PageController();

  CourtApi get _api => context.read<CourtApi>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _pageCtrl.dispose();
    super.dispose();
  }

  // 对齐 onLoad：先用本地缓存/Mock 快速渲染，再拉详情覆盖
  Future<void> _load() async {
    final id = widget.courtId;
    if (id.isEmpty) {
      setState(() {
        _loading = false;
        _errorText = '缺少球场 ID';
      });
      return;
    }

    final preview = CourtApi.mockCourtById(id);
    if (preview != null && mounted) {
      preview.photos = preview.photos.take(2).toList();
      setState(() {
        _court = preview;
        _loading = false;
      });
    }

    try {
      final court = await _api.fetchCourtDetail(id);
      if (!mounted) return;
      court.photos = court.photos.take(2).toList();
      setState(() {
        _court = court;
        _loading = false;
        _errorText = '';
      });
    } catch (_) {
      if (!mounted) return;
      if (_court == null) {
        setState(() {
          _loading = false;
          _errorText = '加载超时，请返回重试';
        });
      }
    }
  }

  // ── 预约（对齐 _doBooking，iOS 渠道适配）──

  Future<void> _doBooking(BookingOption opt) async {
    if (opt.type == 'phone') {
      final phone = opt.phone.isNotEmpty ? opt.phone : (_court?.phone ?? '');
      if (phone.isEmpty) {
        showToast(context, '暂无电话');
        return;
      }
      // 对齐小程序：拨打前 showModal 确认
      final ok = await showConfirm(
        context,
        title: '电话预约',
        content: '拨打 $phone 预约场地？',
        confirmText: '拨打',
      );
      if (!ok || !mounted) return;
      _launch(Uri.parse('tel:$phone'));
      return;
    }
    if (opt.type == 'miniprogram') {
      // iOS 无法跳其它微信小程序（对齐小程序末尾 showToast 的意图）
      showToast(context, '请在微信中搜索小程序预约');
      return;
    }
    showToast(context, opt.name.isNotEmpty ? '请打开「${opt.name}」预约' : '暂无跳转');
  }

  void _onMainBook() {
    final opts = _court?.bookingOptions ?? const [];
    if (opts.isEmpty) return;
    _doBooking(opts.first);
  }

  // ── 电话 / 地图 / 外部来源 ──

  void _onCall() {
    final phone = _court?.phone ?? '';
    if (phone.isEmpty) {
      showToast(context, '暂无电话');
      return;
    }
    _launch(Uri.parse('tel:$phone'));
  }

  /// 对齐 onNavigate（wx.openLocation）→ Apple 地图
  void _onOpenMap() {
    final court = _court;
    if (court == null) return;
    final q = Uri.encodeComponent(court.name);
    _launch(Uri.parse('https://maps.apple.com/?q=$q&ll=${court.lat},${court.lng}'));
  }

  /// 对齐 onExtSource + court_data.getExtSourceJump
  void _onExtSource(ExtSource source) {
    final kw = Uri.encodeComponent(source.keyword);
    if (source.name == '大众点评') {
      // 小程序里是跳点评小程序搜索页；iOS 降级为点评网页搜索
      _launch(Uri.parse('https://www.dianping.com/search/keyword/1_0_$kw'));
      return;
    }
    if (source.name == '小红书') {
      // 小程序里小红书也是走网页（复制链接）；iOS 直接打开
      _launch(Uri.parse('https://www.xiaohongshu.com/search_result?keyword=$kw'));
      return;
    }
    showToast(context, '暂无法跳转');
  }

  Future<void> _launch(Uri uri) async {
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (mounted) showToast(context, '打开失败');
    }
  }

  void _onPhotoError(int index) {
    final court = _court;
    if (court == null || index < 0 || index >= court.photos.length) return;
    final photos = List<String>.from(court.photos)..removeAt(index);
    setState(() {
      court.photos = photos;
      _coverIndex =
          photos.isEmpty ? 0 : _coverIndex.clamp(0, photos.length - 1).toInt();
    });
  }

  // ── UI ──

  @override
  Widget build(BuildContext context) {
    final court = _court;
    // 对齐 wx.setNavigationBarTitle：标题为球场名（截 12 字），缺省「球场详情」
    final title = court == null
        ? '球场详情'
        : court.name.length > 12
            ? court.name.substring(0, 12)
            : court.name;

    return Scaffold(
      appBar: themedAppBar(context, title: title),
      body: ThemedPage(
        child: court == null
            ? _buildStatus()
            : Stack(
                children: [
                  _buildBody(court),
                  Positioned(left: 0, right: 0, bottom: 0, child: _buildBottomBar(court)),
                ],
              ),
      ),
    );
  }

  /// 加载 / 错误状态（对齐 .status-wrap）
  Widget _buildStatus() {
    final theme = slamOf(context);
    if (_loading) {
      return Center(
        child: Text('加载中…', style: TextStyle(fontSize: 14, color: theme.muted)),
      );
    }
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(_errorText, style: const TextStyle(fontSize: 14, color: S.danger)),
          const SizedBox(height: 18),
          GestureDetector(
            onTap: () {
              setState(() {
                _loading = true;
                _errorText = '';
              });
              _load();
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 9),
              decoration: BoxDecoration(
                color: theme.accent,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text('重试',
                  style: TextStyle(
                      color: theme.accentInk, fontSize: 13, fontWeight: FontWeight.w600)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(Court court) {
    return ListView(
      // 对齐 .detail-page padding-bottom：给底部栏留位
      padding: const EdgeInsets.only(bottom: 160),
      children: [
        _buildHero(court),
        _buildInfo(court),
      ],
    );
  }

  /// 图片轮播（对齐 .hero-section：480rpx≈240 高，PageView + 计数角标）
  Widget _buildHero(Court court) {
    if (court.photos.isEmpty) {
      // 对齐 .hero-fallback
      return Container(
        height: 180,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFBAF5E8), Color(0xFFD4FFF4)],
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('🎾', style: TextStyle(fontSize: 40)),
            const SizedBox(height: 10),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Text(
                court.name,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32)),
              ),
            ),
          ],
        ),
      );
    }
    return SizedBox(
      height: 240,
      child: Stack(
        children: [
          PageView.builder(
            controller: _pageCtrl,
            itemCount: court.photos.length,
            onPageChanged: (i) => setState(() => _coverIndex = i),
            itemBuilder: (_, i) => CachedNetworkImage(
              imageUrl: court.photos[i],
              fit: BoxFit.cover,
              placeholder: (_, __) => Container(color: const Color(0xFFE8ECF1)),
              errorWidget: (_, __, ___) {
                WidgetsBinding.instance
                    .addPostFrameCallback((__) => _onPhotoError(i));
                return Container(color: const Color(0xFFE8ECF1));
              },
            ),
          ),
          // 指示点（对齐 indicator-dots）
          if (court.photos.length > 1) ...[
            Positioned(
              left: 0,
              right: 0,
              bottom: 10,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (var i = 0; i < court.photos.length; i++)
                    Container(
                      width: 6,
                      height: 6,
                      margin: const EdgeInsets.symmetric(horizontal: 3),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: i == _coverIndex
                            ? S.green
                            : Colors.white.withValues(alpha: 0.5),
                      ),
                    ),
                ],
              ),
            ),
            // 计数角标（对齐 .photo-count）
            Positioned(
              right: 10,
              bottom: 10,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.55),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${_coverIndex + 1}/${court.photos.length}',
                  style: const TextStyle(color: Colors.white, fontSize: 11),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// 主体信息卡（对齐 .info-section）
  Widget _buildInfo(Court court) {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
      decoration: S.card(radius: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 名称 + 评分徽章（对齐 .title-row / .rating-badge）
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  court.name,
                  style: const TextStyle(
                      fontSize: 19, fontWeight: FontWeight.w700, color: Color(0xFF1A1F26)),
                ),
              ),
              if (court.rating > 0) ...[
                const SizedBox(width: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFFF5A623), Color(0xFFF7B84E)],
                    ),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(
                        court.rating.toStringAsFixed(1),
                        style: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w700, color: Colors.white),
                      ),
                      const SizedBox(width: 2),
                      const Text('分',
                          style: TextStyle(fontSize: 10, color: Color(0xD9FFFFFF))),
                    ],
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 7),
          // 距离 + 类型场地数（对齐 .sub-row）
          Row(
            children: [
              if (court.distanceText.isNotEmpty)
                Text('📍 ${court.distanceText}',
                    style: const TextStyle(
                        fontSize: 13, color: S.green, fontWeight: FontWeight.w500)),
              if (court.distanceText.isNotEmpty) const SizedBox(width: 4),
              Text(
                '· ${court.courtType}${court.totalCourts >= 0 ? court.totalCourts : ''}片场地',
                style: const TextStyle(fontSize: 13, color: S.muted),
              ),
            ],
          ),
          _divider(),

          // 参考价格
          _infoRow(
            '参考价格',
            Text('¥${court.priceRange}/小时',
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32))),
          ),
          // 地址 + 导航（对齐 .nav-link）
          _infoRow(
            '地址',
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Flexible(
                  child: Text(
                    court.address,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 14, color: Color(0xFF1A1F26)),
                  ),
                ),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: _onOpenMap,
                  child: const Text('📍 导航',
                      style: TextStyle(fontSize: 12, color: S.green)),
                ),
              ],
            ),
          ),
          // 电话 + 拨打
          if (court.phone.isNotEmpty)
            _infoRow(
              '电话',
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(court.phone,
                      style: const TextStyle(fontSize: 14, color: Color(0xFF1A1F26))),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: _onCall,
                    child: const Text('📞 拨打',
                        style: TextStyle(fontSize: 12, color: S.green)),
                  ),
                ],
              ),
            ),
          // 营业时间
          if (court.hours.isNotEmpty)
            _infoRow(
              '营业时间',
              Text(court.hours,
                  style: const TextStyle(fontSize: 14, color: Color(0xFF1A1F26))),
            ),
          _divider(),

          // 场地统计（对齐 .court-stats）
          if (court.indoorCourts > 0 || court.outdoorCourts > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Row(
                children: [
                  if (court.indoorCourts > 0) ...[
                    Expanded(child: _statItem('${court.indoorCourts}', '室内场地')),
                    if (court.outdoorCourts > 0) const SizedBox(width: 12),
                  ],
                  if (court.outdoorCourts > 0)
                    Expanded(child: _statItem('${court.outdoorCourts}', '室外场地')),
                ],
              ),
            ),

          // 设施与服务（对齐 .facility-chips）
          if (court.facilities.isNotEmpty) ...[
            const Text('设施与服务',
                style: TextStyle(
                    fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF1A1F26))),
            const SizedBox(height: 9),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final f in court.facilities)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
                    decoration: BoxDecoration(
                      color: const Color(0xFFD4FFF4),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: const Color(0xFFBAF5E8)),
                    ),
                    child: Text(f,
                        style: const TextStyle(fontSize: 12, color: Color(0xFF0D3D32))),
                  ),
              ],
            ),
          ],
          _divider(),

          // 外部评价（对齐 .ext-section）
          if (court.extSources.isNotEmpty) ...[
            const Text('💬 看看大家怎么说',
                style: TextStyle(
                    fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF1A1F26))),
            const SizedBox(height: 9),
            for (var i = 0; i < court.extSources.length; i++)
              Padding(
                padding: EdgeInsets.only(top: i == 0 ? 0 : 6),
                child: GestureDetector(
                  onTap: () => _onExtSource(court.extSources[i]),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 11),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF7FAF8),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFE8ECF1)),
                    ),
                    child: Row(
                      children: [
                        Text(court.extSources[i].icon,
                            style: const TextStyle(fontSize: 18)),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text('${court.extSources[i].name}上看评价',
                              style: const TextStyle(
                                  fontSize: 14, color: Color(0xFF1A1F26))),
                        ),
                        const Text('›',
                            style: TextStyle(fontSize: 16, color: S.faint)),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }

  Widget _divider() => Container(
        height: 1,
        color: const Color(0xFFF0F3F6),
        margin: const EdgeInsets.symmetric(vertical: 14),
      );

  /// 对齐 .info-row
  Widget _infoRow(String label, Widget value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 14, color: S.muted)),
          const SizedBox(width: 16),
          Flexible(child: value),
        ],
      ),
    );
  }

  /// 对齐 .stat-item
  Widget _statItem(String num, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF7FAF8),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Text(num,
              style: const TextStyle(
                  fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32))),
          const SizedBox(height: 3),
          Text(label, style: const TextStyle(fontSize: 11, color: S.muted)),
        ],
      ),
    );
  }

  /// 底部预定栏（对齐 .bottom-bar；「分享」依赖微信会话，iOS 省略）
  Widget _buildBottomBar(Court court) {
    final opts = court.bookingOptions;
    return Container(
      decoration: const BoxDecoration(
        color: S.cardBg,
        border: Border(top: BorderSide(color: Color(0xFFE8ECF1))),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
              child: Row(
                children: [
                  // 地图（对齐 .action-btn 地图）
                  GestureDetector(
                    onTap: _onOpenMap,
                    behavior: HitTestBehavior.opaque,
                    child: const SizedBox(
                      width: 48,
                      child: Column(
                        children: [
                          SizedBox(
                            height: 24,
                            child: Icon(Icons.location_on_outlined,
                                size: 20, color: Color(0xFF2A3330)),
                          ),
                          SizedBox(height: 3),
                          Text('地图', style: TextStyle(fontSize: 10, color: S.muted)),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // 主预约按钮（对齐 .main-book-btn）
                  Expanded(
                    child: GestureDetector(
                      onTap: opts.isNotEmpty ? _onMainBook : null,
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 9),
                        decoration: BoxDecoration(
                          gradient: opts.isNotEmpty
                              ? const LinearGradient(
                                  begin: Alignment.topLeft,
                                  end: Alignment.bottomRight,
                                  colors: [Color(0xFF3BF0BF), S.green],
                                )
                              : null,
                          color: opts.isNotEmpty ? null : const Color(0xFFD0D5DD),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Column(
                          children: [
                            Text(
                              opts.isNotEmpty ? '预约打球' : '暂不支持在线预定',
                              style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white),
                            ),
                            if (opts.isNotEmpty) ...[
                              const SizedBox(height: 1),
                              Text(
                                opts.first.name,
                                style: const TextStyle(
                                    fontSize: 10, color: Color(0xCCFFFFFF)),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // 更多预定渠道（对齐 .more-channels）
            if (opts.length > 1)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(12, 6, 12, 8),
                decoration: const BoxDecoration(
                  border: Border(top: BorderSide(color: Color(0xFFF0F3F6), width: 0.5)),
                ),
                child: Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Text('更多预定方式：',
                        style: TextStyle(fontSize: 11, color: S.faint)),
                    for (var i = 1; i < opts.length; i++)
                      GestureDetector(
                        onTap: () => _doBooking(opts[i]),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0xFFD4FFF4),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(opts[i].name,
                              style:
                                  const TextStyle(fontSize: 11, color: S.green)),
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
