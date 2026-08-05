#!/usr/bin/env bash
# 将 WSL 仓库内的 miniprogram/ 同步到 Windows NTFS 目录，供微信开发者工具打开。
# 源目录（WSL，与云主机一致）为唯一真相源；Windows 副本仅给 DevTools 用，勿在那边长期改代码。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${REPO_ROOT}/miniprogram"

# 默认同步到当前 Windows 用户下的固定路径；可用环境变量覆盖
WIN_USER="${WIN_USER:-baozi}"
DST_DEFAULT="/mnt/c/Users/${WIN_USER}/code/tenclip-miniprogram"
DST="${TENCLIP_MP_WIN_DST:-$DST_DEFAULT}"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: source not found: $SRC" >&2
  exit 1
fi

if [[ ! -d /mnt/c/Users ]]; then
  echo "ERROR: /mnt/c 不可用。请在 WSL 内执行本脚本，且已挂载 Windows C:。" >&2
  exit 1
fi

mkdir -p "$(dirname "$DST")"
mkdir -p "$DST"

echo "Sync miniprogram → Windows (for WeChat DevTools)"
echo "  SRC: $SRC"
echo "  DST: $DST"
echo

# rsync：增量、可删多余文件，排除工具缓存与本机私有配置
rsync -a --delete \
  --exclude '.DS_Store' \
  --exclude 'project.private.config.json' \
  --exclude 'node_modules/' \
  "$SRC/" "$DST/"

# 快速自检：首页 wxml 必须存在
if [[ ! -f "$DST/pages/feed/index.wxml" ]]; then
  echo "ERROR: sync incomplete — missing pages/feed/index.wxml" >&2
  exit 1
fi

echo "OK. Open this folder in WeChat DevTools:"
echo "  C:\\Users\\${WIN_USER}\\code\\tenclip-miniprogram"
echo
echo "Tip: 改完小程序代码后重新跑本脚本，再在开发者工具里点「编译」。"
