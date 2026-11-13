"""Custom macOS-native styled UI components for Emuautotest."""

import zlib
from typing import Any, Callable, List, Optional, Tuple

from PIL import Image
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from emuautotest.ui.icons import make_icon, sf_symbol_pixmap
from emuautotest.ui.rom_metadata import RomInfo
from emuautotest.ui.theme import MacTheme, qcolor, start_window_drag


def pil_to_qpixmap(pil_img: Image.Image, target_size: int) -> QPixmap:
    """Convert a PIL image into a Retina-ready QPixmap."""
    rgba = pil_img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
    pm = QPixmap.fromImage(qimg)
    px = target_size * 2
    scaled = pm.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(2.0)
    return scaled


_FALLBACK_PALETTES_LIGHT = [
    ("#E8EEFC", "#D4E0FA", "#3B5BDB"),  # Indigo
    ("#E4F5F2", "#C9EBE5", "#0CA678"),  # Teal
    ("#F2EBFC", "#E1D2FA", "#7048E8"),  # Violet
    ("#FCECE8", "#F7D5CC", "#E8590C"),  # Coral
    ("#EDF3FA", "#D6E4F5", "#1C7ED6"),  # Azure
    ("#FDF4E3", "#FAE4BC", "#D97706"),  # Amber
]

_FALLBACK_PALETTES_DARK = [
    ("#27304A", "#191E30", "#748FFC"),  # Indigo
    ("#1E3834", "#142623", "#38D9A9"),  # Teal
    ("#312747", "#201930", "#9775FA"),  # Violet
    ("#402822", "#2B1A16", "#FF8787"),  # Coral
    ("#223247", "#162130", "#4DABF7"),  # Azure
    ("#3D301D", "#292012", "#FCC419"),  # Amber
]


def _fallback_palette_for_title(key: str, is_dark: bool) -> Tuple[QColor, QColor, str]:
    idx = zlib.crc32(key.encode("utf-8")) % len(_FALLBACK_PALETTES_LIGHT)
    pal = _FALLBACK_PALETTES_DARK[idx] if is_dark else _FALLBACK_PALETTES_LIGHT[idx]
    return QColor(pal[0]), QColor(pal[1]), pal[2]


def _extract_accent_colors(pil_img: Optional[Image.Image], key: str, is_dark: bool) -> Tuple[QColor, QColor, str]:
    """Extract harmonious top/bottom gradient backdrop colors from a ROM icon."""
    if pil_img is None:
        return _fallback_palette_for_title(key, is_dark)

    try:
        small = pil_img.convert("RGB").resize((8, 8), Image.Resampling.BILINEAR)
        pixels = list(small.getdata())
        # Pick colorful pixels if available
        best = None
        best_score = -1.0
        avg_r = avg_g = avg_b = 0
        for r, g, b in pixels:
            avg_r += r
            avg_g += g
            avg_b += b
            mx, mn = max(r, g, b), min(r, g, b)
            sat = (mx - mn) / max(1, mx)
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            score = sat * (1.0 - abs(lum - 0.5))
            if score > best_score:
                best_score = score
                best = (r, g, b)
        n = max(1, len(pixels))
        ar, ag, ab = avg_r // n, avg_g // n, avg_b // n
        br, bg, bb = best if (best and best_score > 0.12) else (ar, ag, ab)

        base = QColor(br, bg, bb)
        h, s, v, _ = base.getHslF()
        if is_dark:
            c1 = QColor.fromHslF(h, min(0.55, s * 0.85), 0.24)
            c2 = QColor.fromHslF((h + 0.05) % 1.0, min(0.50, s * 0.75), 0.15)
        else:
            c1 = QColor.fromHslF(h, min(0.55, max(0.18, s * 0.65)), 0.92)
            c2 = QColor.fromHslF((h + 0.04) % 1.0, min(0.50, max(0.20, s * 0.70)), 0.84)
        return c1, c2, base.name()
    except Exception:
        return _fallback_palette_for_title(key, is_dark)


