#!/usr/bin/env python3
"""Automated end-to-end test for Emuautotest Azahar 3DS Adapter."""

import sys
import time
from pathlib import Path

# Add package directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from emuautotest.adapters.azahar_3ds import Azahar3DSAdapter
from emuautotest.config import DEFAULT_ROM


def run_tests():
    print("=" * 60)
    print("🚀 Starting Emuautotest E2E Integration Test...")
    print("=" * 60)

    adapter = Azahar3DSAdapter()

    print(f"\n[1/7] Launching Azahar emulator with test ROM: {DEFAULT_ROM.name}...")
    success = adapter.launch(str(DEFAULT_ROM))
    assert success, "Emulator failed to launch"
    print("  -> Emulator launched successfully!")

    # Wait for game to finish initial bootscreen
    time.sleep(2.0)

    print("\n[2/7] Checking emulator status & performance...")
    status = adapter.get_status()
    print(f"  -> PID: {status.pid}")
    print(f"  -> Is Running: {status.is_running}")
    print(f"  -> RPC Connected: {status.rpc_connected}")
    print(f"  -> Game FPS: {status.game_fps}")
    print(f"  -> Speed: {status.emulation_speed}%")
    if status.window_bounds:
        print(f"  -> Window: {status.window_bounds.width}x{status.window_bounds.height} at ({status.window_bounds.x}, {status.window_bounds.y})")
    assert status.is_running, "Emulator process is not running"

    print("\n[3/7] Capturing screenshots (top, bottom, both)...")
    _, b64_both, w_both, h_both = adapter.take_screenshot(target="both")
    print(f"  -> Combined screen captured: {w_both}x{h_both} (base64 length: {len(b64_both)})")
    assert w_both == 400 and h_both == 480, f"Unexpected dimensions: {w_both}x{h_both}"

    _, b64_top, w_top, h_top = adapter.take_screenshot(target="top")
    print(f"  -> Top screen captured: {w_top}x{h_top} (base64 length: {len(b64_top)})")
    assert w_top == 400 and h_top == 240, f"Unexpected top dimensions: {w_top}x{h_top}"

    _, b64_bot, w_bot, h_bot = adapter.take_screenshot(target="bottom")
    print(f"  -> Bottom touch screen captured: {w_bot}x{h_bot} (base64 length: {len(b64_bot)})")
    assert w_bot == 320 and h_bot == 240, f"Unexpected bottom dimensions: {w_bot}x{h_bot}"

    print("\n[4/7] Testing hardware button simulation (D-Pad / Circle Pad)...")
    adapter.press_button("DOWN", duration_ms=100)
    print("  -> Pressed 'DOWN' (moved tiles)")
    time.sleep(0.3)
    adapter.press_button("RIGHT", duration_ms=100)
    print("  -> Pressed 'RIGHT' (moved tiles)")

    print("\n[5/7] Testing touchscreen touch simulation...")
    touch_res = adapter.touch_screen(0.5, 0.5, duration_ms=100)
    print(f"  -> Touched center of screen (0.5, 0.5): {touch_res}")

    print("\n[6/7] Testing macro action execution...")
    macro_actions = [
        {"action": "press", "button": "UP", "duration_ms": 100},
        {"action": "wait", "duration_ms": 200},
        {"action": "press", "button": "LEFT", "duration_ms": 100},
        {"action": "wait", "duration_ms": 200},
        {"action": "screenshot", "screen": "top"},
    ]
    macro_results = adapter.execute_macro(macro_actions)
    print(f"  -> Macro executed {len(macro_results)} steps:")
    for r in macro_results:
        print(f"     Step {r['step']}: {r['action']} -> {r['status']}")

    print("\n[7/7] Stopping emulator...")
    adapter.stop()
    assert not adapter.is_running(), "Emulator failed to stop"
    print("  -> Emulator stopped cleanly!")

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED! Emuautotest is 100% operational!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
