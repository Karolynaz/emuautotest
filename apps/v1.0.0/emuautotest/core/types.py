from dataclasses import dataclass, field
import enum
from typing import Any, Dict, Optional


class Button(str, enum.Enum):
    A = "A"
    B = "B"
    X = "X"
    Y = "Y"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    L = "L"
    R = "R"
    START = "START"
    SELECT = "SELECT"
    HOME = "HOME"


class ScreenTarget(str, enum.Enum):
    TOP = "top"
    BOTTOM = "bottom"
    BOTH = "both"


@dataclass
class WindowBounds:
    x: float
    y: float
    width: float
    height: float


@dataclass
class EmulatorStatus:
    is_running: bool
    pid: Optional[int] = None
    rom_path: Optional[str] = None
    game_fps: float = 0.0
    system_fps: float = 0.0
    emulation_speed: float = 0.0
    window_bounds: Optional[WindowBounds] = None
    rpc_connected: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
