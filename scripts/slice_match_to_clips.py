#!/usr/bin/env python3
"""把网球比赛长视频按时间段批量切成短片，并生成可直接喂给
`build_vlm_dataset_from_videos.py` 的 manifest 骨架。

输入「切片表」（segments），每行描述一个片段（建议一拍 / 一回合，3~10 秒）：

JSONL（推荐，可携带标注字段）::

    {"id":"rally_001","start":"00:12:30","end":"00:12:38","instruction":"...","input":"...","output":""}
    {"id":"rally_002","start":750.5,"end":758,"instruction":"...","input":"..."}

CSV（表头需含 id,start,end，其余列原样带入 manifest）::

    id,start,end,instruction,input,output
    rally_001,00:12:30,00:12:38,请分析正手击球...,场景：底线对拉,

时间支持 `秒`（float）或 `HH:MM:SS(.ms)`。

用法::

    # 单一源视频 + 切片表
    python scripts/slice_match_to_clips.py \
        --video data/matches/match.mp4 \
        --segments data/segments.jsonl \
        --clips-dir data/clips \
        --manifest-out data/manifest_sft.jsonl --mode sft

    # 每行自带 video_path 时可省略 --video
    # 只看将执行的 ffmpeg 命令，不落盘：
    python scripts/slice_match_to_clips.py --video m.mp4 --segments s.jsonl --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_SFT_FIELDS = ("instruction", "input", "output")
_DPO_FIELDS = ("instruction", "input", "chosen", "rejected")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Slice a tennis match video into clips and build a manifest skeleton.")
    p.add_argument("--segments", required=True, help="切片表路径（.jsonl 或 .csv）。")
    p.add_argument("--video", default="", help="源视频路径；当切片表每行未给 video_path 时必填。")
    p.add_argument("--clips-dir", default="data/clips", help="切片输出目录。")
    p.add_argument("--manifest-out", default="data/manifest.jsonl", help="生成的 manifest 输出路径。")
    p.add_argument("--mode", choices=["sft", "dpo"], default="sft", help="决定 manifest 骨架带哪些标注字段。")
    p.add_argument("--ext", default="mp4", help="切片文件扩展名（默认 mp4）。")
    p.add_argument(
        "--copy",
        action="store_true",
        help="用 -c copy 快速切（不重编码，速度快但非关键帧处可能不精确）。默认重编码以保证精度。",
    )
    p.add_argument("--limit", type=int, default=0, help="只处理前 N 个片段（0=全部），便于试跑。")
    p.add_argument("--dry-run", action="store_true", help="只打印将执行的 ffmpeg 命令与 manifest，不实际写盘。")
    p.add_argument("--overwrite", action="store_true", help="切片已存在时覆盖（默认跳过已存在的切片）。")
    return p.parse_args()


def _load_segments(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise SystemExit(f"切片表不存在: {path}")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = [dict(r) for r in csv.DictReader(f)]
    else:
        rows = []
        for ln in path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    if not rows:
        raise SystemExit(f"切片表为空: {path}")
    return rows


def _norm_time(v: Any) -> str:
    """秒(float)或 HH:MM:SS(.ms) 字符串，统一成 ffmpeg 接受的字符串。"""
    s = str(v).strip()
    if not s:
        raise ValueError("空的时间值")
    if ":" in s:
        return s
    return f"{float(s):.3f}"


def _ffmpeg_cmd(src: str, start: str, end: str, out: Path, copy: bool, overwrite: bool) -> list[str]:
    cmd = ["ffmpeg", "-y" if overwrite else "-n", "-ss", start, "-to", end, "-i", src]
    if copy:
        cmd += ["-c", "copy"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac"]
    cmd += [str(out)]
    return cmd


def main() -> int:
    args = parse_args()
    segments = _load_segments(Path(args.segments))
    if args.limit and args.limit > 0:
        segments = segments[: args.limit]

    clips_dir = Path(args.clips_dir)
    manifest_out = Path(args.manifest_out)
    carry = _SFT_FIELDS if args.mode == "sft" else _DPO_FIELDS

    if not args.dry_run and shutil.which("ffmpeg") is None:
        raise SystemExit("未找到 ffmpeg，请先安装（conda install -c conda-forge ffmpeg 或系统包管理器）。")

    if not args.dry_run:
        clips_dir.mkdir(parents=True, exist_ok=True)
        manifest_out.parent.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    made, skipped, failed = 0, 0, 0

    for i, seg in enumerate(segments):
        sid = str(seg.get("id") or f"clip_{i:04d}").strip()
        src = str(seg.get("video_path") or args.video).strip()
        if not src:
            raise SystemExit(f"[{sid}] 既无 video_path 也未提供 --video")
        try:
            start = _norm_time(seg["start"])
            end = _norm_time(seg["end"])
        except (KeyError, ValueError) as e:
            raise SystemExit(f"[{sid}] start/end 缺失或非法: {e}")

        out_clip = clips_dir / f"{sid}.{args.ext}"
        cmd = _ffmpeg_cmd(src, start, end, out_clip, args.copy, args.overwrite)

        if args.dry_run:
            print("DRY  " + " ".join(cmd))
        elif out_clip.exists() and not args.overwrite:
            print(f"SKIP 已存在 {out_clip}")
            skipped += 1
        else:
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                print(f"OK   {out_clip}")
                made += 1
            except subprocess.CalledProcessError as e:
                err = (e.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
                print(f"FAIL {sid}: {err[0]}", file=sys.stderr)
                failed += 1
                continue

        row: dict[str, Any] = {"id": sid, "video_path": str(out_clip)}
        for k in carry:
            row[k] = seg.get(k, "")
        manifest_rows.append(row)

    if args.dry_run:
        print("\n--- manifest 预览（dry-run，未写盘）---")
        for r in manifest_rows[:5]:
            print(json.dumps(r, ensure_ascii=False))
        if len(manifest_rows) > 5:
            print(f"... 共 {len(manifest_rows)} 行")
        return 0

    with manifest_out.open("w", encoding="utf-8") as f:
        for r in manifest_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n切片: 新建 {made} / 跳过 {skipped} / 失败 {failed}")
    print(f"manifest: {len(manifest_rows)} 行 -> {manifest_out}")
    print(f"下一步: python scripts/build_vlm_dataset_from_videos.py --mode {args.mode} "
          f"--manifest {manifest_out} --out data/tennis_vlm_{args.mode}.json --register-key tennis_vlm_{args.mode}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
