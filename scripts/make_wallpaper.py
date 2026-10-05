"""Verifica se as imagens padrão 4:3 e 16:9 estão presentes.

As imagens de marca ficam em:
  assets/wallpaper/desktop-4x3.jpg
  assets/wallpaper/desktop-16x9.jpg
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = (
    ROOT / "assets" / "wallpaper" / "desktop-4x3.jpg",
    ROOT / "assets" / "wallpaper" / "desktop-16x9.jpg",
)


def main() -> int:
    missing = [p for p in REQUIRED if not p.exists()]
    if missing:
        print("Imagens ausentes:", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 1
    for p in REQUIRED:
        print(f"OK {p.name} ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
