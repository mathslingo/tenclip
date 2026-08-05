import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import 'config.dart';
import 'pages/analyze_page.dart';
import 'pages/stroke_page.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TenclipApp());
}

class TenclipApp extends StatelessWidget {
  const TenclipApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: appDisplayName,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF13D8A8),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF2F3F5),
      ),
      home: const HomeShell(),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: const [
          StrokePage(),
          AnalyzePage(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(CupertinoIcons.scissors),
            label: '击球剪辑',
          ),
          NavigationDestination(
            icon: Icon(CupertinoIcons.sportscourt),
            label: '动作分析',
          ),
        ],
      ),
    );
  }
}
