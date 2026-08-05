from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create placeholder images for mock VLM datasets.")
    p.add_argument("--data-dir", default="data", help="Directory containing dataset json files.")
    p.add_argument("--size", type=int, default=512, help="Placeholder square image size.")
    p.add_argument(
        "--pattern",
        default="mock_tennis_qwen2_vl_mm_*_1k.json",
        help="Glob pattern for dataset files.",
    )
    return p.parse_args()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    files = sorted(data_dir.glob(args.pattern))
    if not files:
        raise SystemExit(f"No dataset files found under {data_dir} matching {args.pattern}")

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise SystemExit("Missing Pillow. Please install: pip install pillow") from e

    made = 0
    for fp in files:
        rows = json.loads(fp.read_text(encoding="utf-8"))
        for i, row in enumerate(rows):
            images = row.get("images") or []
            for img_rel in images:
                img_path = data_dir / img_rel
                if img_path.exists():
                    continue
                _ensure_parent(img_path)
                im = Image.new("RGB", (args.size, args.size), color=(186, 245, 232))  # mint
                draw = ImageDraw.Draw(im)
                text = f"mock\n{fp.name}\n{i}"
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = None
                draw.text((14, 14), text, fill=(21, 24, 33), font=font)
                im.save(img_path, format="JPEG", quality=90)
                made += 1

    print(f"[OK] Created {made} placeholder images under: {data_dir.resolve()}")


if __name__ == "__main__":
    main()
