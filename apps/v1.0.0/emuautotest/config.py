import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
EMULATOR_DIR = BASE_DIR / "emulator" / "azahar-macos-arm64-2126.2"
EMUAUTOTEST_APP = EMULATOR_DIR / "Emuautotest.app"
AZAHAR_BINARY = (EMUAUTOTEST_APP / "Contents" / "MacOS" / "azahar") if EMUAUTOTEST_APP.exists() else (EMULATOR_DIR / "Azahar.app" / "Contents" / "MacOS" / "azahar")
ROMS_DIR = BASE_DIR / "roms"
DEFAULT_ROM = ROMS_DIR / "2048-3D.3dsx"

# Azahar RPC Configuration
AZAHAR_RPC_HOST = "127.0.0.1"
AZAHAR_RPC_PORT = 45987
AZAHAR_INPUT_PORT = 26760

# 3DS Screen Resolutions
TOP_SCREEN_WIDTH = 400
TOP_SCREEN_HEIGHT = 240
BOTTOM_SCREEN_WIDTH = 320
BOTTOM_SCREEN_HEIGHT = 240
COMBINED_WIDTH = 400
COMBINED_HEIGHT = 480
