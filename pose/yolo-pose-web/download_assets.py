#!/usr/bin/env python3
"""Download sample assets for the Safari demo (bus.jpg)."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

BUS_URL = "https://ultralytics.com/images/bus.jpg"


def main() -> None:
    root = Path(__file__).resolve().parent
    dest = root / "assets" / "bus.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {BUS_URL} → {dest}")
    urlretrieve(BUS_URL, dest)
    print(f"OK {dest.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