def make_cover_artwork(rom: RomInfo, width: int, height: int, theme: MacTheme, hovered: bool = False) -> QPixmap:
    """Paint a rich, modern macOS-style game cover artwork pixmap at 2x Retina with true rounded shadow."""
    pad_x = 8
    pad_top = 5
    pad_bottom = 11
    total_w = width + pad_x * 2
    total_h = height + pad_top + pad_bottom

    pm = QPixmap(total_w * 2, total_h * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    radius = 14.0
    card_rect = QRectF(pad_x, pad_top, width, height)

    # True rounded-corner ambient drop shadow (zero rectangular QGraphicsEffect artifacts)
    p.setPen(Qt.PenStyle.NoPen)
    if hovered:
        shadow_layers = [
            (0.0, 2.0, 1.0, 28 if not theme.is_dark else 70),
            (0.0, 5.0, 3.0, 20 if not theme.is_dark else 50),
            (0.0, 8.0, 5.5, 12 if not theme.is_dark else 32),
        ]
    else:
        shadow_layers = [
            (0.0, 1.5, 0.5, 20 if not theme.is_dark else 55),
            (0.0, 3.5, 2.0, 14 if not theme.is_dark else 38),
            (0.0, 6.0, 4.0, 8 if not theme.is_dark else 22),
        ]
    for dx, dy, expand, alpha in shadow_layers:
        sr = card_rect.adjusted(-expand + dx, -expand + dy, expand + dx, expand + dy)
        p.setBrush(QColor(0, 0, 0, alpha))
        p.drawRoundedRect(sr, radius + expand * 0.5, radius + expand * 0.5)

    clip_path = QPainterPath()
    clip_path.addRoundedRect(card_rect, radius, radius)
    p.setClipPath(clip_path)

    # Backdrop gradient derived from ROM icon or curated fallback palette
    c1, c2, accent_hex = _extract_accent_colors(rom.icon_image, f"{rom.title}:{rom.file_type}", theme.is_dark)
    grad = QLinearGradient(card_rect.left(), card_rect.top(), card_rect.right(), card_rect.bottom())
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    p.fillRect(card_rect, grad)

    if rom.icon_image is not None:
        # Stretch / fill game icon edge-to-edge across the entire rounded card
        rgba = rom.icon_image.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
        icon_pm = QPixmap.fromImage(qimg)
        target_side = max(width, height) * 2
        scaled = icon_pm.scaled(
            target_side,
            target_side,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(2.0)
        sx = (scaled.width() / 2.0 - width) / 2.0
        sy = (scaled.height() / 2.0 - height) / 2.0
        p.drawPixmap(int(pad_x - sx), int(pad_top - sy), scaled)

        # Subtle bottom vignette so format badge stays crisp over bright artwork
        vig = QLinearGradient(0, pad_top + height * 0.58, 0, pad_top + height)
        vig.setColorAt(0.0, QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QColor(0, 0, 0, 85))
        p.fillRect(card_rect, vig)
    else:
        # Subtle ambient radial highlight + clean joystick/controller icon directly on gradient (no white box)
        rad = QRadialGradient(pad_x + width * 0.25, pad_top + height * 0.2, width * 0.9)
        rad.setColorAt(0.0, QColor(255, 255, 255, 55 if not theme.is_dark else 26))
        rad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(card_rect, rad)

        sym_size = max(34, int(min(width, height) * 0.36))
        sym_pm = sf_symbol_pixmap("gamecontroller.fill", color=accent_hex, size=sym_size, weight="medium")
        sx = pad_x + (width - sym_size) / 2.0
        sy = pad_top + (height - sym_size) / 2.0 - 4.0
        p.drawPixmap(int(sx), int(sy), sym_pm)

    # Bottom-left subtle format pill ("3DSX" / "3DS")
    badge_text = rom.file_type
    font = p.font()
    font.setPointSize(9)
    font.setWeight(QFont.Weight.DemiBold)
    p.setFont(font)
    fm = p.fontMetrics()
    bw = fm.horizontalAdvance(badge_text) + 12
    bh = 18
    bx = pad_x + 10.0
    by = pad_top + height - bh - 9.0
    if rom.icon_image is not None:
        pill_bg = QColor(18, 18, 22, 175)
        pill_fg = QColor("#FFFFFF")
    else:
        pill_bg = QColor(0, 0, 0, 95) if theme.is_dark else QColor(255, 255, 255, 190)
        pill_fg = QColor("#F5F5F7") if theme.is_dark else QColor("#3A3A3C")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(pill_bg)
    p.drawRoundedRect(QRectF(bx, by, bw, bh), 6.0, 6.0)
    p.setPen(pill_fg)
    p.drawText(QRectF(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, badge_text)

    # Hover Play Pill in bottom-right
    if hovered:
        play_d = 30.0
        px = pad_x + width - play_d - 9.0
        py = pad_top + height - play_d - 9.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor(theme.accent))
        p.drawEllipse(QRectF(px, py, play_d, play_d))
        play_pm = sf_symbol_pixmap("play.fill", color="#FFFFFF", size=14, weight="bold")
        p.drawPixmap(int(px + (play_d - 14) / 2 + 1), int(py + (play_d - 14) / 2), play_pm)

    # Crisp outer card border / hover ring
    p.setClipping(False)
    border_color = qcolor(theme.accent) if hovered else qcolor(theme.card_border)
    pen_w = 1.6 if hovered else 1.0
    p.setPen(QPen(border_color, pen_w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(card_rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

    p.end()
    return pm


class DraggableHeader(QWidget):
    """Unified 52px macOS title/toolbar header that supports native window dragging."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(52)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            # Only drag if clicking empty header space or a non-interactive QLabel
            if child is None or isinstance(child, QLabel):
                start_window_drag(self)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or isinstance(child, QLabel):
                win = self.window()
                if win is not None:
                    if win.isMaximized():
                        win.showNormal()
                    else:
                        win.showMaximized()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


class SidebarNavItem(QFrame):
    """Native macOS Finder/Music style sidebar navigation pill (QFrame-based to avoid QMacStyle button bleed)."""

    clicked = Signal()

    def __init__(
        self,
        icon_kind: str,
        label: str,
        badge_text: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._icon_kind = icon_kind
        self._label_text = label
        self._badge_text = badge_text
        self._checked = False
        self._hovered = False
        self._theme: Optional[MacTheme] = None

        self.setObjectName("sidebarNavItem")
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(9)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(18, 18)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.icon_lbl)

        self.text_lbl = QLabel(label)
        self.text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.text_lbl, 1)

        self.badge_lbl = QLabel(badge_text)
        self.badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.badge_lbl.setVisible(bool(badge_text))
        lay.addWidget(self.badge_lbl)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked != checked:
            self._checked = checked
            self._refresh_visuals()

    def set_badge(self, text: str) -> None:
        self._badge_text = text
        self.badge_lbl.setText(text)
        self.badge_lbl.setVisible(bool(text))

    def apply_theme(self, theme: MacTheme) -> None:
        self._theme = theme
        self._refresh_visuals()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._refresh_visuals()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._refresh_visuals()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def _refresh_visuals(self) -> None:
        if self._theme is None:
            return
        t = self._theme
        checked = self._checked
        if checked:
            bg = t.sidebar_active
        elif self._hovered:
            bg = t.sidebar_hover
        else:
            bg = "transparent"

        self.setStyleSheet(
            f"#sidebarNavItem {{ border: none; border-radius: 8px; background-color: {bg}; }}"
        )
        icon_color = t.accent if checked else t.text_secondary
        self.icon_lbl.setStyleSheet("border: none; background: transparent;")
        self.icon_lbl.setPixmap(sf_symbol_pixmap(self._icon_kind, color=icon_color, size=16, weight="medium"))

        text_color = t.accent_text if checked else t.text_primary
        weight = "600" if checked else "500"
        self.text_lbl.setStyleSheet(
            f"color: {text_color}; font-size: 13px; font-weight: {weight}; background: transparent; border: none;"
        )

        badge_color = t.accent_text if checked else t.text_muted
        badge_bg = t.accent_soft if checked else t.pill_bg
        self.badge_lbl.setStyleSheet(
            f"color: {badge_color}; background-color: {badge_bg}; border: none; "
            "border-radius: 9px; padding: 1px 7px; font-size: 11px; font-weight: 600;"
        )


class ToolbarIconButton(QPushButton):
    """Crisp macOS toolbar icon button with SF Symbol and optional active highlight."""

    def __init__(self, icon_kind: str, tooltip: str, size: int = 16, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_kind = icon_kind
        self._icon_size = size
        self._accent_state = False
        self._danger_state = False
        self._force_dark = False
        self._theme: Optional[MacTheme] = None

        self.setToolTip(tooltip)
        self.setFixedSize(28, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_icon_kind(self, icon_kind: str) -> None:
        self._icon_kind = icon_kind
        self._refresh_visuals()

    def set_state_colors(self, accent: bool = False, danger: bool = False) -> None:
        self._accent_state = accent
        self._danger_state = danger
        self._refresh_visuals()

    def apply_theme(self, theme: MacTheme, force_dark: bool = False) -> None:
        self._theme = theme
        self._force_dark = force_dark
        self._refresh_visuals()

    def _refresh_visuals(self) -> None:
        if self._theme is None:
            return
        t = self._theme
        if self._force_dark:
            hover_bg = "rgba(255, 255, 255, 0.12)"
            pressed_bg = "rgba(255, 255, 255, 0.18)"
            if self._danger_state:
                bg = "rgba(255, 69, 58, 0.24)"
                icon_col = "#FF453A"
            elif self._accent_state:
                bg = "rgba(10, 132, 255, 0.25)"
                icon_col = "#409CFF"
            else:
                bg = "transparent"
                icon_col = "#FF453A" if self._icon_kind in ("record", "stop_save") else "#D1D1D6"
        else:
            hover_bg = t.toolbar_hover
            pressed_bg = t.toolbar_pressed
            if self._danger_state:
                bg = t.danger_soft
                icon_col = t.danger
            elif self._accent_state:
                bg = t.toolbar_active_bg
                icon_col = t.accent
            else:
                bg = "transparent"
                icon_col = t.danger if self._icon_kind in ("record", "stop_save") else t.text_secondary

        self.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 6px; background-color: {bg}; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: {hover_bg}; }}"
            f"QPushButton:pressed {{ background-color: {pressed_bg}; }}"
            f"QPushButton:disabled {{ opacity: 0.4; }}"
        )
        self.setIcon(make_icon(self._icon_kind, color=icon_col, size=self._icon_size))
        self.setIconSize(QSize(self._icon_size, self._icon_size))


class _BrowserTabChip(QFrame):
    """Single Safari-style browser tab showing only the game title and subtle close button."""

    selected = Signal(int)
    close_requested = Signal(int)

    def __init__(self, tab_id: int, title: str, active: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tab_id = tab_id
        self._title = title
        self._active = active
        self._hovered = False
        self._dark = False
        self._theme: Optional[MacTheme] = None

        self.setObjectName("browserTabChip")
        self.setFixedHeight(28)
        self.setMinimumWidth(90)
        self.setMaximumWidth(210)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(11, 0, 7, 0)
        lay.setSpacing(6)

        self.title_lbl = QLabel(title)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.title_lbl, 1)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Close Tab")
        self.close_btn.clicked.connect(lambda: self.close_requested.emit(self.tab_id))
        lay.addWidget(self.close_btn)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._refresh()

    def set_title(self, title: str) -> None:
        self._title = title
        self.title_lbl.setText(title)

    def apply_theme(self, theme: MacTheme, force_dark: bool = False) -> None:
        self._theme = theme
        self._dark = force_dark or theme.is_dark
        self._refresh()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._refresh()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._refresh()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.tab_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def _refresh(self) -> None:
        if self._dark:
            if self._active:
                bg = "#27282D"
                border = "rgba(255, 255, 255, 0.14)"
                fg = "#F5F5F7"
            elif self._hovered:
                bg = "rgba(255, 255, 255, 0.08)"
                border = "transparent"
                fg = "#D1D1D6"
            else:
                bg = "rgba(255, 255, 255, 0.04)"
                border = "transparent"
                fg = "#8E8E93"
            close_fg = "#AEAEB2"
            close_hover = "rgba(255, 255, 255, 0.14)"
        else:
            if self._active:
                bg = "#FFFFFF"
                border = "rgba(0, 0, 0, 0.12)"
                fg = "#1D1D1F"
            elif self._hovered:
                bg = "rgba(0, 0, 0, 0.06)"
                border = "transparent"
                fg = "#3A3A3C"
            else:
                bg = "rgba(0, 0, 0, 0.03)"
                border = "transparent"
                fg = "#6E6E73"
            close_fg = "#6E6E73"
            close_hover = "rgba(0, 0, 0, 0.09)"

        self.setStyleSheet(
            f"#browserTabChip {{ background-color: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
        )
        weight = "600" if self._active else "500"
        self.title_lbl.setStyleSheet(
            f"color: {fg}; font-size: 12px; font-weight: {weight}; background: transparent; border: none;"
        )
        self.close_btn.setVisible(self._active or self._hovered)
        self.close_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 8px; background: transparent; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: {close_hover}; }}"
        )
        self.close_btn.setIcon(make_icon("xmark", color=close_fg, size=10, weight="bold"))
        self.close_btn.setIconSize(QSize(10, 10))


class GameTabBar(QWidget):
    """Browser-style tab strip for open game sessions plus '+' button to add a tab."""

    tab_selected = Signal(int)
    tab_closed = Signal(int)
    new_tab_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._chips: dict[int, _BrowserTabChip] = {}
        self._theme: Optional[MacTheme] = None
        self._force_dark = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._tabs_lay = QHBoxLayout()
        self._tabs_lay.setContentsMargins(0, 0, 0, 0)
        self._tabs_lay.setSpacing(4)
        lay.addLayout(self._tabs_lay)

        self.add_btn = QPushButton()
        self.add_btn.setFixedSize(26, 26)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setToolTip("Open New Game Tab")
        self.add_btn.clicked.connect(self.new_tab_requested.emit)
        lay.addWidget(self.add_btn)

    def set_tabs(self, tabs: List[Tuple[int, str]], active_tab_id: Optional[int]) -> None:
        while self._tabs_lay.count():
            item = self._tabs_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._chips.clear()

        for tid, title in tabs:
            chip = _BrowserTabChip(tid, title, active=(tid == active_tab_id))
            chip.selected.connect(self.tab_selected.emit)
            chip.close_requested.connect(self.tab_closed.emit)
            if self._theme is not None:
                chip.apply_theme(self._theme, force_dark=self._force_dark)
            self._chips[tid] = chip
            self._tabs_lay.addWidget(chip)

    def apply_theme(self, theme: MacTheme, force_dark: bool = False) -> None:
        self._theme = theme
        self._force_dark = force_dark
        for chip in self._chips.values():
            chip.apply_theme(theme, force_dark=force_dark)

        dark = force_dark or theme.is_dark
        fg = "#D1D1D6" if dark else theme.text_secondary
        hover = "rgba(255, 255, 255, 0.12)" if dark else theme.toolbar_hover
        self.add_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 6px; background: transparent; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: {hover}; }}"
        )
        self.add_btn.setIcon(make_icon("plus", color=fg, size=13, weight="semibold"))
        self.add_btn.setIconSize(QSize(13, 13))


class SegmentedControl(QFrame):
    """Apple-style segmented pill control supporting text or icon segments."""

    changed = Signal(object)

    def __init__(
        self,
        options: List[Tuple[Any, str, Optional[str]]],
        initial: Any = None,
        parent: Optional[QWidget] = None,
    ):
        """options: list of (value, label_or_tooltip, icon_kind_or_None)."""
        super().__init__(parent)
        self._options = options
        self._current = initial if initial is not None else options[0][0]
        self._buttons: dict[Any, QPushButton] = {}
        self._theme: Optional[MacTheme] = None

        self.setFixedHeight(28)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)

        for value, text, icon_kind in options:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setChecked(value == self._current)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(22)
            if icon_kind:
                btn.setToolTip(text)
                btn.setFixedWidth(28)
            else:
                btn.setText(text)
                btn.setMinimumWidth(46)
            btn.clicked.connect(lambda _=False, v=value: self.set_value(v, emit=True))
            self._buttons[value] = btn
            lay.addWidget(btn)

    def value(self) -> Any:
        return self._current

    def set_value(self, value: Any, emit: bool = False) -> None:
        if value not in self._buttons:
            return
        self._current = value
        for v, btn in self._buttons.items():
            btn.setChecked(v == value)
        self._refresh_visuals()
        if emit:
            self.changed.emit(value)

    def apply_theme(self, theme: MacTheme) -> None:
        self._theme = theme
        self._refresh_visuals()

    def _refresh_visuals(self) -> None:
        if self._theme is None:
            return
        t = self._theme
        self.setStyleSheet(
            f"SegmentedControl {{ background-color: {t.segment_track}; border-radius: 8px; border: none; }}"
        )
        for v, _text, icon_kind in self._options:
            btn = self._buttons[v]
            active = v == self._current
            fg = t.text_primary if active else t.text_muted
            bg = t.segment_thumb if active else "transparent"
            weight = "600" if active else "500"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {bg}; color: {fg}; border: none; border-radius: 6px; "
                f"padding: 0 9px; font-size: 12px; font-weight: {weight}; }}"
                f"QPushButton:hover {{ color: {t.text_primary}; }}"
            )
            if icon_kind:
                btn.setIcon(make_icon(icon_kind, color=fg, size=14))
                btn.setIconSize(QSize(14, 14))


class SearchField(QFrame):
    """Native macOS rounded search input with SF Symbol icon and clear button."""

    textChanged = Signal(str)

    def __init__(self, placeholder: str = "Search games", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme: Optional[MacTheme] = None
        self.setFixedHeight(28)
        self.setMinimumWidth(160)
        self.setMaximumWidth(220)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 0, 6, 0)
        lay.setSpacing(6)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(14, 14)
        lay.addWidget(self.icon_lbl)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFrame(False)
        self.edit.textChanged.connect(self._on_text_changed)
        lay.addWidget(self.edit, 1)

        self.clear_btn = QPushButton()
        self.clear_btn.setFixedSize(16, 16)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setVisible(False)
        self.clear_btn.clicked.connect(self.edit.clear)
        lay.addWidget(self.clear_btn)

    def text(self) -> str:
        return self.edit.text()

    def _on_text_changed(self, text: str) -> None:
        self.clear_btn.setVisible(bool(text))
        self.textChanged.emit(text)

    def apply_theme(self, theme: MacTheme) -> None:
        self._theme = theme
        self.setStyleSheet(
            f"SearchField {{ background-color: {theme.input_bg}; border-radius: 8px; border: 1px solid {theme.separator}; }}"
        )
        self.edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {theme.text_primary}; font-size: 12px; selection-background-color: {theme.accent}; }}"
        )
        self.icon_lbl.setPixmap(sf_symbol_pixmap("search", color=theme.text_muted, size=13, weight="medium"))
        self.clear_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self.clear_btn.setIcon(make_icon("clear", color=theme.text_muted, size=13))
        self.clear_btn.setIconSize(QSize(13, 13))


class GameCard(QWidget):
    """macOS showcase game card with dynamic artwork gradient, rounded shadow, and hover play badge."""

    clicked = Signal(object)

    def __init__(self, rom: RomInfo, cover_size: int = 148, theme: Optional[MacTheme] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rom = rom
        self._cover_size = cover_size
        self._hovered = False
        self._theme = theme

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.cover_label)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(8, 0, 8, 0)
        text_box.setSpacing(2)

        self.title_label = QLabel(rom.title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(36)
        text_box.addWidget(self.title_label)

        sub_text = rom.publisher if rom.publisher else f"{rom.file_type} · {rom.size_human}"
        self.sub_label = QLabel(sub_text)
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        text_box.addWidget(self.sub_label)

        layout.addLayout(text_box)

        if theme is not None:
            self.apply_theme(theme)

    def apply_theme(self, theme: MacTheme) -> None:
        self._theme = theme
        self.title_label.setStyleSheet(
            f"color: {theme.text_primary}; font-size: 13px; font-weight: 600; background: transparent; border: none;"
        )
        self.sub_label.setStyleSheet(
            f"color: {theme.text_muted}; font-size: 11px; font-weight: 400; background: transparent; border: none;"
        )
        self._refresh_cover()

    def set_cover_size(self, size: int) -> None:
        self._cover_size = size
        self._refresh_cover()

    def _refresh_cover(self) -> None:
        if self._theme is None:
            return
        w = self._cover_size
        h = int(self._cover_size * 1.12)
        self.cover_label.setPixmap(make_cover_artwork(self.rom, w, h, self._theme, hovered=self._hovered))
        self.cover_label.setFixedSize(w + 16, h + 16)
        self.title_label.setFixedWidth(w)
        self.sub_label.setFixedWidth(w)
        self.setFixedWidth(w + 16)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._refresh_cover()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._refresh_cover()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.rom)
        super().mousePressEvent(event)


class GameListRow(QFrame):
    """Rich macOS list-view row with icon, metadata, and launch pill button."""

    play_clicked = Signal(object)

    def __init__(self, rom: RomInfo, theme: MacTheme, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rom = rom
        self._theme = theme
        self.setFixedHeight(58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        # Rounded thumbnail badge
        self.thumb = QLabel()
        self.thumb.setFixedSize(40, 40)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if rom.icon_image is not None:
            raw_pm = pil_to_qpixmap(rom.icon_image, 40)
            rounded = QPixmap(80, 80)
            rounded.setDevicePixelRatio(2.0)
            rounded.fill(Qt.GlobalColor.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, 40, 40), 9.0, 9.0)
            p.setClipPath(path)
            p.drawPixmap(0, 0, raw_pm)
            p.end()
            self.thumb.setPixmap(rounded)
        else:
            self.thumb.setPixmap(sf_symbol_pixmap("gamecontroller.fill", color=theme.text_muted, size=22))
            self.thumb.setStyleSheet(f"background-color: {theme.pill_bg}; border-radius: 9px;")
        lay.addWidget(self.thumb)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(2)

        title_lbl = QLabel(rom.title)
        title_lbl.setStyleSheet(f"color: {theme.text_primary}; font-size: 13px; font-weight: 600; background: transparent;")
        info_col.addWidget(title_lbl)

        parts = [p for p in [rom.publisher, rom.file_type, rom.size_human] if p]
        sub_lbl = QLabel(" · ".join(parts))
        sub_lbl.setStyleSheet(f"color: {theme.text_muted}; font-size: 11px; background: transparent;")
        info_col.addWidget(sub_lbl)

        lay.addLayout(info_col, 1)

        play_btn = QPushButton(" Play")
        play_btn.setIcon(make_icon("play", color="#FFFFFF", size=11, weight="bold"))
        play_btn.setIconSize(QSize(11, 11))
        play_btn.setFixedHeight(26)
        play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        play_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.accent}; color: #FFFFFF; border: none; "
            "border-radius: 13px; padding: 0 12px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover {{ background-color: {theme.accent_hover}; }}"
        )
        play_btn.clicked.connect(lambda: self.play_clicked.emit(self.rom))
        lay.addWidget(play_btn)

        self.setStyleSheet(
            f"GameListRow {{ background-color: transparent; border-radius: 10px; }}"
            f"GameListRow:hover {{ background-color: {theme.sidebar_hover}; }}"
        )

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self.rom)
        super().mouseDoubleClickEvent(event)


class ToastOverlay(QFrame):
    """Floating macOS HUD notification pill replacing old-school QStatusBar."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setVisible(False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 16, 8)
        lay.setSpacing(8)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(15, 15)
        lay.addWidget(self.icon_lbl)

        self.msg_lbl = QLabel()
        self.msg_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 500; background: transparent;")
        lay.addWidget(self.msg_lbl)

        self.setStyleSheet(
            "ToastOverlay { background-color: rgba(28, 28, 30, 0.88); "
            "border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 16px; }"
        )

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

    def show_message(self, text: str, icon_kind: str = "sparkles", accent_color: str = "#FFFFFF", duration_ms: int = 2600) -> None:
        self.msg_lbl.setText(text)
        self.icon_lbl.setPixmap(sf_symbol_pixmap(icon_kind, color=accent_color, size=14, weight="semibold"))
        self.adjustSize()
        self.reposition()
        self._hide_timer.stop()
        self._anim.stop()
        self._opacity.setOpacity(1.0)
        self.setVisible(True)
        self.raise_()
        self._hide_timer.start(duration_ms)

    def reposition(self) -> None:
        p = self.parentWidget()
        if p is None:
            return
        x = (p.width() - self.width()) // 2
        y = p.height() - self.height() - 20
        self.move(max(12, x), max(12, y))

    def _fade_out(self) -> None:
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._opacity.opacity() <= 0.01:
            self.setVisible(False)


class SettingsCard(QFrame):
    """macOS System Settings grouped inset card container."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._separators: List[QFrame] = []

    def add_row(self, row: QWidget) -> None:
        if self._layout.count() > 0:
            sep = QFrame()
            sep.setFixedHeight(1)
            self._separators.append(sep)
            self._layout.addWidget(sep)
        self._layout.addWidget(row)

    def apply_theme(self, theme: MacTheme) -> None:
        self.setStyleSheet(
            f"SettingsCard {{ background-color: {theme.card_bg}; "
            f"border: 1px solid {theme.card_border}; border-radius: 12px; }}"
        )
        for sep in self._separators:
            sep.setStyleSheet(f"background-color: {theme.separator}; margin-left: 52px;")


class SettingsRow(QWidget):
    """Single row inside a macOS SettingsCard with colored SF icon tile, title, subtitle, and control."""

    def __init__(
        self,
        icon_kind: str,
        badge_bg: str,
        title: str,
        subtitle: str = "",
        control: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        icon_tile = QLabel()
        icon_tile.setFixedSize(28, 28)
        icon_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_tile.setPixmap(sf_symbol_pixmap(icon_kind, color="#FFFFFF", size=15, weight="semibold"))
        icon_tile.setStyleSheet(f"background-color: {badge_bg}; border-radius: 7px;")
        lay.addWidget(icon_tile)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.title_lbl = QLabel(title)
        text_col.addWidget(self.title_lbl)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setVisible(bool(subtitle))
        text_col.addWidget(self.sub_lbl)

        lay.addLayout(text_col, 1)

        if control is not None:
            lay.addWidget(control)

    def apply_theme(self, theme: MacTheme) -> None:
        self.title_lbl.setStyleSheet(f"color: {theme.text_primary}; font-size: 13px; font-weight: 500; background: transparent;")
        self.sub_lbl.setStyleSheet(f"color: {theme.text_muted}; font-size: 11px; background: transparent;")


def make_keycap(text: str, theme: MacTheme) -> QLabel:
    """Create a crisp macOS keyboard shortcut cap badge."""
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"color: {theme.text_primary}; background-color: {theme.pill_bg}; "
        f"border: 1px solid {theme.pill_border}; border-radius: 5px; "
        "padding: 2px 7px; font-size: 11px; font-weight: 600;"
    )
    return lbl
