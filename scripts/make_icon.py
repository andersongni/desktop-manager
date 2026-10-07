"""Gera app.png e app.ico a partir do artwork em assets/icon/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icon"


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("Instale Pillow: pip install pillow", file=sys.stderr)
        return 1

    src_candidates = [
        ICON_DIR / "desktop-manager-icon.png",
        ICON_DIR / "desktop-manager-icon.jpg",
        ICON_DIR / "app.png",
    ]
    src = next((p for p in src_candidates if p.exists()), None)
    if src is None:
        print(f"Artwork não encontrado em {ICON_DIR}", file=sys.stderr)
        return 1

    img = Image.open(src).convert("RGBA")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    png = ICON_DIR / "app.png"
    img.resize((256, 256), Image.Resampling.LANCZOS).save(png, format="PNG")

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icons = [img.resize(s, Image.Resampling.LANCZOS) for s in sizes]
    ico = ICON_DIR / "app.ico"
    icons[-1].save(ico, format="ICO", sizes=sizes)

    print(f"OK: {png}")
    print(f"OK: {ico}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
