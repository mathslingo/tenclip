#!/usr/bin/env bash
# 自检小程序依赖的后端接口（须先启动 app.py，默认 7861）
set -euo pipefail
BASE="${1:-http://127.0.0.1:7861}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp /tmp/tenclip_probe.XXXXXX.mp4)"
trap 'rm -f "$TMP"' EXIT

echo "==> health $BASE/api/mobile/health"
curl -sf "$BASE/api/mobile/health" | head -c 200
echo ""

echo "==> stroke submit (tiny file)"
# 最小有效 ftyp 头即可测 multipart 通路
printf 'ftypisom' > "$TMP"
RESP="$(curl -sf -X POST "$BASE/api/mobile/stroke-extract/submit" \
  -F "video=@${TMP};filename=probe.mp4" \
  -F "detect_mode=combined" \
  -F "motion_percentile=72" \
  -F "vlm_filter=0")"
echo "$RESP" | head -c 300
echo ""
TASK_ID="$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")"

echo "==> stroke task status $TASK_ID"
curl -sf "$BASE/api/mobile/stroke-extract/tasks/$TASK_ID" | head -c 400
echo ""
echo "OK: 上传提交与任务查询通路正常（分析可能因探针文件无效而 failed，属预期）"
