import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from AppKit import NSRunningApplication
except ImportError:
    NSRunningApplication = None

from emuautotest.adapters.base import BaseEmulatorAdapter
from emuautotest.config import (
    AZAHAR_BINARY,
    AZAHAR_RPC_HOST,
    AZAHAR_RPC_PORT,
    DEFAULT_ROM,
)
from emuautotest.core.input_manager import InputManager
from emuautotest.core.screen_manager import ScreenManager
from emuautotest.core.types import EmulatorStatus
from emuautotest.core.video_recorder import VideoRecorder
from emuautotest.rpc.azahar_rpc import AzaharRPCClient


class Azahar3DSAdapter(BaseEmulatorAdapter):
    """Nintendo 3DS adapter using Azahar emulator with RPC and macOS input automation."""

    def __init__(self, binary_path: Optional[Path] = None):
        self.binary_path = binary_path or AZAHAR_BINARY
        self.current_rom: Optional[Path] = None
        self.process: Optional[subprocess.Popen] = None
        self.rpc = AzaharRPCClient(address=AZAHAR_RPC_HOST, port=AZAHAR_RPC_PORT, timeout=2.0)
        self.input_mgr = InputManager()
        self.recorder = VideoRecorder(frame_provider=self._get_raw_frame)

    def launch(self, rom_path: Optional[str] = None) -> bool:
        """Launch Azahar emulator with specified ROM."""
        self.stop()
        try:
            subprocess.run(["pkill", "-9", "-f", "azahar"], capture_output=True)
            time.sleep(0.3)
        except Exception:
            pass

        if rom_path:
            target_rom = Path(rom_path).resolve()
        else:
            target_rom = DEFAULT_ROM.resolve()

        if not target_rom.exists():
            raise FileNotFoundError(f"ROM file not found: {target_rom}")

        if not self.binary_path.exists():
            raise FileNotFoundError(f"Azahar binary not found: {self.binary_path}")

        self.current_rom = target_rom

        cmd = [str(self.binary_path), str(target_rom)]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )

        if self.process.pid:
            self.input_mgr.set_pid(self.process.pid)

            def _minimize_to_dock(pid: int):
                for _ in range(15):
                    time.sleep(0.15)
                    if NSRunningApplication:
                        try:
                            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
                            if app:
                                app.hide()
                        except Exception:
                            pass
                    try:
                        subprocess.run(
                            [
                                "osascript",
                                "-e",
                                f'tell application "System Events" to set miniaturized of (every window of (every process whose unix id is {pid})) to true',
                            ],
                            capture_output=True,
                            timeout=1.0,
                        )
                    except Exception:
                        pass

            threading.Thread(target=_minimize_to_dock, args=(self.process.pid,), daemon=True).start()

        # Wait for RPC server or window to be active
        ready = False
        for _ in range(25):  # up to 5 seconds
            time.sleep(0.2)
            if self.rpc.ping():
                ready = True
                break
            if self.input_mgr.find_emulator_window():
                ready = True
                break

        return ready or self.is_running()

    def is_running(self) -> bool:
        if self.process is not None:
            if self.process.poll() is None:
                return True
        # Check if window is visible on screen
        win = self.input_mgr.find_emulator_window()
        return win is not None

    def stop(self) -> bool:
        """Stop running emulator gracefully without triggering crash dialogs."""
        # 0. Cleanly stop active video recording first
        if hasattr(self, "recorder") and self.recorder.is_recording():
            try:
                self.recorder.stop()
            except Exception:
                pass

        if self.process and self.process.poll() is None:
            # 1. Graceful Cocoa termination (avoids macOS CrashReporter)
            if NSRunningApplication:
                try:
                    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(self.process.pid)
                    if app:
                        app.terminate()
                except Exception:
                    pass

            try:
                self.process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                # 2. SIGTERM
                self.process.terminate()
                try:
                    self.process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    # 3. Last resort: kill
                    self.process.kill()
            self.process = None

        # Clean any remaining processes gracefully
        try:
            subprocess.run(["pkill", "-TERM", "-f", "azahar"], capture_output=True)
        except Exception:
            pass

        self.current_rom = None
        return True

    def get_status(self) -> EmulatorStatus:
        running = self.is_running()
        pid = self.process.pid if self.process and self.process.poll() is None else self.input_mgr.target_pid
        rom_str = str(self.current_rom) if self.current_rom else None

        game_fps = 0.0
        sys_fps = 0.0
        speed = 0.0
        rpc_ok = False

        if running:
            stats = self.rpc.perf_stats()
            if stats:
                rpc_ok = True
                game_fps = round(stats.get("game_fps", 0.0), 2)
                sys_fps = round(stats.get("system_fps", 0.0), 2)
                speed = round(stats.get("emulation_speed", 0.0) * 100.0, 1)

        win_info = self.input_mgr.find_emulator_window()
        bounds = win_info[1] if win_info else None

        return EmulatorStatus(
            is_running=running,
            pid=pid,
            rom_path=rom_str,
            game_fps=game_fps,
            system_fps=sys_fps,
            emulation_speed=speed,
            window_bounds=bounds,
            rpc_connected=rpc_ok,
        )

    def take_screenshot(self, target: str = "both") -> Tuple[bytes, str, int, int]:
        """Capture frame and return (bytes, base64_str, width, height)."""
        if not self.is_running():
            raise RuntimeError("Emulator is not running")

        # 1. Try In-Engine Screenshot via RPC
        try:
            png_bytes = self.rpc.screenshot_png()
            return ScreenManager.process_screenshot_bytes(png_bytes, target=target)
        except Exception:
            pass

        # 2. Fallback: OS Window Capture
        win = self.input_mgr.find_emulator_window()
        if win:
            win_id, _ = win
            win_bytes = ScreenManager.capture_window_screencapture(win_id)
            if win_bytes:
                return ScreenManager.process_screenshot_bytes(win_bytes, target=target)

        raise RuntimeError("Failed to capture screenshot via RPC or OS window capture")

    def press_button(self, button: str, duration_ms: int = 100) -> bool:
        if not self.is_running():
            raise RuntimeError("Emulator is not running")
        return self.input_mgr.press_button(button, duration_ms=duration_ms)

    def touch_screen(self, normalized_x: float, normalized_y: float, duration_ms: int = 100) -> bool:
        if not self.is_running():
            raise RuntimeError("Emulator is not running")
        return self.input_mgr.touch_screen(normalized_x, normalized_y, duration_ms=duration_ms)

    def circle_pad(self, direction: str, duration_ms: int = 200) -> bool:
        if not self.is_running():
            raise RuntimeError("Emulator is not running")
        return self.input_mgr.circle_pad_move(direction, duration_ms=duration_ms)

    def execute_macro(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for idx, act in enumerate(actions):
            act_type = act.get("action", "").lower().strip()
            item_res = {"step": idx, "action": act_type, "status": "ok"}

            try:
                if act_type == "press":
                    btn = act.get("button", "A")
                    dur = int(act.get("duration_ms", 100))
                    self.press_button(btn, duration_ms=dur)
                elif act_type == "wait":
                    dur = int(act.get("duration_ms", 200))
                    time.sleep(dur / 1000.0)
                elif act_type == "touch":
                    x = float(act.get("x", 0.5))
                    y = float(act.get("y", 0.5))
                    dur = int(act.get("duration_ms", 100))
                    self.touch_screen(x, y, duration_ms=dur)
                elif act_type == "circle_pad":
                    direction = act.get("direction", "UP")
                    dur = int(act.get("duration_ms", 200))
                    self.circle_pad(direction, duration_ms=dur)
                elif act_type == "screenshot":
                    target = act.get("screen", "both")
                    _, b64, w, h = self.take_screenshot(target=target)
                    item_res["screenshot"] = {"width": w, "height": h, "base64": b64}
                elif act_type == "record_start":
                    rec_target = act.get("target", "both")
                    rec_fps = int(act.get("fps", 30))
                    rec_fmt = act.get("format", "mp4")
                    rec_scale = int(act.get("scale", 1))
                    rec_out = act.get("output_path", None)
                    rec_res = self.start_recording(
                        target=rec_target, fps=rec_fps, format=rec_fmt, scale=rec_scale, output_path=rec_out
                    )
                    item_res["recording"] = rec_res
                elif act_type == "record_stop":
                    item_res["recording"] = self.stop_recording()
                elif act_type == "record_clip":
                    dur_sec = float(act.get("duration_seconds", 3.0))
                    rec_target = act.get("target", "both")
                    rec_fps = int(act.get("fps", 30))
                    rec_fmt = act.get("format", "mp4")
                    rec_scale = int(act.get("scale", 1))
                    item_res["recording"] = self.record_clip(
                        duration_seconds=dur_sec, target=rec_target, fps=rec_fps, format=rec_fmt, scale=rec_scale
                    )
                else:
                    item_res["status"] = f"ignored unknown action: {act_type}"
            except Exception as e:
                item_res["status"] = f"error: {str(e)}"

            results.append(item_res)
        return results

    def _get_raw_frame(self) -> bytes:
        """Fetch raw PNG frame directly from emulator RPC or OS window capture."""
        try:
            return self.rpc.screenshot_png()
        except Exception:
            win = self.input_mgr.find_emulator_window()
            if win:
                win_bytes = ScreenManager.capture_window_screencapture(win[0])
                if win_bytes:
                    return win_bytes
            raise RuntimeError("Failed to capture frame from RPC or OS window")

    def start_recording(
        self,
        target: str = "both",
        fps: int = 30,
        format: str = "mp4",
        scale: int = 1,
        output_path: Optional[str] = None,
        max_duration: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.is_running():
            raise RuntimeError("Emulator is not running")
        return self.recorder.start(
            target=target,
            fps=fps,
            format=format,
            scale=scale,
            output_path=output_path,
            max_duration=max_duration,
        )

    def stop_recording(self) -> Dict[str, Any]:
        return self.recorder.stop()

    def get_recording_status(self) -> Dict[str, Any]:
        return self.recorder.get_status()

    def record_clip(
        self,
        duration_seconds: float = 5.0,
        target: str = "both",
        fps: int = 30,
        format: str = "mp4",
        scale: int = 1,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_running():
            raise RuntimeError("Emulator is not running")
        return self.recorder.record_clip(
            duration_seconds=duration_seconds,
            target=target,
            fps=fps,
            format=format,
            scale=scale,
            output_path=output_path,
        )

    def list_recordings(self) -> List[Dict[str, Any]]:
        return VideoRecorder.list_saved_recordings()

    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        return self.rpc.read_memory(address, size)

    def write_memory(self, address: int, data: bytes) -> bool:
        return self.rpc.write_memory(address, data)
