#!/usr/bin/env python3
"""Export Ultralytics YOLO detect ONNX for tennis / sports-ball demo.

Uses COCO pretrained nano detect (class 32 = sports ball) as v1 tennis proxy
until a fine-tuned single-class tennis model is available.

Usage (mmpose_gpu):
  conda activate mmpose_gpu
  cd pose/yolo-pose-web
  python export_tennis_onnx.py
  python export_tennis_onnx.py --model yolov8n.pt --imgsz 640

Output:
  models/yolo11n-tennis.onnx
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--model",
        default="yolo11n.pt",
        help="Ultralytics detect weights (COCO). sports ball = class 32",
    )
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
    dst = Path(args.out) if args.out else models_dir / "yolo11n-tennis.onnx"
    if not dst.is_absolute():
        dst = root / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    print(f"Copied → {dst} ({dst.stat().st_size / 1e6:.2f} MB)")
    print("Frontend filters COCO class 32 (sports ball) as tennis proxy.")
    print("Demo: enable「网球」in the page after placing the onnx under models/.")


if __name__ == "__main__":
    main()
