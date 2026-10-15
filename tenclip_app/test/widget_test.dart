import 'package:flutter_test/flutter_test.dart';
import 'package:tenclip_app/models/models.dart';
import 'package:tenclip_app/widgets/common.dart';

void main() {
  test('splitWaterfall 按累高分列', () {
    final items = [
      FeedItem(id: '1', coverRatio: 1.0),
      FeedItem(id: '2', coverRatio: 1.0),
      FeedItem(id: '3', coverRatio: 2.0),
    ];
    final r = splitWaterfall(items);
    expect(r.left.map((e) => e.id), ['1', '3']);
    expect(r.right.map((e) => e.id), ['2']);
  });

  test('formatFeedTime 相对时间', () {
    final nowSec = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    expect(formatFeedTime(nowSec), '刚刚');
    expect(formatFeedTime(nowSec - 300), '5 分钟前');
    expect(formatFeedTime(0), '');
  });
}
