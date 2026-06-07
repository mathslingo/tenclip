from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Qwen2-VL multimodal SFT/DPO datasets from local videos.")
    p.add_argument("--manifest", required=True, help="JSONL manifest file path.")
    p.add_argument("--out", required=True, help="Output dataset json path (under data/).")
    p.add_argument("--data-dir", default="data", help="Data directory (image paths are relative to this).")
    p.add_argument("--image-root", default="vlm_images", help="Image root directory under data-dir.")
    p.add_argument("--num-frames", type=int, default=4, help="Frames per video sample.")
    p.add_argument("--max-side", type=int, default=384, help="Resize longest side to this.")
    p.add_argument("--max-sec", type=float, default=300.0, help="Max seconds analyzed per video.")
    p.add_argument("--mode", choices=["sft", "dpo"], default="sft", help="Output dataset type.")
    p.add_argument(
        "--register-key",
        default="",
        help="If set, append/update this key in dataset_info.json (LLaMA-Factory dataset name).",
    )
    p.add_argument(
        "--dataset-info",
        default="",
        help="Path to dataset_info.json (default: <data-dir>/dataset_info.json).",
    )
    p.add_argument("--limit", type=int, default=0, help="Only process first N rows (0=all); handy for trial runs.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manifest (video_path exists, fields present) and preview first sample; no frame/dataset output.",
    )
    return p.parse_args()


def _required_fields(mode: str) -> tuple[str, ...]:
    return ("instruction", "output") if mode == "sft" else ("instruction", "chosen", "rejected")


def _validate_manifest(rows: List[Dict[str, Any]], mode: str, single_video: str = "") -> List[str]:
    """返回问题列表（空=通过）。检查 video_path 存在与必填标注字段。"""
    problems: List[str] = []
    req = _required_fields(mode)
    for i, r in enumerate(rows):
        sid = r.get("id") or f"row_{i}"
        vp = r.get("video_path") or single_video
        if not vp:
            problems.append(f"[{sid}] 缺少 video_path")
        elif not Path(vp).is_file():
            problems.append(f"[{sid}] 视频文件不存在: {vp}")
        for k in req:
            if not str(r.get(k, "")).strip():
                problems.append(f"[{sid}] 缺少必填字段 {k!r}（mode={mode}）")
    return problems


def _load_manifest(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        rows.append(json.loads(ln))
    return rows


def _save_jpgs(images: List[Any], out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for i, im in enumerate(images):
        p = out_dir / f"frame_{i:02d}.jpg"
        im.save(p, format="JPEG", quality=90)
        paths.append(p)
    return paths


def _dataset_file_name_for_info(out_path: Path, data_dir: Path) -> tuple[str, bool]:
    """返回 (file_name, 是否在 data_dir 下)。LLaMA-Factory 的 file_name 一般为相对 dataset_dir 的路径。"""
    try:
        rel = out_path.resolve().relative_to(data_dir.resolve())
        return str(rel).replace("\\", "/"), True
    except ValueError:
        return out_path.name, False


def _register_in_dataset_info(
    *,
    dataset_info_path: Path,
    key: str,
    mode: str,
    file_name: str,
) -> None:
    if not key.strip():
        return
    key = key.strip()
    if not dataset_info_path.exists():
        info: Dict[str, Any] = {}
    else:
        info = json.loads(dataset_info_path.read_text(encoding="utf-8"))

    if mode == "sft":
        entry: Dict[str, Any] = {
            "file_name": file_name,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "images": "images",
            },
        }
    else:
        entry = {
            "file_name": file_name,
            "ranking": True,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "chosen": "chosen",
                "rejected": "rejected",
                "images": "images",
            },
        }

    if key in info:
        print(f"[WARN] dataset_info.json already has key {key!r}; overwriting.")
    info[key] = entry
    dataset_info_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Registered dataset key {key!r} in {dataset_info_path.resolve()}")


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    data_dir = Path(args.data_dir)
    image_root = Path(args.image_root)

    rows = _load_manifest(manifest_path)
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    if args.dry_run:
        problems = _validate_manifest(rows, args.mode)
        print(f"[dry-run] manifest 行数: {len(rows)}  模式: {args.mode}")
        if problems:
            print(f"[dry-run] 发现 {len(problems)} 个问题：")
            for p in problems[:50]:
                print("  - " + p)
            if len(problems) > 50:
                print(f"  ... 其余 {len(problems) - 50} 条略")
        else:
            print("[dry-run] 校验通过：video_path 均存在，必填字段齐全。")
        if rows:
            sample = rows[0]
            preview = {
                "id": sample.get("id"),
                "video_path": sample.get("video_path"),
                "instruction": (str(sample.get("instruction", ""))[:60]),
                "num_frames_plan": int(args.num_frames),
            }
            print("[dry-run] 首条样本预览:", json.dumps(preview, ensure_ascii=False))
        print("[dry-run] 未抽帧、未写数据集、未改 dataset_info.json。")
        return

    try:
        # 复用项目内抽帧逻辑（保证与线上推理帧策略一致）
        from services.vlm_tennis import sample_frames
    except Exception as e:
        raise SystemExit(f"Failed to import sample_frames from services.vlm_tennis: {e}") from e

    out_rows: List[Dict[str, Any]] = []

    for r in rows:
        video_path = r.get("video_path")
        if not video_path:
            raise SystemExit("manifest row missing video_path")

        # 每条样本一个目录，避免文件名冲突
        sample_id = r.get("id") or uuid.uuid4().hex
        out_dir = data_dir / image_root / sample_id

        images, _ = sample_frames(
            video_path=str(video_path),
            max_duration_sec=float(args.max_sec),
            num_frames=int(args.num_frames),
            max_side=int(args.max_side),
        )
        img_paths = _save_jpgs(images, out_dir)
        rel_imgs = [str(p.relative_to(data_dir)).replace("\\", "/") for p in img_paths]

        instruction = r.get("instruction", "")
        input_text = r.get("input", "")

        if args.mode == "sft":
            output = r.get("output", "")
            out_rows.append(
                {
                    "instruction": instruction,
                    "input": input_text,
                    "output": output,
                    "images": rel_imgs,
                }
            )
        else:
            chosen = r.get("chosen", "")
            rejected = r.get("rejected", "")
            out_rows.append(
                {
                    "instruction": instruction,
                    "input": input_text,
                    "chosen": chosen,
                    "rejected": rejected,
                    "images": rel_imgs,
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {len(out_rows)} rows -> {out_path.resolve()}")

    if args.register_key:
        info_path = Path(args.dataset_info) if args.dataset_info else data_dir / "dataset_info.json"
        file_name, under_data = _dataset_file_name_for_info(out_path, data_dir)
        if not under_data:
            print(
                "[WARN] --out 不在 --data-dir 下：dataset_info 的 file_name 仅写为文件名；"
                "建议把 --out 设为 data/ 下的路径，例如 data/tennis_vlm_sft.json"
            )
        _register_in_dataset_info(
            dataset_info_path=info_path,
            key=args.register_key,
            mode=args.mode,
            file_name=file_name,
        )


if __name__ == "__main__":
    main()

