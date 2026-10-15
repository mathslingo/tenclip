import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'api/auth_api.dart';
import 'api/court_api.dart';
import 'api/feed_api.dart';
import 'api/mobile_api.dart';
import 'api/social_api.dart';
import 'config.dart';
import 'core/api_client.dart';
import 'core/session.dart';
import 'core/storage.dart';
import 'pages/action_analyze_page.dart';
import 'pages/court_detail_page.dart';
import 'pages/courts_page.dart';
import 'pages/feed_detail_page.dart';
import 'pages/feed_page.dart';
import 'pages/feed_search_page.dart';
import 'pages/follow_list_page.dart';
import 'pages/legal_page.dart';
import 'pages/login_page.dart';
import 'pages/me_page.dart';
import 'pages/messages_page.dart';
import 'pages/note_compose_page.dart';
import 'pages/note_detail_page.dart';
import 'pages/pose_tab_page.dart';
import 'pages/pose_webview_page.dart';
import 'pages/profile_edit_page.dart';
import 'pages/profile_page.dart';
import 'pages/settings_page.dart';
import 'pages/stroke_extract_page.dart';
import 'pages/user_page.dart';
import 'state/app_state.dart';
import 'theme/slam_theme.dart';
import 'widgets/app_tab_bar.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final storage = await Storage.init();
  final session = Session(storage);
  final apiClient = ApiClient(session);
  final authApi = AuthApi(apiClient, session);
  final socialApi = SocialApi(apiClient, session);
  final courtApi = CourtApi(apiClient);
  final feedApi = FeedApi(apiClient, storage);
  final mobileApi = MobileApi(apiClient);
  final slam = SlamController(storage)..load();
  final appState = AppState(session, authApi, socialApi);

  runApp(
    MultiProvider(
      providers: [
        Provider<Storage>.value(value: storage),
        Provider<Session>.value(value: session),
        Provider<ApiClient>.value(value: apiClient),
        Provider<AuthApi>.value(value: authApi),
        Provider<SocialApi>.value(value: socialApi),
        Provider<CourtApi>.value(value: courtApi),
        Provider<FeedApi>.value(value: feedApi),
        Provider<MobileApi>.value(value: mobileApi),
        ChangeNotifierProvider<SlamController>.value(value: slam),
        ChangeNotifierProvider<AppState>.value(value: appState),
      ],
      child: const TenclipApp(),
    ),
  );
}

class TenclipApp extends StatelessWidget {
  const TenclipApp({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = context.watch<SlamController>().theme;
    return MaterialApp(
      title: appDisplayName,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: theme.pageBg,
        colorScheme: ColorScheme.dark(
          primary: theme.accent,
          onPrimary: theme.accentInk,
          surface: theme.courtA,
          onSurface: theme.ink,
        ),
        useMaterial3: true,
        splashFactory: NoSplash.splashFactory,
      ),
      home: const HomeShell(),
      onGenerateRoute: _onGenerateRoute,
    );
  }
}

Route<dynamic> _onGenerateRoute(RouteSettings settings) {
  final args = settings.arguments is Map
      ? Map<String, dynamic>.from(settings.arguments as Map)
      : <String, dynamic>{};
  Widget page;
  switch (settings.name) {
    case '/login':
      page = LoginPage(from: args['from']?.toString() ?? '');
      break;
    case '/me':
      page = const MePage();
      break;
    case '/profile-edit':
      page = const ProfileEditPage();
      break;
    case '/settings':
      page = const SettingsPage();
      break;
    case '/legal-privacy':
      page = const LegalPage(kind: LegalKind.privacy);
      break;
    case '/legal-terms':
      page = const LegalPage(kind: LegalKind.terms);
      break;
    case '/court-detail':
      page = CourtDetailPage(courtId: args['id']?.toString() ?? '');
      break;
    case '/feed-detail':
      page = FeedDetailPage(itemId: args['id']?.toString() ?? '');
      break;
    case '/feed-search':
      page = const FeedSearchPage();
      break;
    case '/note-detail':
      page = NoteDetailPage(noteId: args['id']?.toString() ?? '');
      break;
    case '/note-compose':
      page = NoteComposePage(kind: args['kind']?.toString() ?? 'note');
      break;
    case '/user':
      page = UserPage(userId: args['user_id']?.toString() ?? '');
      break;
    case '/follow-list':
      page = FollowListPage(
        userId: args['user_id']?.toString() ?? '',
        kind: args['kind']?.toString() ?? 'following',
      );
      break;
    case '/messages':
      page = const MessagesPage();
      break;
    case '/stroke-extract':
      page = const StrokeExtractPage();
      break;
    case '/action-analyze':
      page = const ActionAnalyzePage();
      break;
    case '/pose-webview':
      page = PoseWebviewPage(url: args['url']?.toString() ?? '');
      break;
    default:
      page = const HomeShell();
  }
  return MaterialPageRoute(builder: (_) => page, settings: settings);
}

/// 需要登录（对齐 auth_api.requireLogin）；未登录跳登录页并返回 false
bool requireLogin(BuildContext context, {String from = ''}) {
  if (context.read<AppState>().isLoggedIn) return true;
  Navigator.of(context).pushNamed('/login', arguments: {'from': from});
  return false;
}

/// 主框架：找球场 · 发现 · [网球球] · 有场 · 我的
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 1; // 与小程序一致，默认落在「发现」

  static const _tabs = <Widget>[
    CourtsPage(),
    FeedPage(),
    PoseTabPage(),
    ProfilePage(),
  ];

  void _onActionBall() {
    final theme = context.read<SlamController>().theme;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: theme.courtA,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 8),
              _actionItem(ctx, '发笔记', 'note', theme),
              _actionItem(ctx, '发场地', 'offer', theme),
              _actionItem(ctx, '收场地', 'seek', theme),
              const SizedBox(height: 8),
            ],
          ),
        );
      },
    );
  }

  Widget _actionItem(BuildContext ctx, String label, String kind, SlamTheme theme) {
    return ListTile(
      title: Text(label, textAlign: TextAlign.center, style: TextStyle(color: theme.ink, fontSize: 16)),
      onTap: () {
        Navigator.pop(ctx);
        if (!requireLogin(context, from: 'compose')) return;
        Navigator.of(context).pushNamed('/note-compose', arguments: {'kind': kind});
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = context.watch<SlamController>().theme;
    return Scaffold(
      backgroundColor: theme.pageBg,
      body: IndexedStack(index: _index, children: _tabs),
      bottomNavigationBar: AppTabBar(
        theme: theme,
        selectedIndex: _index,
        onTap: (i) => setState(() => _index = i),
        onAction: _onActionBall,
      ),
    );
  }
}
