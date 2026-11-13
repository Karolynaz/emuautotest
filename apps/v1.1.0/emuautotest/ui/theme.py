"""Native macOS theme tokens and AppKit glass/window integration."""

import re
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QMainWindow, QWidget

try:
    import AppKit
    import objc
    _HAS_APPKIT = True
except Exception:
    AppKit = None
    objc = None
    _HAS_APPKIT = False


@dataclass(frozen=True)
class MacTheme:
    is_dark: bool
    # Window & surfaces
    content_bg: str
    header_bg: str
    card_bg: str
    card_hover_bg: str
    grouped_bg: str
    input_bg: str
    input_focus_bg: str
    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    # Accents & states
    accent: str
    accent_hover: str
    accent_soft: str
    accent_text: str
    danger: str
    danger_soft: str
    success: str
    # Borders & dividers
    separator: str
    sidebar_divider: str
    card_border: str
    card_hover_border: str
    # Interactive controls
    sidebar_hover: str
    sidebar_active: str
    toolbar_hover: str
    toolbar_pressed: str
    toolbar_active_bg: str
    segment_track: str
    segment_thumb: str
    pill_bg: str
    pill_border: str
    shadow_rgba: tuple[int, int, int, int]
    shadow_hover_rgba: tuple[int, int, int, int]


LIGHT_THEME = MacTheme(
    is_dark=False,
    content_bg="#FFFFFF",
    header_bg="rgba(255, 255, 255, 0.92)",
    card_bg="#FFFFFF",
    card_hover_bg="#FAFAFC",
    grouped_bg="#F5F5F7",
    input_bg="rgba(0, 0, 0, 0.05)",
    input_focus_bg="#FFFFFF",
    text_primary="#1D1D1F",
    text_secondary="#48484A",
    text_muted="#8E8E93",
    accent="#007AFF",
    accent_hover="#0066D6",
    accent_soft="rgba(0, 122, 255, 0.13)",
    accent_text="#0066CC",
    danger="#FF3B30",
    danger_soft="rgba(255, 59, 48, 0.12)",
    success="#34C759",
    separator="rgba(0, 0, 0, 0.07)",
    sidebar_divider="rgba(0, 0, 0, 0.09)",
    card_border="rgba(0, 0, 0, 0.08)",
    card_hover_border="rgba(0, 122, 255, 0.45)",
    sidebar_hover="rgba(0, 0, 0, 0.05)",
    sidebar_active="rgba(0, 122, 255, 0.14)",
    toolbar_hover="rgba(0, 0, 0, 0.06)",
    toolbar_pressed="rgba(0, 0, 0, 0.11)",
    toolbar_active_bg="rgba(0, 122, 255, 0.13)",
    segment_track="rgba(0, 0, 0, 0.06)",
    segment_thumb="#FFFFFF",
    pill_bg="rgba(0, 0, 0, 0.05)",
    pill_border="rgba(0, 0, 0, 0.08)",
    shadow_rgba=(0, 0, 0, 20),
    shadow_hover_rgba=(0, 0, 0, 38),
)

DARK_THEME = MacTheme(
    is_dark=True,
    content_bg="#1E1E20",
    header_bg="rgba(30, 30, 32, 0.90)",
    card_bg="#28282B",
    card_hover_bg="#303034",
    grouped_bg="#252528",
    input_bg="rgba(255, 255, 255, 0.08)",
    input_focus_bg="#2C2C30",
    text_primary="#F5F5F7",
    text_secondary="#C7C7CC",
    text_muted="#8E8E93",
    accent="#0A84FF",
    accent_hover="#409CFF",
    accent_soft="rgba(10, 132, 255, 0.22)",
    accent_text="#409CFF",
    danger="#FF453A",
    danger_soft="rgba(255, 69, 58, 0.20)",
    success="#30D158",
    separator="rgba(255, 255, 255, 0.08)",
    sidebar_divider="rgba(255, 255, 255, 0.10)",
    card_border="rgba(255, 255, 255, 0.09)",
    card_hover_border="rgba(10, 132, 255, 0.60)",
    sidebar_hover="rgba(255, 255, 255, 0.07)",
    sidebar_active="rgba(10, 132, 255, 0.24)",
    toolbar_hover="rgba(255, 255, 255, 0.09)",
    toolbar_pressed="rgba(255, 255, 255, 0.15)",
    toolbar_active_bg="rgba(10, 132, 255, 0.22)",
    segment_track="rgba(255, 255, 255, 0.08)",
    segment_thumb="#3A3A3E",
    pill_bg="rgba(255, 255, 255, 0.08)",
    pill_border="rgba(255, 255, 255, 0.12)",
    shadow_rgba=(0, 0, 0, 55),
    shadow_hover_rgba=(0, 0, 0, 90),
)


