#!/usr/bin/env python3
"""Export Ultralytics YOLO11n-pose (or v8n-pose) to ONNX for the Safari demo.

Usage:
  pip install ultralytics
  python export_onnx.py
  python export_onnx.py --model yolov8n-pose.pt --imgsz 416

Output:
  models/yolo11n-pose.onnx   (or renamed to match --out)
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="yolo11n-pose.pt", help="Ultralytics pose weights")
    p.add_argument("--imgsz", type=int, default=640, choices=[320, 384, 416, 640])
    p.add_argument("--out", default="", help="Destination .onnx path")
    args = p.parse_args()

    from ultralytics import YOLO

    root = Path(__file__).resolve().parent
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.model} …")
    model = YOLO(args.model)
    print(f"Export ONNX imgsz={args.imgsz} …")
    out_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        simplify=True,
        opset=12,
        dynamic=False,
    )
    src = Path(out_path)
    dst = Path(args.out) if args.out else models_dir / f"{src.stem}.onnx"
    if not dst.is_absolute():
        dst = root / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        dst.write_bytes(src.read_bytes())
        print(f"Copied → {dst} ({dst.stat().st_size / 1e6:.2f} MB)")
    else:
        print(f"Saved → {dst}")

    print("Demo: open index.html via HTTPS/localhost, then tap Start on iPhone.")


if __name__ == "__main__":
    main()
