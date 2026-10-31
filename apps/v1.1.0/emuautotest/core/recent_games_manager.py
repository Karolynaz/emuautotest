import os
import re
from pathlib import Path
from typing import List, Optional

VALID_EXTENSIONS = {".3dsx", ".3ds", ".cci", ".cxi", ".elf", ".axf", ".app"}
DEFAULT_CONFIG_PATH = Path.home() / "Library" / "Application Support" / "Azahar" / "config" / "qt-config.ini"
DEFAULT_RECENT_DIR = Path.home() / "Library" / "Application Support" / "Azahar" / "recent_games"


class RecentGamesManager:
    """Manages the 5 most recently played ROMs and ensures they are displayed

    in the emulator's initial startup window game list without requiring manual menu navigation.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        recent_dir: Optional[Path] = None,
        max_games: int = 5,
    ):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.recent_dir = recent_dir or DEFAULT_RECENT_DIR
        self.max_games = max_games

    def get_recent_roms(self) -> List[Path]:
        """Read and return valid, unique recent ROM paths in recency order."""
        if not self.config_path.exists():
            return []

        recent: List[Path] = []
        seen_names = set()

        try:
            with open(self.config_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("Paths\\recentFiles="):
                        val = line.split("=", 1)[1].strip()
                        parts = [p.strip() for p in val.split(",") if p.strip()]
                        for item in parts:
                            p = Path(item).resolve()
                            if (
                                p.exists()
                                and p.is_file()
                                and p.suffix.lower() in VALID_EXTENSIONS
                                and p.name not in seen_names
                            ):
                                seen_names.add(p.name)
                                recent.append(p)
                        break
        except Exception:
            pass

        return recent

    def sync(self, active_rom: Optional[Path] = None) -> List[Path]:
        """Synchronize the recent_games directory symlinks and qt-config.ini

        so that the initial game list table always lists the latest 5 games.
        """
        self.recent_dir.mkdir(parents=True, exist_ok=True)

        current_recents = self.get_recent_roms()

        all_roms: List[Path] = []
        seen_names = set()

        if active_rom:
            p_act = Path(active_rom).resolve()
            if p_act.exists() and p_act.is_file():
                seen_names.add(p_act.name)
                all_roms.append(p_act)

        for r in current_recents:
            if r.name not in seen_names:
                seen_names.add(r.name)
                all_roms.append(r)

        top_games = all_roms[: self.max_games]

        # Clean existing symlinks/files in recent_dir
        try:
            for item in self.recent_dir.iterdir():
                try:
                    if item.is_symlink() or item.is_file():
                        item.unlink()
                except Exception:
                    pass
        except Exception:
            pass

        # Create fresh symlinks for the top 5 games
        created_links: List[Path] = []
        for idx, game in enumerate(top_games, 1):
            target_link = self.recent_dir / game.name
            if target_link.exists():
                target_link = self.recent_dir / f"{idx}_{game.name}"
            try:
                target_link.symlink_to(game)
                created_links.append(target_link)
            except Exception:
                pass

        # Update qt-config.ini to register recent_games in Paths\gamedirs
        self._update_qt_config(top_games)

        return top_games

    def _update_qt_config(self, top_games: List[Path]) -> None:
        """Update qt-config.ini with recentFiles and ensure recent_games is in gamedirs."""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            recent_str = ", ".join(str(p) for p in top_games)
            recent_dir_str = str(self.recent_dir.resolve())

            new_lines: List[str] = []
            has_recent_dir = False
            gamedirs_indices = []

            for line in lines:
                if line.startswith("Paths\\recentFiles="):
                    new_lines.append(f"Paths\\recentFiles={recent_str}\n")
                    continue

                # Remove legacy dummy dirs like .../rrrr
                if "/rrrr" in line:
                    continue

                if line.startswith("Paths\\gamedirs\\"):
                    m = re.match(r"^Paths\\gamedirs\\(\d+)\\path=(.*)$", line.strip())
                    if m:
                        idx = int(m.group(1))
                        path_val = m.group(2)
                        gamedirs_indices.append(idx)
                        if path_val == recent_dir_str:
                            has_recent_dir = True

                new_lines.append(line)

            # Ensure recent_games is configured in Paths\gamedirs
            if not has_recent_dir:
                next_idx = max(gamedirs_indices) + 1 if gamedirs_indices else 3
                # Insert recent_games directory configuration
                insert_block = [
                    f"Paths\\gamedirs\\{next_idx}\\deep_scan=false\n",
                    f"Paths\\gamedirs\\{next_idx}\\deep_scan\\default=true\n",
                    f"Paths\\gamedirs\\{next_idx}\\expanded=true\n",
                    f"Paths\\gamedirs\\{next_idx}\\expanded\\default=true\n",
                    f"Paths\\gamedirs\\{next_idx}\\path={recent_dir_str}\n",
                ]

                # Find Paths\gamedirs\size line or append before Paths\inserted_cartridge
                inserted = False
                final_lines: List[str] = []
                for line in new_lines:
                    if line.startswith("Paths\\gamedirs\\size="):
                        final_lines.extend(insert_block)
                        curr_size = int(line.strip().split("=")[1])
                        new_size = max(curr_size, next_idx)
                        final_lines.append(f"Paths\\gamedirs\\size={new_size}\n")
                        inserted = True
                    else:
                        final_lines.append(line)

                if not inserted:
                    final_lines.extend(insert_block)
                new_lines = final_lines

            with open(self.config_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

        except Exception:
            pass
