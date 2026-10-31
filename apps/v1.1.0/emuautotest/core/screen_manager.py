import base64
import io
import subprocess
import tempfile
from typing import Optional, Tuple

from PIL import Image


class ScreenManager:
    """Manages screenshot processing, cropping, and conversion for 3DS screens."""

    @staticmethod
    def process_screenshot_bytes(
        png_bytes: bytes, target: str = "both", crop_bottom_bars: bool = True
    ) -> Tuple[bytes, str, int, int]:
        """
        Process raw 400x480 3DS frame bytes:
        - target: "top" (400x240), "bottom" (320x240), or "both" (400x480).
        Returns: (png_bytes, base64_str, width, height)
        """
        img = Image.open(io.BytesIO(png_bytes))
        width, height = img.size

        if target.lower() == "top":
            # Top screen: 0 to 240 height
            top_box = (0, 0, width, height // 2)
            img = img.crop(top_box)
        elif target.lower() == "bottom":
            # Bottom screen: 240 to 480 height
            # 3DS touch screen is 320px centered in 400px (40px padding on left/right)
            if crop_bottom_bars and width == 400 and height == 480:
                bottom_box = (40, 240, 360, 480)
            else:
                bottom_box = (0, height // 2, width, height)
            img = img.crop(bottom_box)

        # Ensure RGB mode for PNG output
        if img.mode != "RGB":
            img = img.convert("RGB")

        out_io = io.BytesIO()
        img.save(out_io, format="PNG")
        processed_bytes = out_io.getvalue()
        b64 = base64.b64encode(processed_bytes).decode("ascii")

        return processed_bytes, b64, img.width, img.height

    @staticmethod
    def capture_window_screencapture(window_id: int) -> Optional[bytes]:
        """Fallback: capture window on macOS using native screencapture tool."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # -l <window_id>: capture window, -x: mute sound, -o: no shadow
            res = subprocess.run(["screencapture", "-l", str(window_id), "-x", "-o", tmp_path], capture_output=True)
            if res.returncode == 0:
                with open(tmp_path, "rb") as f:
                    return f.read()
        except Exception:
            pass
        return None
