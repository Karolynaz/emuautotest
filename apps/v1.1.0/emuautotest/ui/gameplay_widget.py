import io
import threading
import time
from typing import Optional

from PIL import Image
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from emuautotest.adapters.azahar_3ds import Azahar3DSAdapter
from emuautotest.core.input_manager import _app_services, kCGHIDEventTap
from emuautotest.rpc.azahar_rpc import SCREENSHOT_FLAG_RAW_RGB
from emuautotest.ui.icons import sf_symbol_pixmap


# Map Qt keys to macOS virtual keycodes matching Azahar's qt-config.ini bindings
_QT_TO_MAC_KEYCODE = {
    Qt.Key.Key_A: 0,       # Button A
    Qt.Key.Key_S: 1,       # Button B
    Qt.Key.Key_W: 13,      # Button X
    Qt.Key.Key_D: 2,       # Button Y
    Qt.Key.Key_Q: 12,      # L
    Qt.Key.Key_E: 14,      # R
    Qt.Key.Key_Return: 36, # Start
    Qt.Key.Key_Enter: 36,
    Qt.Key.Key_Shift: 56,  # Select
    Qt.Key.Key_B: 11,      # Home
    Qt.Key.Key_Left: 123,  # Circle Pad Left
    Qt.Key.Key_Right: 124, # Circle Pad Right
    Qt.Key.Key_Down: 125,  # Circle Pad Down
    Qt.Key.Key_Up: 126,    # Circle Pad Up
    Qt.Key.Key_BracketLeft: 33,  # D-Pad Up
    Qt.Key.Key_Apostrophe: 39,   # D-Pad Down
    Qt.Key.Key_Semicolon: 41,    # D-Pad Left
    Qt.Key.Key_Backslash: 42,    # D-Pad Right
}


