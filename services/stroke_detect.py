"""从网球视频中检测「击球/回合」活跃片段，剪掉等待与非击球时间。

思路（工程启发式，非端到端 VLM）：
1. **画面运动**：降采样灰度帧，相邻帧差分 → 回合中跑动/挥拍运动更强。
2. **击球声**（可选）：单声道音频 RMS 能量峰 → 击球瞬间常有短促冲击声。
3. 合并两路信号的时间段，加前后缓冲、合并近邻片段，再用 ffmpeg 拼接输出。

适合：业余/转播机位相对固定、能听见击球声的视频。
局限：换边、捡球、观众鼓掌、镜头推拉可能造成误检/漏检；精修可后续叠 VLM 或人工校对切片表。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

SignalMode = Literal["motion", "audio", "combined"]
ProgressFn = Callable[[str, float], None] | None


@dataclass
class StrokeDetectConfig:
    sample_fps: float = 4.0
    frame_width: int = 320
    frame_height: int = 180
    max_analyze_sec: float = 0.0  # 0 = 全片

    motion_percentile: float = 72.0
    audio_percentile: float = 82.0
    smooth_sec: float = 0.45

    min_segment_sec: float = 1.0
    max_segment_sec: float = 50.0
    pad_before_sec: float = 0.35
    pad_after_sec: float = 0.75
    merge_gap_sec: float = 2.8

    audio_sample_rate: int = 16000
    audio_hop_sec: float = 0.04

    # 尖峰锚定：短暂击球（如侧身正手）运动/声音持续不足 min_segment_sec 时，靠局部峰值补段
    enable_spike_detect: bool = True
    spike_motion_percentile: float = 58.0
    spike_audio_percentile: float = 68.0
    spike_pad_before_sec: float = 1.2
    spike_pad_after_sec: float = 2.8
    spike_min_interval_sec: float = 1.0


@dataclass
class StrokeSegment:
    start: float
    end: float
    score: float = 0.0
    source: str = "combined"

    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration(), 3),
            "score": round(self.score, 4),
            "source": self.source,
        }


@dataclass
class StrokeDetectResult:
    segments: list[StrokeSegment] = field(default_factory=list)
    duration_sec: float = 0.0
    kept_sec: float = 0.0
    mode: str = "combined"
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_sec": round(self.duration_sec, 3),
            "kept_sec": round(self.kept_sec, 3),
            "kept_ratio": round(self.kept_sec / self.duration_sec, 4) if self.duration_sec > 0 else 0.0,
            "mode": self.mode,
            "segment_count": len(self.segments),
            "segments": [s.to_dict() for s in self.segments],
            "debug": self.debug,
        }


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("未找到 ffmpeg，请安装：conda install -c conda-forge ffmpeg 或 sudo apt install ffmpeg")


def probe_duration(video_path: str | Path) -> float:
    video_path = str(video_path)
    if shutil.which("ffprobe") is None:
        from moviepy.video.io.VideoFileClip import VideoFileClip

        with VideoFileClip(video_path) as clip:
            return float(clip.duration)
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"ffprobe 无法读取时长: {video_path}")
    return float(out.stdout.strip())


def _smooth(values: np.ndarray, window: int) -> np.ndarray:
    if len(values) == 0:
        return values
    window = max(1, int(window))
    if window == 1:
        return values.astype(np.float64)
    kernel = np.ones(window, dtype=np.float64) / window
    return np.convolve(values.astype(np.float64), kernel, mode="same")


def _runs_above(mask: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    segs: list[tuple[int, int]] = []
    start: int | None = None
    for i, on in enumerate(mask):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= min_len:
                segs.append((start, i))
            start = None
    if start is not None and len(mask) - start >= min_len:
        segs.append((start, len(mask)))
    return segs


def _motion_scores(
    video_path: str,
    cfg: StrokeDetectConfig,
    progress: ProgressFn = None,
) -> tuple[np.ndarray, np.ndarray]:
    w, h = cfg.frame_width, cfg.frame_height
    vf = f"fps={cfg.sample_fps},scale={w}:{h},format=gray"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if cfg.max_analyze_sec and cfg.max_analyze_sec > 0:
        cmd += ["-t", str(cfg.max_analyze_sec)]
    cmd += ["-i", video_path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    frame_n = w * h
    prev: np.ndarray | None = None
    scores: list[float] = []
    times: list[float] = []
    i = 0
    report_every = max(200, int(cfg.sample_fps * 30))
    while True:
        buf = proc.stdout.read(frame_n)
        if len(buf) != frame_n:
            break
        gray = np.frombuffer(buf, dtype=np.uint8).reshape(h, w)
        t = i / cfg.sample_fps
        if prev is not None:
            scores.append(float(np.mean(np.abs(gray.astype(np.int16) - prev.astype(np.int16)))))
        else:
            scores.append(0.0)
        times.append(t)
        prev = gray
        i += 1
        if progress and i % report_every == 0:
            _emit(progress, f"画面运动分析… 已读 {i} 帧", 0.05 + min(0.35, i / (report_every * 20)))
    proc.wait()
    if proc.returncode not in (0, None) and not times:
        err = (proc.stderr or b"").decode("utf-8", "replace")[-400:]
        raise RuntimeError(f"ffmpeg 抽帧失败: {err}")
    return np.array(times, dtype=np.float64), np.array(scores, dtype=np.float64)


def probe_has_audio(video_path: str | Path) -> bool:
    video_path = str(video_path)
    if shutil.which("ffprobe") is None:
        return True
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.returncode == 0 and "audio" in (out.stdout or "").lower()


def _emit(progress: ProgressFn, msg: str, frac: float) -> None:
    if progress:
        progress(msg, max(0.0, min(1.0, frac)))


def _audio_rms_scores(
    video_path: str,
    cfg: StrokeDetectConfig,
    progress: ProgressFn = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """流式读取 PCM，避免长视频整段 wav 占内存（200MB+ 源文件常见 1h+）。"""
    _require_ffmpeg()
    sr = cfg.audio_sample_rate
    hop = max(1, int(sr * cfg.audio_hop_sec))
    win = max(hop, int(sr * cfg.audio_hop_sec * 2))
    bytes_per_sample = 2
    win_bytes = win * bytes_per_sample

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if cfg.max_analyze_sec and cfg.max_analyze_sec > 0:
        cmd += ["-t", str(cfg.max_analyze_sec)]
    cmd += ["-i", video_path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        return None
    assert proc.stdout is not None

    pcm_buf = b""
    rms: list[float] = []
    times: list[float] = []
    sample_offset = 0
    read_chunk = win_bytes * 8

    while True:
        chunk = proc.stdout.read(read_chunk)
        if not chunk:
            break
        pcm_buf += chunk
        while len(pcm_buf) >= win_bytes:
            window = pcm_buf[:win_bytes]
            pcm_buf = pcm_buf[hop * bytes_per_sample :]
            samples = np.frombuffer(window, dtype=np.int16).astype(np.float64)
            rms.append(float(np.sqrt(np.mean(samples * samples) + 1e-9)))
            times.append((sample_offset + win / 2) / sr)
            sample_offset += hop

    proc.wait()
    if proc.returncode != 0 and not times:
        return None
    if not rms:
        return None
    _emit(progress, "音频能量分析完成", 0.55)
    return np.array(times, dtype=np.float64), np.array(rms, dtype=np.float64)


def _scores_to_segments(
    times: np.ndarray,
    scores: np.ndarray,
    cfg: StrokeDetectConfig,
    percentile: float,
    source: str,
) -> list[StrokeSegment]:
    if len(scores) == 0:
        return []
    if source == "audio":
        win = max(1, int(cfg.smooth_sec / cfg.audio_hop_sec))
    else:
        win = max(1, int(cfg.smooth_sec * cfg.sample_fps))
    smoothed = _smooth(scores, win)
    thr = float(np.percentile(smoothed, percentile))
    min_len = max(1, int(cfg.min_segment_sec * cfg.sample_fps))
    if source == "audio":
        min_len = max(1, int(cfg.min_segment_sec / cfg.audio_hop_sec))
    runs = _runs_above(smoothed >= thr, min_len)
    out: list[StrokeSegment] = []
    for a, b in runs:
        t0 = float(times[a])
        t1 = float(times[min(b, len(times) - 1)])
        seg_score = float(np.max(smoothed[a:b]))
        out.append(StrokeSegment(start=t0, end=t1, score=seg_score, source=source))
    return out


def _spike_segments_from_signal(
    times: np.ndarray,
    scores: np.ndarray,
    cfg: StrokeDetectConfig,
    *,
    percentile: float,
    source: str,
    neighborhood_sec: float,
) -> list[StrokeSegment]:
    """在 RMS/运动曲线上找局部峰值，为短暂击球强制补一段（解决 28s 类漏检）。"""
    if len(scores) < 3:
        return []
    thr = float(np.percentile(scores, percentile))
    med = float(np.median(scores))
    if neighborhood_sec <= 0.05:
        neighborhood_sec = 0.25
    # 邻域半宽（样本点数）
    dt = float(np.median(np.diff(times))) if len(times) > 1 else 0.25
    radius = max(1, int(neighborhood_sec / max(dt, 1e-6)))

    candidates: list[tuple[float, float]] = []
    for i in range(1, len(scores) - 1):
        sc = float(scores[i])
        if sc < thr or sc < med * 1.35:
            continue
        lo, hi = max(0, i - radius), min(len(scores), i + radius + 1)
        if sc >= float(np.max(scores[lo:hi])) * 0.97:
            candidates.append((float(times[i]), sc))

    # 按强度 NMS，避免同一拍重复
    candidates.sort(key=lambda x: -x[1])
    picked: list[tuple[float, float]] = []
    for t, sc in candidates:
        if all(abs(t - pt) >= cfg.spike_min_interval_sec for pt, _ in picked):
            picked.append((t, sc))

    out: list[StrokeSegment] = []
    for t, sc in picked:
        out.append(
            StrokeSegment(
                start=t - cfg.spike_pad_before_sec,
                end=t + cfg.spike_pad_after_sec,
                score=sc,
                source=f"{source}_spike",
            )
        )
    return out


def _merge_segments(segments: list[StrokeSegment], gap: float) -> list[StrokeSegment]:
    if not segments:
        return []
    segs = sorted(segments, key=lambda s: s.start)
    merged: list[StrokeSegment] = [StrokeSegment(segs[0].start, segs[0].end, segs[0].score, segs[0].source)]
    for s in segs[1:]:
        last = merged[-1]
        if s.start <= last.end + gap:
            merged[-1] = StrokeSegment(
                start=last.start,
                end=max(last.end, s.end),
                score=max(last.score, s.score),
                source="combined" if last.source != s.source else last.source,
            )
        else:
            merged.append(StrokeSegment(s.start, s.end, s.score, s.source))
    return merged


def _pad_and_clip(
    segments: list[StrokeSegment],
    duration: float,
    cfg: StrokeDetectConfig,
) -> list[StrokeSegment]:
    out: list[StrokeSegment] = []
    for s in segments:
        start = max(0.0, s.start - cfg.pad_before_sec)
        end = min(duration, s.end + cfg.pad_after_sec)
        if end - start < cfg.min_segment_sec:
            continue
        if end - start > cfg.max_segment_sec:
            end = start + cfg.max_segment_sec
        out.append(StrokeSegment(start, end, s.score, s.source))
    return _merge_segments(out, gap=0.0)


def detect_stroke_segments(
    video_path: str | Path,
    *,
    mode: SignalMode = "combined",
    config: StrokeDetectConfig | None = None,
    progress: ProgressFn = None,
) -> StrokeDetectResult:
    """检测视频中应保留的击球/活跃时间段。"""
    _require_ffmpeg()
    video_path = Path(video_path)
    if not video_path.is_file():
        raise FileNotFoundError(str(video_path))

    cfg = config or StrokeDetectConfig()
    _emit(progress, "读取视频时长…", 0.02)
    duration = probe_duration(video_path)
    if cfg.max_analyze_sec and cfg.max_analyze_sec > 0:
        duration = min(duration, cfg.max_analyze_sec)

    segments: list[StrokeSegment] = []
    debug: dict[str, Any] = {"duration_sec": duration, "mode": mode}
    mt: np.ndarray | None = None
    ms: np.ndarray | None = None
    at: np.ndarray | None = None
    asc: np.ndarray | None = None

    if mode in ("motion", "combined"):
        _emit(progress, "分析画面运动（流式抽帧，适合长视频）…", 0.05)
        mt, ms = _motion_scores(str(video_path), cfg, progress)
        motion_segs = _scores_to_segments(mt, ms, cfg, cfg.motion_percentile, "motion")
        segments.extend(motion_segs)
        debug["motion_segment_count"] = len(motion_segs)
        debug["motion_threshold_percentile"] = cfg.motion_percentile
        debug["motion_frames"] = int(len(mt))
        _emit(progress, f"运动候选 {len(motion_segs)} 段", 0.45)

    if mode in ("audio", "combined"):
        _emit(progress, "分析击球声（流式 PCM）…", 0.48)
        audio = _audio_rms_scores(str(video_path), cfg, progress)
        if audio is None:
            debug["audio_available"] = False
            if mode == "audio":
                raise RuntimeError("视频无可用音轨，请改用 --mode motion 或 combined（无音轨时仅运动）。")
        else:
            at, asc = audio
            audio_segs = _scores_to_segments(at, asc, cfg, cfg.audio_percentile, "audio")
            segments.extend(audio_segs)
            debug["audio_available"] = True
            debug["audio_segment_count"] = len(audio_segs)

    if cfg.enable_spike_detect:
        spike_count = 0
        if mt is not None and ms is not None and len(ms) > 0:
            m_spikes = _spike_segments_from_signal(
                mt,
                ms,
                cfg,
                percentile=cfg.spike_motion_percentile,
                source="motion",
                neighborhood_sec=0.45,
            )
            segments.extend(m_spikes)
            spike_count += len(m_spikes)
            debug["motion_spike_count"] = len(m_spikes)
        if at is not None and asc is not None and len(asc) > 0:
            a_spikes = _spike_segments_from_signal(
                at,
                asc,
                cfg,
                percentile=cfg.spike_audio_percentile,
                source="audio",
                neighborhood_sec=0.12,
            )
            segments.extend(a_spikes)
            spike_count += len(a_spikes)
            debug["audio_spike_count"] = len(a_spikes)
        debug["spike_segment_total"] = spike_count
        if spike_count:
            _emit(progress, f"尖峰锚定补段 {spike_count} 处", 0.58)

    merged = _merge_segments(segments, cfg.merge_gap_sec)
    final = _pad_and_clip(merged, duration, cfg)
    kept = sum(s.duration() for s in final)
    _emit(progress, f"检测完成：保留 {len(final)} 段 / {kept:.0f}s", 0.62)

    return StrokeDetectResult(
        segments=final,
        duration_sec=duration,
        kept_sec=kept,
        mode=mode,
        debug=debug,
    )


def _mp4_encode_args(*, has_audio: bool) -> list[str]:
    """Windows / 手机播放器兼容：H.264 + yuv420p + faststart。"""
    args = [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    return args


def verify_exported_video(path: str | Path, *, min_duration_sec: float = 0.2) -> None:
    """导出后校验；不可播放则抛错（避免留下 0 字节或损坏文件）。"""
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 1024:
        raise RuntimeError(f"导出文件不存在或过小（{path}，{path.stat().st_size if path.is_file() else 0} B）")
    if shutil.which("ffprobe") is None:
        return
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"导出文件无法被 ffprobe 解析（可能已损坏）: {path}\n{out.stderr[-500:]}")
    try:
        info = json.loads(out.stdout or "{}")
        fmt_d = float((info.get("format") or {}).get("duration") or 0)
        streams = info.get("streams") or []
        if not streams:
            raise RuntimeError(f"导出文件无视频轨: {path}")
        if fmt_d < min_duration_sec:
            raise RuntimeError(f"导出文件时长异常 ({fmt_d:.2f}s): {path}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"无法解析 ffprobe 输出: {path}") from e


def _source_needs_reencode(path: Path) -> bool:
    """iPhone MOV / HEVC 等不宜 filter_complex 直拼，走分段重编码更稳。"""
    if path.suffix.lower() in (".mov", ".m4v", ".hevc"):
        return True
    if not shutil.which("ffprobe"):
        return True
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    codec = (out.stdout or "").strip().lower()
    return codec in ("hevc", "h265", "prores", "av1") or not codec


def _ffmpeg_cut_one(
    src: str,
    start: float,
    end: float,
    out: Path,
    *,
    copy: bool,
    has_audio: bool,
) -> None:
    dur = max(0.05, end - start)
    if copy:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            src,
            "-t",
            f"{dur:.3f}",
            "-c",
            "copy",
            str(out),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{dur:.3f}",
            "-map",
            "0:v:0",
        ]
        if has_audio:
            cmd += ["-map", "0:a:0?"]
        cmd += _mp4_encode_args(has_audio=has_audio)
        cmd.append(str(out))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _ffmpeg_concat_parts(parts: list[Path], output_path: Path, *, has_audio: bool) -> None:
    list_file = output_path.with_suffix(".concat.txt")
    try:
        list_file.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in parts) + "\n",
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
        ]
        cmd += _mp4_encode_args(has_audio=has_audio)
        cmd.append(str(output_path))
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    finally:
        list_file.unlink(missing_ok=True)


def _export_filter_complex_batch(
    src: str,
    segments: list[StrokeSegment],
    output_path: Path,
    *,
    has_audio: bool,
) -> None:
    """单次 ffmpeg filter_complex 拼接一批片段（减少中间文件，适合长视频多段）。"""
    filters: list[str] = []
    v_labels: list[str] = []
    a_labels: list[str] = []
    for i, seg in enumerate(segments):
        s, e = seg.start, seg.end
        filters.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
        v_labels.append(f"[v{i}]")
        if has_audio:
            filters.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
            a_labels.append(f"[a{i}]")
    n = len(segments)
    if has_audio:
        filters.append(f"{''.join(v_labels)}{''.join(a_labels)}concat=n={n}:v=1:a=1[outv][outa]")
        maps = ["-map", "[outv]", "-map", "[outa]"]
    else:
        filters.append(f"{''.join(v_labels)}concat=n={n}:v=1:a=0[outv]")
        maps = ["-map", "[outv]"]
    fc = ";".join(filters)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        src,
        "-filter_complex",
        fc,
        *maps,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
    ]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd.append(str(output_path))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _export_via_segment_concat(
    src: str,
    segments: list[StrokeSegment],
    output_path: Path,
    *,
    has_audio: bool,
    copy: bool,
    progress: ProgressFn,
    batch_size: int,
) -> None:
    """分段切出 → concat 重编码（iPhone MOV / HEVC 最稳）。"""
    with tempfile.TemporaryDirectory(prefix="tenclip_stroke_") as td:
        td_path = Path(td)
        parts: list[Path] = []
        total = len(segments)
        for i, seg in enumerate(segments):
            if progress and i % 2 == 0:
                _emit(progress, f"切片 {i + 1}/{total}…", 0.7 + 0.25 * (i / max(total, 1)))
            part = td_path / f"part_{i:04d}.mp4"
            try:
                _ffmpeg_cut_one(src, seg.start, seg.end, part, copy=copy, has_audio=has_audio)
            except subprocess.CalledProcessError:
                _ffmpeg_cut_one(src, seg.start, seg.end, part, copy=False, has_audio=has_audio)
            verify_exported_video(part, min_duration_sec=0.05)
            parts.append(part)

        if len(parts) > batch_size:
            mid_parts: list[Path] = []
            for b in range(0, len(parts), batch_size):
                batch = parts[b : b + batch_size]
                mid = td_path / f"mid_{b // batch_size:03d}.mp4"
                _ffmpeg_concat_parts(batch, mid, has_audio=has_audio)
                verify_exported_video(mid)
                mid_parts.append(mid)
            parts = mid_parts

        _emit(progress, "拼接导出…", 0.92)
        _ffmpeg_concat_parts(parts, output_path, has_audio=has_audio)


def export_stroke_clips(
    video_path: str | Path,
    segments: list[StrokeSegment],
    output_path: str | Path,
    *,
    copy: bool = False,
    progress: ProgressFn = None,
    batch_size: int = 25,
) -> Path:
    """将多个时间段拼接为一个输出视频。长视频多段时按 batch 用 filter_complex 拼接。"""
    _require_ffmpeg()
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        raise ValueError("没有可导出的片段（检测未命中，可调低 percentile 或换 --mode）")

    has_audio = probe_has_audio(video_path)
    src = str(video_path)
    reencode_src = _source_needs_reencode(video_path)
    if reencode_src:
        copy = False  # MOV/HEVC 禁止 stream copy

    if len(segments) == 1:
        _emit(progress, "导出 1 段…", 0.85)
        _ffmpeg_cut_one(src, segments[0].start, segments[0].end, output_path, copy=copy, has_audio=has_audio)
        verify_exported_video(output_path)
        _emit(progress, "导出完成", 1.0)
        return output_path

    # iPhone MOV / HEVC：跳 filter_complex，分段重编码拼接
    if not copy and not reencode_src and len(segments) <= batch_size:
        _emit(progress, f"ffmpeg 拼接 {len(segments)} 段…", 0.75)
        try:
            _export_filter_complex_batch(src, segments, output_path, has_audio=has_audio)
            verify_exported_video(output_path)
            _emit(progress, "导出完成", 1.0)
            return output_path
        except (subprocess.CalledProcessError, RuntimeError):
            pass

    _export_via_segment_concat(
        src, segments, output_path, has_audio=has_audio, copy=copy, progress=progress, batch_size=batch_size
    )
    verify_exported_video(output_path)
    _emit(progress, "导出完成", 1.0)
    return output_path


def run_stroke_extract_pipeline(
    video_path: str | Path,
    output_path: str | Path,
    *,
    mode: SignalMode = "combined",
    config: StrokeDetectConfig | None = None,
    vlm_filter: bool = False,
    vlm_mode: str = "eco",
    copy: bool = False,
    progress: ProgressFn = None,
) -> StrokeDetectResult:
    """检测 → 可选 VLM 过滤 → 导出击球集锦。"""
    result = detect_stroke_segments(video_path, mode=mode, config=config, progress=progress)
    segments = result.segments

    if vlm_filter and segments:
        _emit(progress, "VLM 二次过滤…", 0.65)
        from services.stroke_vlm_filter import vlm_filter_segments

        def _vlm_prog(msg: str) -> None:
            _emit(progress, msg, 0.7)

        segments, vlm_dbg = vlm_filter_segments(
            str(video_path),
            segments,
            perf_mode=vlm_mode,
            progress=_vlm_prog,
        )
        result.segments = segments
        result.kept_sec = sum(s.duration() for s in segments)
        result.debug["vlm"] = vlm_dbg

    if not segments:
        return result

    _emit(progress, "导出击球集锦…", 0.78)
    export_stroke_clips(video_path, segments, output_path, copy=copy, progress=progress)
    result.debug["output_path"] = str(output_path)
    return result


def segments_to_manifest_rows(
    segments: list[StrokeSegment],
    *,
    video_path: str | Path,
    id_prefix: str = "stroke",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    vp = str(video_path)
    for i, seg in enumerate(segments):
        rows.append(
            {
                "id": f"{id_prefix}_{i:04d}",
                "video_path": vp,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "instruction": "请基于图像序列分析该回合击球动作，输出可执行训练建议。",
                "input": "场景：自动提取的击球/回合片段。\n请按「动作判断 / 关键问题 / 训练计划 / 下次拍摄建议」输出。",
                "output": "",
            }
        )
    return rows


def write_segments_jsonl(rows: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    if path.is_dir():
        raise IsADirectoryError(f"segments 输出必须是文件路径，不能是目录: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
