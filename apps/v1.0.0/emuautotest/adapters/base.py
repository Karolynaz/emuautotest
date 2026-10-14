from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from emuautotest.core.types import EmulatorStatus


class BaseEmulatorAdapter(ABC):
    """Abstract Base Class for all emulator adapters (3DS, GBA, NDS, PS1, etc.)."""

    @abstractmethod
    def launch(self, rom_path: Optional[str] = None) -> bool:
        """Launch the emulator with the given ROM."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stop the running emulator."""
        pass

    @abstractmethod
    def get_status(self) -> EmulatorStatus:
        """Get current status of the emulator."""
        pass

    @abstractmethod
    def take_screenshot(self, target: str = "both") -> Tuple[bytes, str, int, int]:
        """Capture screenshot and return (png_bytes, base64_str, width, height)."""
        pass

    @abstractmethod
    def press_button(self, button: str, duration_ms: int = 100) -> bool:
        """Simulate pressing a hardware button."""
        pass

    @abstractmethod
    def touch_screen(self, normalized_x: float, normalized_y: float, duration_ms: int = 100) -> bool:
        """Simulate touch screen interaction."""
        pass

    @abstractmethod
    def circle_pad(self, direction: str, duration_ms: int = 200) -> bool:
        """Simulate analog stick movement."""
        pass

    @abstractmethod
    def execute_macro(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute a sequence of actions (press, wait, touch, screenshot)."""
        pass

    @abstractmethod
    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        """Read emulator RAM."""
        pass

    @abstractmethod
    def write_memory(self, address: int, data: bytes) -> bool:
        """Write to emulator RAM."""
        pass