def qcolor(css: str) -> QColor:
    """Parse hex (#RRGGBB) or CSS rgba(r, g, b, a) strings into a valid QColor."""
    s = css.strip()
    m = re.match(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)$", s)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a_raw = float(m.group(4)) if m.group(4) is not None else 1.0
        a = int(round(a_raw * 255)) if a_raw <= 1.0 else int(round(a_raw))
        return QColor(r, g, b, max(0, min(255, a)))
    return QColor(s)


def is_macos_dark_mode() -> bool:
    """Detect whether macOS is currently using Dark appearance."""
    app = QGuiApplication.instance()
    if app is not None:
        try:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except Exception:
            pass
    if _HAS_APPKIT:
        try:
            name = AppKit.NSApplication.sharedApplication().effectiveAppearance().name()
            return "Dark" in str(name)
        except Exception:
            pass
    return False


def get_theme() -> MacTheme:
    return DARK_THEME if is_macos_dark_mode() else LIGHT_THEME


def apply_macos_window_glass(window: QMainWindow) -> Optional[object]:
    """Configure full-size content view, transparent titlebar, and NSVisualEffectView behind Qt.

    Returns the installed NSVisualEffectView (or None if unavailable).
    """
    if not _HAS_APPKIT:
        return None
    try:
        ns_view = objc.objc_object(c_void_p=int(window.winId()))
        ns_win = ns_view.window()
        if ns_win is None:
            return None

        ns_win.setTitlebarAppearsTransparent_(True)
        ns_win.setTitleVisibility_(AppKit.NSWindowTitleHidden)
        ns_win.setStyleMask_(ns_win.styleMask() | AppKit.NSWindowStyleMaskFullSizeContentView)
        ns_win.setOpaque_(False)
        ns_win.setBackgroundColor_(AppKit.NSColor.clearColor())

        existing = getattr(window, "_ns_visual_effect_view", None)
        if existing is not None:
            return existing

        parent_view = ns_view.superview()
        if parent_view is None:
            return None

        vev = AppKit.NSVisualEffectView.alloc().initWithFrame_(ns_view.frame())
        vev.setMaterial_(AppKit.NSVisualEffectMaterialSidebar)
        vev.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        vev.setState_(AppKit.NSVisualEffectStateFollowsWindowActiveState)
        vev.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        parent_view.addSubview_positioned_relativeTo_(vev, AppKit.NSWindowBelow, ns_view)
        window._ns_visual_effect_view = vev
        return vev
    except Exception:
        return None


def set_glass_enabled(window: QMainWindow, enabled: bool) -> None:
    """Show or hide the underlying NSVisualEffectView (e.g. hide in fullscreen theater mode)."""
    vev = getattr(window, "_ns_visual_effect_view", None)
    if vev is not None:
        try:
            vev.setHidden_(not enabled)
        except Exception:
            pass


def start_window_drag(widget: QWidget) -> None:
    """Trigger native macOS window drag when dragging the unified title/header bar."""
    win = widget.window()
    if win is not None and win.windowHandle() is not None:
        win.windowHandle().startSystemMove()
