#!/usr/bin/env python3
"""自动检测网球视频中的击球/回合片段，剪掉等待与非击球时间。

适合 **长视频 / 大文件（200MB+）**：画面与音频均为 ffmpeg **流式**分析，不整段载入内存。

用法::

    python scripts/extract_stroke_clips.py /path/to/match.MOV --analyze-only
    python scripts/extract_stroke_clips.py match.MOV --out data/clips/strokes.mp4
    python scripts/extract_stroke_clips.py match.MOV --vlm-filter --out out.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.stroke_detect import (  # noqa: E402
    StrokeDetectConfig,
    detect_stroke_segments,
    export_stroke_clips,
    run_stroke_extract_pipeline,
    segments_to_manifest_rows,
    write_segments_jsonl,
)


def _resolve_output_file(path: Path | str, default: Path, arg_name: str) -> Path:
    """若传入目录或 '.'，则在目录下使用 default 文件名。"""
    p = Path(path)
    if not str(path).strip():
        raise ValueError(f"{arg_name} 不能为空")
    if p.is_dir() or str(p) == ".":
        p = p / default.name
    elif p.exists() and p.is_dir():
        p = p / default.name
    elif not p.suffix:
        p = p.with_suffix(default.suffix)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="检测并保留网球视频中的击球/回合片段（支持长视频）")
    p.add_argument("video", type=Path, help="输入视频路径")
    p.add_argument("--out", type=Path, default="", help="输出视频（拼接后的击球集锦）")
    p.add_argument("--mode", choices=["motion", "audio", "combined"], default="combined")
    p.add_argument("--analyze-only", action="store_true", help="只检测时间段，不写输出视频")
    p.add_argument("--vlm-filter", action="store_true", help="VLM 二次过滤（较慢，需 GPU/模型）")
    p.add_argument("--vlm-mode", choices=["eco", "balanced", "quality"], default="eco")
    p.add_argument("--segments-out", type=Path, default="", help="导出切片表 JSONL")
    p.add_argument("--report-out", type=Path, default="", help="导出检测报告 JSON")
    p.add_argument("--max-sec", type=float, default=0.0, help="只分析前 N 秒（0=全片）")
    p.add_argument("--motion-percentile", type=float, default=72.0)
    p.add_argument("--audio-percentile", type=float, default=82.0)
    p.add_argument("--merge-gap", type=float, default=2.8)
    p.add_argument("--copy", action="store_true", help="切片 -c copy（快，关键帧处可能不精确）")
    return p.parse_args()


def _progress_print(msg: str, frac: float) -> None:
    print(f"[{int(frac * 100):3d}%] {msg}", flush=True)


def main() -> int:
    args = parse_args()
    if not args.video.is_file():
        print(f"视频不存在: {args.video}", file=sys.stderr)
        return 1

    cfg = StrokeDetectConfig(
        max_analyze_sec=float(args.max_sec),
        motion_percentile=float(args.motion_percentile),
        audio_percentile=float(args.audio_percentile),
        merge_gap_sec=float(args.merge_gap),
    )

    print(f"分析: {args.video}  ({args.video.stat().st_size / (1024*1024):.1f} MB)  mode={args.mode}")
    if args.vlm_filter:
        print("VLM 二次过滤: 开")

    if args.analyze_only:
        result = detect_stroke_segments(
            args.video, mode=args.mode, config=cfg, progress=_progress_print
        )
        if args.vlm_filter and result.segments:
            from services.stroke_vlm_filter import vlm_filter_segments

            segs, vlm_dbg = vlm_filter_segments(
                str(args.video),
                result.segments,
                perf_mode=args.vlm_mode,
                progress=lambda m: _progress_print(m, 0.7),
            )
            result.segments = segs
            result.kept_sec = sum(s.duration() for s in segs)
            result.debug["vlm"] = vlm_dbg
    else:
        out = Path(args.out) if args.out else args.video.with_name(args.video.stem + "_strokes_only.mp4")
        result = run_stroke_extract_pipeline(
            args.video,
            out,
            mode=args.mode,
            config=cfg,
            vlm_filter=args.vlm_filter,
            vlm_mode=args.vlm_mode,
            copy=args.copy,
            progress=_progress_print,
        )
        if result.segments:
            print(f"导出: {out}")

    ratio = result.kept_sec / result.duration_sec if result.duration_sec > 0 else 0.0
    print(f"原时长 {result.duration_sec:.1f}s → 保留 {result.kept_sec:.1f}s ({ratio:.0%})，{len(result.segments)} 段")

    for i, seg in enumerate(result.segments[:20]):
        print(f"  [{i:02d}] {seg.start:7.2f}s - {seg.end:7.2f}s  ({seg.duration():.2f}s)  score={seg.score:.3f}")
    if len(result.segments) > 20:
        print(f"  ... 其余 {len(result.segments) - 20} 段")

    if args.report_out:
        report_path = _resolve_output_file(
            args.report_out,
            args.video.with_name(f"{args.video.stem}_stroke_report.json"),
            "--report-out",
        )
        report_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告: {report_path}")

    if args.segments_out:
        seg_path = _resolve_output_file(
            args.segments_out,
            args.video.with_name(f"{args.video.stem}_segments.jsonl"),
            "--segments-out",
        )
        rows = segments_to_manifest_rows(result.segments, video_path=args.video)
        write_segments_jsonl(rows, seg_path)
        print(f"切片表: {seg_path} ({len(rows)} 行)")

    if args.analyze_only:
        return 0 if result.segments else 1
    return 0 if result.segments else 1


if __name__ == "__main__":
    raise SystemExit(main())
