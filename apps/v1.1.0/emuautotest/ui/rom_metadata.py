import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PIL import Image

from emuautotest.config import RECENT_GAMES_DIR, ROMS_DIR
from emuautotest.core.recent_games_manager import RecentGamesManager, VALID_EXTENSIONS

# 3DS 8x8 tile Morton order LUT
_TILE_ORDER = [
    0, 1, 8, 9, 2, 3, 10, 11,
    16, 17, 24, 25, 18, 19, 26, 27,
    4, 5, 12, 13, 6, 7, 14, 15,
    20, 21, 28, 29, 22, 23, 30, 31,
    32, 33, 40, 41, 34, 35, 42, 43,
    48, 49, 56, 57, 50, 51, 58, 59,
    36, 37, 44, 45, 38, 39, 46, 47,
    52, 53, 60, 61, 54, 55, 62, 63,
]


@dataclass
class RomInfo:
    path: Path
    title: str
    publisher: str
    file_type: str
    size_bytes: int
    icon_image: Optional[Image.Image] = None

    @property
    def size_human(self) -> str:
        val = float(self.size_bytes)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if val < 1024.0:
                return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
            val /= 1024.0
        return f"{val:.1f} TiB"


def _decode_smdh_icon(icon_bytes: bytes) -> Optional[Image.Image]:
    """Decode 48x48 RGB565 Morton-tiled SMDH large icon into a PIL Image."""
    if len(icon_bytes) < 48 * 48 * 2:
        return None

    img = Image.new("RGB", (48, 48))
    pixels = img.load()

    # 48x48 = 6x6 tiles of 8x8 pixels
    tile_idx = 0
    for ty in range(6):
        for tx in range(6):
            tile_offset = tile_idx * 64 * 2
            for i in range(64):
                morton = _TILE_ORDER[i]
                px = tx * 8 + (morton & 7)
                py = ty * 8 + (morton >> 3)
                off = tile_offset + i * 2
                rgb565 = struct.unpack_from("<H", icon_bytes, off)[0]
                r = ((rgb565 >> 11) & 0x1F) * 255 // 31
                g = ((rgb565 >> 5) & 0x3F) * 255 // 63
                b = (rgb565 & 0x1F) * 255 // 31
                pixels[px, py] = (r, g, b)
            tile_idx += 1

    return img


def parse_3dsx_smdh(rom_path: Path) -> Optional[tuple[str, str, Optional[Image.Image]]]:
    """Extract (title, publisher, icon_image) from a .3dsx file's SMDH block."""
    try:
        with open(rom_path, "rb") as f:
            header = f.read(44)
            if len(header) < 44 or header[:4] != b"3DSX":
                return None
            header_size = struct.unpack_from("<H", header, 4)[0]
            if header_size < 44:
                return None
            smdh_offset, smdh_size = struct.unpack_from("<II", header, 0x20)
            if smdh_offset == 0 or smdh_size < 0x36C0:
                return None

            f.seek(smdh_offset)
            smdh = f.read(0x36C0)
            if len(smdh) < 0x36C0 or smdh[:4] != b"SMDH":
                return None

            # English title is slot 1 (offset 0x08 + 0x200), fallback to slot 0 (0x08)
            title = ""
            publisher = ""
            for slot in (1, 0):
                base = 0x08 + slot * 0x200
                short_desc = smdh[base : base + 128].decode("utf-16le", errors="ignore").rstrip("\x00").strip()
                pub = smdh[base + 384 : base + 512].decode("utf-16le", errors="ignore").rstrip("\x00").strip()
                if short_desc:
                    title = short_desc
                    publisher = pub
                    break

            icon = _decode_smdh_icon(smdh[0x24C0 : 0x24C0 + 48 * 48 * 2])
            return title, publisher, icon
    except Exception:
        return None


def inspect_rom(rom_path: Path) -> RomInfo:
    """Build RomInfo for any supported 3DS ROM file."""
    resolved = rom_path.resolve()
    title = resolved.stem
    publisher = ""
    icon_image = None

    if resolved.suffix.lower() == ".3dsx":
        parsed = parse_3dsx_smdh(resolved)
        if parsed:
            parsed_title, parsed_pub, parsed_icon = parsed
            if parsed_title:
                title = parsed_title
            publisher = parsed_pub
            icon_image = parsed_icon

    size_bytes = resolved.stat().st_size if resolved.exists() else 0
    return RomInfo(
        path=resolved,
        title=title,
        publisher=publisher,
        file_type=resolved.suffix.lstrip(".").upper(),
        size_bytes=size_bytes,
        icon_image=icon_image,
    )


def discover_all_roms() -> List[RomInfo]:
    """Discover all unique ROMs from bundled ROMS_DIR and recent files."""
    seen_paths = set()
    seen_names = set()
    roms: List[RomInfo] = []

    candidates: List[Path] = []
    if ROMS_DIR.exists():
        for p in sorted(ROMS_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS:
                candidates.append(p)

    mgr = RecentGamesManager()
    candidates.extend(mgr.get_recent_roms())

    if RECENT_GAMES_DIR.exists():
        for p in sorted(RECENT_GAMES_DIR.iterdir()):
            if p.exists() and p.suffix.lower() in VALID_EXTENSIONS:
                candidates.append(p)

    for p in candidates:
        res = p.resolve()
        if not res.exists() or res in seen_paths or res.name in seen_names:
            continue
        seen_paths.add(res)
        seen_names.add(res.name)
        roms.append(inspect_rom(res))

    return roms


def discover_recent_roms(limit: int = 5) -> List[RomInfo]:
    """Discover the top N recently played ROMs."""
    mgr = RecentGamesManager(max_games=limit)
    return [inspect_rom(p) for p in mgr.get_recent_roms()[:limit]]
