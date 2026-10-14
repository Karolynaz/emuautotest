import ctypes
import ctypes.util
import time
from typing import List, Optional, Tuple

import Quartz
from emuautotest.core.types import Button, WindowBounds

# Load ApplicationServices framework
_app_services = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))

# Ctypes Signatures
CGEventSourceRef = ctypes.c_void_p
CGEventRef = ctypes.c_void_p
CGKeyCode = ctypes.c_uint16
pid_t = ctypes.c_int32


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


_app_services.CGEventCreateKeyboardEvent.argtypes = [CGEventSourceRef, CGKeyCode, ctypes.c_bool]
_app_services.CGEventCreateKeyboardEvent.restype = CGEventRef

_app_services.CGEventCreateMouseEvent.argtypes = [CGEventSourceRef, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
_app_services.CGEventCreateMouseEvent.restype = CGEventRef

_app_services.CGEventPostToPid.argtypes = [pid_t, CGEventRef]
_app_services.CGEventPostToPid.restype = None

_app_services.CGEventPost.argtypes = [ctypes.c_uint32, CGEventRef]
_app_services.CGEventPost.restype = None

_app_services.CFRelease.argtypes = [ctypes.c_void_p]
_app_services.CFRelease.restype = None

# macOS Virtual Keycodes
KEYCODES = {
    # Buttons
    "A": [0],         # 'A'
    "B": [1],         # 'S'
    "X": [13],        # 'W'
    "Y": [2],         # 'D'
    "L": [12],        # 'Q'
    "R": [14],        # 'E'
    "START": [36],    # Return
    "SELECT": [56],   # Shift
    "HOME": [11],     # 'B'
    # D-pad bindings; Circle Pad uses arrow keys separately.
    "UP": [33],      # Arrow Up & '['
    "DOWN": [39],    # Arrow Down & '''
    "LEFT": [41],    # Arrow Left & ';'
    "RIGHT": [42],   # Arrow Right & '\'
}

# Mouse event types in CoreGraphics
kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGEventMouseMoved = 5
kCGEventLeftMouseDragged = 6
kCGHIDEventTap = 0


class InputManager:
    """Manages programmatic input simulation for Azahar emulator."""

    def __init__(self, target_pid: Optional[int] = None):
        self.target_pid = target_pid

    def set_pid(self, pid: int) -> None:
        self.target_pid = pid

    def find_emulator_window(self, process_name: str = "azahar", on_screen_only: bool = False) -> Optional[Tuple[int, WindowBounds]]:
        """Find the emulator window ID and bounding box on macOS."""
        options = Quartz.kCGWindowListOptionOnScreenOnly if on_screen_only else Quartz.kCGWindowListOptionAll
        window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        for w in window_list:
            owner = w.get("kCGWindowOwnerName", "")
            name = w.get("kCGWindowName", "")
            pid = w.get("kCGWindowOwnerPID")
            if process_name.lower() in owner.lower() or process_name.lower() in name.lower():
                bounds = w.get("kCGWindowBounds", {})
                if bounds.get("Width", 0) > 50 and bounds.get("Height", 0) > 50:
                    wb = WindowBounds(
                        x=float(bounds["X"]),
                        y=float(bounds["Y"]),
                        width=float(bounds["Width"]),
                        height=float(bounds["Height"]),
                    )
                    if pid:
                        self.target_pid = int(pid)
                    return int(w["kCGWindowNumber"]), wb
        return None

    def press_keycodes(self, keycodes: List[int], duration_ms: int = 100) -> None:
        """Press down a set of macOS keycodes and release after duration."""
        # Key down
        for code in keycodes:
            ev = _app_services.CGEventCreateKeyboardEvent(None, code, True)
            if ev:
                if self.target_pid:
                    _app_services.CGEventPostToPid(self.target_pid, ev)
                else:
                    _app_services.CGEventPost(kCGHIDEventTap, ev)
                _app_services.CFRelease(ev)

        time.sleep(max(duration_ms, 20) / 1000.0)

        # Key up
        for code in reversed(keycodes):
            ev = _app_services.CGEventCreateKeyboardEvent(None, code, False)
            if ev:
                if self.target_pid:
                    _app_services.CGEventPostToPid(self.target_pid, ev)
                else:
                    _app_services.CGEventPost(kCGHIDEventTap, ev)
                _app_services.CFRelease(ev)

    def press_button(self, button_name: str, duration_ms: int = 100) -> bool:
        """Press a named 3DS button."""
        btn_key = button_name.upper().strip()
        codes = KEYCODES.get(btn_key)
        if not codes:
            raise ValueError(f"Unknown button: {button_name}. Available buttons: {list(KEYCODES.keys())}")
        self.press_keycodes(codes, duration_ms=duration_ms)
        return True

    def circle_pad_move(self, direction: str, duration_ms: int = 200) -> bool:
        """Simulate analog circle pad direction."""
        dir_clean = direction.upper().strip()
        keycodes = []
        if "UP" in dir_clean:
            keycodes.append(126)
        if "DOWN" in dir_clean:
            keycodes.append(125)
        if "LEFT" in dir_clean:
            keycodes.append(123)
        if "RIGHT" in dir_clean:
            keycodes.append(124)

        if not keycodes:
            raise ValueError(f"Unknown direction: {direction}. Use UP, DOWN, LEFT, RIGHT or compounds like UP_LEFT.")
        self.press_keycodes(keycodes, duration_ms=duration_ms)
        return True

    def touch_screen(self, normalized_x: float, normalized_y: float, duration_ms: int = 100) -> bool:
        """
        Touch the bottom 3DS screen.
        normalized_x: 0.0 (left) to 1.0 (right) of bottom screen.
        normalized_y: 0.0 (top) to 1.0 (bottom) of bottom screen.
        """
        win_info = self.find_emulator_window()
        if not win_info:
            raise RuntimeError("Cannot touch screen: Emulator window not found")

        _, bounds = win_info
        # In default 3DS vertical layout:
        # Top screen is the top half, bottom screen is the bottom half.
        # Add a small margin for window title bar (approx 30px)
        title_bar_height = 28.0
        content_height = bounds.height - title_bar_height
        half_height = content_height / 2.0

        # Bottom screen bounds inside window:
        bottom_screen_top = bounds.y + title_bar_height + half_height
        bottom_screen_width = bounds.width * 0.8
        bottom_screen_left = bounds.x + (bounds.width - bottom_screen_width) / 2
        bottom_screen_height = half_height

        # Calculate target screen coordinate
        target_x = bottom_screen_left + (normalized_x * bottom_screen_width)
        target_y = bottom_screen_top + (normalized_y * bottom_screen_height)

        pt = CGPoint(target_x, target_y)

        # Mouse Down
        down_ev = _app_services.CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, pt, 0)
        if down_ev:
            _app_services.CGEventPost(kCGHIDEventTap, down_ev)
            _app_services.CFRelease(down_ev)

        time.sleep(max(duration_ms, 30) / 1000.0)

        # Mouse Up
        up_ev = _app_services.CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, pt, 0)
        if up_ev:
            _app_services.CGEventPost(kCGHIDEventTap, up_ev)
            _app_services.CFRelease(up_ev)

        return True