class GameplayWidget(QWidget):
    """Embedded 3DS dual-screen gameplay viewport rendered inside the main library window.

    Streams frames via Azahar RPC and forwards keyboard/touch events to the background emulator.
    """

    frame_ready = Signal(QImage)
    stop_requested = Signal()
    fullscreen_requested = Signal()

    def __init__(self, adapter: Azahar3DSAdapter, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.adapter = adapter
        self._current_image: Optional[QImage] = None
        self._render_rect = QRect()
        self._streaming = False
        self._stream_thread: Optional[threading.Thread] = None
        self._is_fullscreen_bg = False

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(False)
        self.frame_ready.connect(self._on_frame_ready)

        # Subtle bottom hint pill inside the theater viewport (Full Screen & Close live in top header)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 14)
        root.addStretch()

        hint_bar = QHBoxLayout()
        hint_bar.addStretch()
        self.hint_pill = QLabel("Arrows: Circle Pad  ·  A/S/W/D: A/B/X/Y  ·  Q/E: L/R  ·  Click bottom screen for touch")
        self.hint_pill.setStyleSheet(
            "color: rgba(235, 235, 245, 165); background-color: rgba(28, 28, 32, 175); "
            "border: 1px solid rgba(255, 255, 255, 24); border-radius: 10px; "
            "padding: 4px 12px; font-size: 11px; font-weight: 500;"
        )
        hint_bar.addWidget(self.hint_pill)
        hint_bar.addStretch()
        root.addLayout(hint_bar)

    def set_fullscreen_mode(self, is_fs: bool) -> None:
        self._is_fullscreen_bg = is_fs
        self.hint_pill.setVisible(not is_fs)
        self.update()

    def start_streaming(self) -> None:
        if self._streaming:
            return
        self._streaming = True
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
        self.setFocus()

    def stop_streaming(self) -> None:
        self._streaming = False
        self._current_image = None
        self.update()

    def _stream_loop(self) -> None:
        use_raw = True
        while self._streaming:
            if not self.adapter.is_running():
                time.sleep(0.1)
                continue
            try:
                if use_raw:
                    res = self.adapter.rpc._take_screenshot(0, SCREENSHOT_FLAG_RAW_RGB)
                    if res is not None:
                        w, h, raw_bytes = res
                        expected_rgb = w * h * 3
                        expected_rgba = w * h * 4
                        if len(raw_bytes) == expected_rgba:
                            img = QImage(raw_bytes, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
                            self.frame_ready.emit(img)
                            time.sleep(0.016)
                            continue
                        elif len(raw_bytes) == expected_rgb:
                            img = QImage(raw_bytes, w, h, w * 3, QImage.Format.Format_RGB888).copy()
                            self.frame_ready.emit(img)
                            time.sleep(0.016)
                            continue
                        else:
                            use_raw = False
                # PNG fallback
                png_bytes = self.adapter.rpc.screenshot_png()
                pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                data = pil_img.tobytes("raw", "RGB")
                img = QImage(data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format.Format_RGB888).copy()
                self.frame_ready.emit(img)
                time.sleep(0.025)
            except Exception:
                time.sleep(0.08)

    def _on_frame_ready(self, img: QImage) -> None:
        self._current_image = img
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        bg = QColor("#000000") if self._is_fullscreen_bg else QColor("#111215")
        p.fillRect(self.rect(), bg)

        if not self._is_fullscreen_bg:
            glow = QRadialGradient(self.width() * 0.5, self.height() * 0.48, max(self.width(), self.height()) * 0.6)
            glow.setColorAt(0.0, QColor(32, 38, 56, 120))
            glow.setColorAt(1.0, QColor(17, 18, 21, 0))
            p.fillRect(self.rect(), glow)

        if self._current_image is None or self._current_image.isNull():
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            pm = sf_symbol_pixmap("gamecontroller.fill", color="#8E8E93", size=38, weight="medium")
            p.drawPixmap(int(cx - 19), int(cy - 40), pm)

            f = p.font()
            f.setPointSize(14)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(QPen(QColor("#E5E5EA")))
            p.drawText(QRectF(0, cy + 8, self.width(), 24), Qt.AlignmentFlag.AlignCenter, "Starting Nintendo 3DS...")

            f.setPointSize(11)
            f.setWeight(QFont.Weight.Normal)
            p.setFont(f)
            p.setPen(QPen(QColor("#8E8E93")))
            p.drawText(QRectF(0, cy + 32, self.width(), 20), Qt.AlignmentFlag.AlignCenter, "Connecting to Azahar viewport")
            return

        # Fit 3DS frame inside widget preserving aspect ratio
        pad_x = 0 if self._is_fullscreen_bg else 28
        pad_y = 0 if self._is_fullscreen_bg else 32
        avail_w = max(10, self.width() - pad_x * 2)
        avail_h = max(10, self.height() - pad_y * 2)
        img_w = self._current_image.width()
        img_h = self._current_image.height()
        scale = min(avail_w / img_w, avail_h / img_h)
        draw_w = int(img_w * scale)
        draw_h = int(img_h * scale)
        x = (self.width() - draw_w) // 2
        y = (self.height() - draw_h) // 2
        self._render_rect = QRect(x, y, draw_w, draw_h)

        if not self._is_fullscreen_bg:
            # Subtle rounded bezel & shadow
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 110))
            p.drawRoundedRect(QRectF(x - 2, y + 6, draw_w + 4, draw_h + 4), 12.0, 12.0)

            clip = QPainterPath()
            clip.addRoundedRect(QRectF(self._render_rect), 10.0, 10.0)
            p.save()
            p.setClipPath(clip)
            p.drawImage(self._render_rect, self._current_image)
            p.restore()

            p.setPen(QPen(QColor(255, 255, 255, 34), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(x - 0.5, y - 0.5, draw_w + 1, draw_h + 1), 10.0, 10.0)
        else:
            p.drawImage(self._render_rect, self._current_image)

    def _post_mac_key(self, keycode: int, down: bool) -> None:
        ev = _app_services.CGEventCreateKeyboardEvent(None, keycode, down)
        if ev:
            pid = self.adapter.input_mgr.target_pid
            if pid:
                _app_services.CGEventPostToPid(pid, ev)
            else:
                _app_services.CGEventPost(kCGHIDEventTap, ev)
            _app_services.CFRelease(ev)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not event.isAutoRepeat():
            kc = _QT_TO_MAC_KEYCODE.get(event.key())
            if kc is not None:
                self._post_mac_key(kc, True)
                event.accept()
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if not event.isAutoRepeat():
            kc = _QT_TO_MAC_KEYCODE.get(event.key())
            if kc is not None:
                self._post_mac_key(kc, False)
                event.accept()
                return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        if event.button() == Qt.MouseButton.LeftButton and not self._render_rect.isEmpty():
            pos = event.position()
            # Bottom 3DS screen is lower half (y >= 0.5 of combined 400x480), centered 320/400 width
            rx = (pos.x() - self._render_rect.x()) / self._render_rect.width()
            ry = (pos.y() - self._render_rect.y()) / self._render_rect.height()
            if 0.0 <= rx <= 1.0 and 0.5 <= ry <= 1.0:
                norm_x = max(0.0, min(1.0, (rx - 0.1) / 0.8))
                norm_y = max(0.0, min(1.0, (ry - 0.5) / 0.5))
                threading.Thread(
                    target=self.adapter.touch_screen,
                    args=(norm_x, norm_y, 80),
                    daemon=True,
                ).start()
        super().mousePressEvent(event)
