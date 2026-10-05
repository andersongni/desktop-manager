"""Gera um plano de fundo BMP de exemplo (sem dependências)."""

from __future__ import annotations

import struct
from pathlib import Path


def write_gradient_bmp(path: Path, width: int = 1920, height: int = 1080) -> None:
    row_padded = (width * 3 + 3) & ~3
    pixel_size = row_padded * height
    file_size = 54 + pixel_size

    header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0,
        0,
        54,
    )
    dib = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height,
        1,
        24,
        0,
        pixel_size,
        2835,
        2835,
        0,
        0,
    )

    pixels = bytearray()
    for y in range(height):
        row = bytearray()
        for x in range(width):
            # Gradiente azul-petróleo → cinza-azulado (BGR)
            t = x / max(width - 1, 1)
            u = y / max(height - 1, 1)
            b = int(40 + 50 * (1 - t) + 20 * u)
            g = int(55 + 40 * t + 30 * (1 - u))
            r = int(30 + 25 * t)
            # Faixa inferior sutil
            if y < 80:
                r = min(255, r + 15)
                g = min(255, g + 10)
            row += bytes((b, g, r))
        row += b"\x00" * (row_padded - width * 3)
        pixels += row

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + dib + pixels)

    # Também salva como desktop.bmp; o config aponta para .jpg —
    # criamos desktop.jpg como cópia do bmp (Windows aceita ambos na API)
    # Preferimos apontar config para .bmp gerado.
    print(f"Gerado: {path} ({width}x{height})")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    out = root / "assets" / "wallpaper" / "desktop.bmp"
    write_gradient_bmp(out)
    # Atualiza settings para usar o bmp se jpg não existir
    jpg = root / "assets" / "wallpaper" / "desktop.jpg"
    if not jpg.exists():
        import json

        cfg = root / "config" / "settings.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["wallpaper"]["image"] = "assets/wallpaper/desktop.bmp"
        cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("settings.json atualizado para desktop.bmp")
