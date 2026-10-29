#!/usr/bin/env python3
"""
Automated gameplay recording session for Diablo 3DS (DevilutionX).
Captures full dual-screen 3DS footage from launch to town exploration,
NPC interaction, dungeon approach, and combat.
"""

import sys
import time
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from emuautotest.adapters.azahar_3ds import Azahar3DSAdapter
from emuautotest.config import RECORDINGS_DIR


def record_diablo_mission():
    print("=" * 60)
    print("🎬 Starting Diablo 3DS Gameplay Recording Mission...")
    print("=" * 60)

    adapter = Azahar3DSAdapter()
    rom_path = BASE_DIR / "roms" / "devil-3ds.3dsx"
    output_video = RECORDINGS_DIR / "diablo3ds_gameplay_mission.mp4"

    # 1. Start Emulator
    print(f"\n[1/8] Launching Diablo 3DS ({rom_path.name})...")
    adapter.launch(str(rom_path))
    time.sleep(1.0)

    # 2. Start Video Recording immediately to capture intro
    print(f"\n[2/8] Starting dual-screen 30 FPS video recording...")
    rec_info = adapter.start_recording(
        target="both",
        fps=30,
        format="mp4",
        scale=1,
        output_path=str(output_video),
    )
    print(f"  -> Recording to: {rec_info['file_name']}")

    # 3. Skip intro movies to reach Hellfire Title Menu
    print("\n[3/8] Skipping intro logos/cinematics...")
    for i in range(16):
        time.sleep(0.5)
        adapter.press_button("A", duration_ms=50)

    time.sleep(1.0)

    # 4. Select Single Player & Character
    print("\n[4/8] Navigating menus & selecting character...")
    # Select Single Player
    adapter.press_button("A", duration_ms=100)
    time.sleep(1.5)

    # Select Hero from list
    adapter.press_button("A", duration_ms=100)
    time.sleep(1.0)

    # Select Normal Difficulty
    adapter.press_button("A", duration_ms=100)
    time.sleep(1.0)

    # Loop A to pass difficulty confirmation & enter loading screen
    print("\n[5/8] Loading Tristram...")
    for _ in range(16):
        time.sleep(0.8)
        adapter.press_button("A", duration_ms=60)

    # Wait for town assets to settle
    time.sleep(2.0)
    status = adapter.get_status()
    print(f"  -> Tristram loaded! FPS: {status.game_fps}")

    # 6. Walk through Tristram across the bridge into town square
    print("\n[6/8] Exploring Tristram & navigating across bridge...")
    # Walk down-right to path
    adapter.circle_pad("DOWN_RIGHT", duration_ms=1500)
    time.sleep(0.3)

    # Walk right across the wooden bridge
    adapter.circle_pad("RIGHT", duration_ms=3500)
    time.sleep(0.3)

    # Walk up-right into town center
    adapter.circle_pad("UP_RIGHT", duration_ms=2500)
    time.sleep(0.5)

    # 7. Interact with Town NPC & Combat Actions
    print("\n[7/8] Interacting with NPC & combat simulation...")
    # Talk to NPC (Cain / Griswold)
    adapter.press_button("A", duration_ms=150)
    time.sleep(2.5)

    # Close dialog if open or continue
    adapter.press_button("B", duration_ms=100)
    time.sleep(0.5)

    # Perform attack swings / arrow shots
    for _ in range(6):
        adapter.press_button("A", duration_ms=150)
        time.sleep(0.4)

    # Walk north towards church / labyrinth path
    adapter.circle_pad("UP", duration_ms=3000)
    time.sleep(0.5)

    # Attack enemies along path
    for _ in range(8):
        adapter.press_button("A", duration_ms=120)
        time.sleep(0.35)

    # Return down towards town center
    adapter.circle_pad("DOWN", duration_ms=2500)
    time.sleep(0.5)

    # Talk to NPC again
    adapter.press_button("A", duration_ms=150)
    time.sleep(2.0)
    adapter.press_button("B", duration_ms=100)
    time.sleep(1.0)

    # 8. Finalize Video Recording
    print("\n[8/8] Finalizing video recording & stopping emulator...")
    rec_result = adapter.stop_recording()
    adapter.stop()

    print("\n" + "=" * 60)
    print("🎉 MISSION COMPLETE! Video Exported Successfully!")
    print(f"File Name: {rec_result['file_name']}")
    print(f"File Path: {rec_result['file_path']}")
    print(f"Duration:  {rec_result['duration_seconds']} seconds")
    print(f"Frames:    {rec_result['frame_count']} ({rec_result['fps']} FPS)")
    print(f"Size:      {rec_result['file_size_human']}")
    print("=" * 60)
    return rec_result


if __name__ == "__main__":
    record_diablo_mission()
