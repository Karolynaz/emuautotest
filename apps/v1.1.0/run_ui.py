#!/usr/bin/env python3
"""Entry point for the Emuautotest Native macOS Desktop UI."""

import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import PySide6

# Qt 6's QDir cannot enumerate plugins inside macOS iCloud Drive FileProvider folders;
# mirror Qt plugins to ~/Library/Application Support/Emuautotest/qt_plugins if needed.
_src_plugins = Path(PySide6.__file__).resolve().parent / "Qt" / "plugins"
_local_plugins = Path.home() / "Library" / "Application Support" / "Emuautotest" / "qt_plugins"
if _src_plugins.exists():
    if not (_local_plugins / "platforms" / "libqcocoa.dylib").exists():
        _local_plugins.parent.mkdir(parents=True, exist_ok=True)
        if _local_plugins.exists():
            shutil.rmtree(_local_plugins)
        shutil.copytree(_src_plugins, _local_plugins)
    os.environ["QT_PLUGIN_PATH"] = str(_local_plugins)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(_local_plugins / "platforms")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from emuautotest.ui.main_window import EmuautotestMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Emuautotest")
    app.setOrganizationName("Emuautotest")

    icon_path = BASE_DIR / "icon.jpg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = EmuautotestMainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
