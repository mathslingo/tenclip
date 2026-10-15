import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../config.dart';
import '../widgets/common.dart';

/// 协议类型（对齐 miniprogram pages/legal-privacy / legal-terms）
enum LegalKind { privacy, terms }

/// 隐私政策 / 用户服务协议（标题与正文逐字对齐小程序）
class LegalPage extends StatelessWidget {
  const LegalPage({super.key, required this.kind});

  final LegalKind kind;

  bool get _isPrivacy => kind == LegalKind.privacy;

  String get _title => _isPrivacy ? '隐私政策' : '用户协议';

  String get _webUrl => '$apiBaseUrl/legal/${_isPrivacy ? 'privacy' : 'terms'}';

  /// (样式, 文本)；样式：h1 / meta / h2 / p / li
  List<(String, String)> get _blocks =>
      _isPrivacy ? _privacyBlocks : _termsBlocks;

  Future<void> _copyWebUrl(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: _webUrl));
    if (!context.mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('链接已复制'),
        content: Text('完整$_title地址已复制，可粘贴到浏览器打开：\n$_webUrl'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: themedAppBar(context, title: _title),
      body: ThemedPage(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 20),
          children: [
            SlamCard(
              padding: const EdgeInsets.fromLTRB(14, 16, 14, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final b in _blocks) _block(b),
                  const SizedBox(height: 20),
                  Center(
                    child: GestureDetector(
                      onTap: () => _copyWebUrl(context),
                      child: const Text('查看网页完整版',
                          style: TextStyle(fontSize: 13, color: Color(0xFF0A8F6D))),
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

  Widget _block((String, String) b) {
    switch (b.$1) {
      case 'h1':
        return Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text(b.$2,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF0D3D32))),
        );
      case 'meta':
        return Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: Text(b.$2, style: const TextStyle(fontSize: 11, color: Color(0xFF9AA3AD))),
        );
      case 'h2':
        return Padding(
          padding: const EdgeInsets.only(top: 16, bottom: 5),
          child: Text(b.$2,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF22303C))),
        );
      default: // p / li
        return Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text(b.$2, style: const TextStyle(fontSize: 13, color: S.sub, height: 1.7)),
        );
    }
  }
}

const _privacyBlocks = <(String, String)>[
  ('h1', 'UChance 隐私政策'),
  ('meta', '更新日期：2026-09-08'),
  ('p', '欢迎使用 UChance。本政策说明我们如何收集、使用与保护你的个人信息。使用本小程序即表示你已阅读并同意本政策。'),
  ('h2', '一、我们收集的信息'),
  ('li', '· 账号信息：微信 openid / 会话；游客昵称与密码（哈希存储）'),
  ('li', '· 资料信息：头像、昵称、简介、网球习惯等'),
  ('li', '· 内容信息：笔记、图片、评论、点赞、关注'),
  ('li', '· 媒体权限：经你授权访问相册/相机（剪辑、发笔记、关键点）'),
  ('li', '· 位置信息：仅在你主动选地点或找球场时使用'),
  ('li', '· 设备与日志：必要的请求与错误日志'),
  ('h2', '二、使用目的'),
  ('p', '提供登录、发笔记、社交、击球剪辑、关键点检测等功能；保障安全与排查故障；在法律法规或你同意的范围内使用。'),
  ('h2', '三、存储与共享'),
  ('p', '数据主要存储于中国境内服务器。我们不会出售个人信息；仅在法律要求、保护权益或经你同意时可能披露。'),
  ('h2', '四、你的权利'),
  ('p', '可在「我的」编辑资料、删除自己的笔记与评论。注销账号请通过设置反馈联系我们。'),
  ('h2', '五、未成年人'),
  ('p', '本产品主要面向成年人。未满 18 周岁请在监护人指导下使用。'),
  ('h2', '六、联系我们'),
  ('p', '隐私问题请通过「我的 → 设置」反馈，或按公众平台主体信息联系运营方。'),
];

const _termsBlocks = <(String, String)>[
  ('h1', 'UChance 用户服务协议'),
  ('meta', '更新日期：2026-09-08'),
  ('p', '本协议是你与 UChance 之间关于使用本小程序及相关服务的约定。注册、登录或使用即视为同意本协议。'),
  ('h2', '一、服务内容'),
  ('p', '提供网球相关内容浏览、笔记发布、社交互动、击球剪辑、姿态关键点预览、球场信息查询等。具体以实际提供为准。'),
  ('h2', '二、账号规范'),
  ('li', '· 妥善保管账号与密码'),
  ('li', '· 不得冒用身份、批量注册或干扰服务'),
  ('li', '· 游客账号与微信账号均受本协议约束'),
  ('h2', '三、用户内容'),
  ('li', '· 保证发布内容合法且不侵权'),
  ('li', '· 禁止违法、色情、暴力、骚扰、欺诈等内容'),
  ('li', '· 违规内容可被隐藏、删除或限制功能'),
  ('h2', '四、AI / 算法说明'),
  ('p', '击球剪辑与关键点等结果仅供训练参考，不构成专业教练或医疗建议。'),
  ('h2', '五、免责声明'),
  ('p', '因网络、第三方、不可抗力或自身操作导致的中断、丢失或间接损失，在法律允许范围内我们不承担责任。球场预订以实际场馆为准。'),
  ('h2', '六、适用法律'),
  ('p', '适用中华人民共和国法律。争议协商不成的，提交有管辖权的人民法院解决。'),
];
