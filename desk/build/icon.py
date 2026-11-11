"""Equion Desk 의 아이콘 파일을 만든다 — `desk/equion_desk/assets/equion-desk.ico` (저장소에 넣어 둔다. 다시 만들 일은 그림을 바꿀 때뿐이다).

    uv run python desk/build/icon.py            # .ico 를 다시 쓴다
    uv run python desk/build/icon.py --check    # 저장소의 것이 이 코드가 만드는 것과 같은지

그림은 화면의 상표(web/js/icons.js 의 LOGO, web/img/icon.svg)와 같다: 청록 둥근 네모 위에 흰 가로줄 셋(항등 '≡'이자 E)과 노란 점 하나.
다른 프로그램의 아이콘을 옮기지 않고 새로 그렸다(DECISIONS D13). 그리는 도구 없이 여기서 점을 찍는다 — 의존성을 늘리지 않으려고.
작은 크기(16~24)는 줄을 굵게, 여백을 좁게 한 그림을 따로 쓴다(그대로 줄이면 줄이 뭉개진다).
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "equion_desk" / "assets" / "equion-desk.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
TOP, BOTTOM = (0x16, 0x91, 0x8A), (0x07, 0x54, 0x50)
WHITE, DOT = (255, 255, 255), (0xFF, 0xD2, 0x7A)

# (x, y, 폭, 높이, 모서리 반지름) — 64×64 자리 기준
LARGE = {"tile": (4, 4, 56, 56, 14), "bars": [(17, 18, 30, 6, 3), (17, 29, 19, 6, 3), (17, 40, 30, 6, 3)], "dot": (44, 32, 3.6)}
SMALL = {"tile": (2, 2, 60, 60, 13), "bars": [(14, 14, 36, 8, 3), (14, 28, 22, 8, 3), (14, 42, 36, 8, 3)], "dot": (45, 32, 4.6)}


def in_round_rect(x: float, y: float, box: tuple) -> bool:
    x0, y0, w, h, r = box
    if not (x0 <= x <= x0 + w and y0 <= y <= y0 + h):
        return False
    cx = min(max(x, x0 + r), x0 + w - r)
    cy = min(max(y, y0 + r), y0 + h - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def sample(x: float, y: float, art: dict) -> tuple[int, int, int] | None:
    """64×64 자리의 한 점의 색(그림 밖이면 None)."""
    if not in_round_rect(x, y, art["tile"]):
        return None
    cx, cy, r = art["dot"]
    if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
        return DOT
    if any(in_round_rect(x, y, bar) for bar in art["bars"]):
        return WHITE
    t = min(1.0, max(0.0, (x + y - 8) / 112))
    return tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))  # type: ignore[return-value]


def render(size: int) -> bytes:
    """size×size 그림의 RGBA 바이트(위에서 아래로). 점 하나를 여러 번 찍어 가장자리를 부드럽게 한다."""
    art = SMALL if size <= 24 else LARGE
    n = 8 if size <= 48 else 4
    scale = 64 / size
    out = bytearray()
    for py in range(size):
        for px in range(size):
            r = g = b = hits = 0
            for sy in range(n):
                for sx in range(n):
                    color = sample((px + (sx + 0.5) / n) * scale, (py + (sy + 0.5) / n) * scale, art)
                    if color is not None:
                        r, g, b, hits = r + color[0], g + color[1], b + color[2], hits + 1
            if hits:
                out += bytes((round(r / hits), round(g / hits), round(b / hits), round(255 * hits / (n * n))))
            else:
                out += b"\0\0\0\0"
    return bytes(out)


def png(size: int, rgba: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = b"".join(b"\0" + rgba[y * size * 4:(y + 1) * size * 4] for y in range(size))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def dib(size: int, rgba: bytes) -> bytes:
    """아이콘 안의 비트맵(32비트 BGRA, 아래에서 위로) + 빈 마스크 — 작은 크기는 PNG 를 읽지 못하는 곳이 있다."""
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = bytearray()
    for y in range(size - 1, -1, -1):
        row = rgba[y * size * 4:(y + 1) * size * 4]
        for x in range(size):
            r, g, b, a = row[x * 4:x * 4 + 4]
            pixels += bytes((b, g, r, a))
    mask = b"\0" * (((size + 31) // 32) * 4 * size)
    return header + bytes(pixels) + mask


def build() -> bytes:
    images = []
    for size in SIZES:
        rgba = render(size)
        images.append((size, png(size, rgba) if size >= 128 else dib(size, rgba)))
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for size, data in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return head + entries + b"".join(data for _, data in images)


def main() -> int:
    ap = argparse.ArgumentParser(description="Equion Desk 아이콘 만들기")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 저장소의 것과 견준다")
    args = ap.parse_args()
    data = build()
    if args.check:
        same = OUT.is_file() and OUT.read_bytes() == data
        print("같음" if same else f"다름 — python desk/build/icon.py 로 다시 만드세요: {OUT}")
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(data)
    print(f"{OUT} ({len(data) / 1024:.0f}KB, {len(SIZES)}개 크기)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
