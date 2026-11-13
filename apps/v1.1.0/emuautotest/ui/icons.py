"""Modern Apple SF Symbols icon renderer for Retina macOS UI."""

from functools import lru_cache
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

from emuautotest.ui.theme import qcolor

try:
    import AppKit
    _HAS_APPKIT = True
except Exception:
    AppKit = None
    _HAS_APPKIT = False


# Semantic UI icon keys -> Apple SF Symbol names
_SYMBOL_MAP = {
    "sidebar": "sidebar.left",
    "home": "gamecontroller.fill",
    "home_outline": "gamecontroller",
    "recent": "clock.fill",
    "settings": "gearshape.fill",
    "grid": "square.grid.2x2",
    "list": "list.bullet",
    "quick_save": "square.and.arrow.down",
    "quick_load": "square.and.arrow.up",
    "record": "record.circle",
    "pause": "pause.circle.fill",
    "stop_save": "stop.circle.fill",
    "sound_on": "speaker.wave.2.fill",
    "sound_off": "speaker.slash.fill",
    "restart": "arrow.clockwise",
    "search": "magnifyingglass",
    "play": "play.fill",
    "play_circle": "play.circle.fill",
    "folder": "folder.fill",
    "video": "video.fill",
    "keyboard": "keyboard.fill",
    "fullscreen": "arrow.up.left.and.arrow.down.right",
    "exit_fullscreen": "arrow.down.right.and.arrow.up.left",
    "back": "chevron.left",
    "clear": "xmark.circle.fill",
    "xmark": "xmark",
    "plus": "plus",
}


def _resolve_symbol_name(kind: str) -> str:
    return _SYMBOL_MAP.get(kind, kind)


@lru_cache(maxsize=256)
def sf_symbol_pixmap(
    symbol_or_kind: str,
    color: str = "#1D1D1F",
    size: int = 18,
    weight: str = "medium",
) -> QPixmap:
    """Render an Apple SF Symbol into a crisp 2x Retina QPixmap centered in size x size."""
    symbol_name = _resolve_symbol_name(symbol_or_kind)

    if _HAS_APPKIT:
        try:
            ns_img = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol_name, None)
            if ns_img is not None:
                weight_map = {
                    "regular": AppKit.NSFontWeightRegular,
                    "medium": AppKit.NSFontWeightMedium,
                    "semibold": AppKit.NSFontWeightSemibold,
                    "bold": AppKit.NSFontWeightBold,
                }
                ns_weight = weight_map.get(weight, AppKit.NSFontWeightMedium)
                point_size = max(10.0, size * 0.82)
                cfg = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(point_size, ns_weight)

                qc = qcolor(color)
                ns_color = AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
                    qc.redF(), qc.greenF(), qc.blueF(), qc.alphaF()
                )
                color_cfg = AppKit.NSImageSymbolConfiguration.configurationWithHierarchicalColor_(ns_color)
                cfg = cfg.configurationByApplyingConfiguration_(color_cfg)
                sym = ns_img.imageWithSymbolConfiguration_(cfg)

                sz = sym.size()
                scale = 2
                canvas_px = size * scale
                rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
                    None,
                    canvas_px,
                    canvas_px,
                    8,
                    4,
                    True,
                    False,
                    AppKit.NSCalibratedRGBColorSpace,
                    0,
                    0,
                )
                ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
                AppKit.NSGraphicsContext.saveGraphicsState()
                AppKit.NSGraphicsContext.setCurrentContext_(ctx)

                # Center symbol proportionally inside the 2x canvas
                sym_w = max(1.0, float(sz.width) * scale)
                sym_h = max(1.0, float(sz.height) * scale)
                max_dim = canvas_px * 0.92
                fit = min(1.0, max_dim / max(sym_w, sym_h))
                draw_w = sym_w * fit
                draw_h = sym_h * fit
                dx = (canvas_px - draw_w) / 2.0
                dy = (canvas_px - draw_h) / 2.0

                sym.drawInRect_fromRect_operation_fraction_(
                    AppKit.NSMakeRect(dx, dy, draw_w, draw_h),
                    AppKit.NSZeroRect,
                    AppKit.NSCompositingOperationSourceOver,
                    1.0,
                )
                AppKit.NSGraphicsContext.restoreGraphicsState()

                tiff = rep.TIFFRepresentation()
                qimg = QImage.fromData(bytes(tiff))
                pm = QPixmap.fromImage(qimg)
                pm.setDevicePixelRatio(2.0)
                return pm
        except Exception:
            pass

    return _fallback_vector_pixmap(symbol_or_kind, color, size)


def _fallback_vector_pixmap(kind: str, color: str, size: int) -> QPixmap:
    """Minimal vector fallback if AppKit SF Symbols are unavailable."""
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    c = qcolor(color)
    p.setPen(QPen(c, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = float(size)
    m = 3.0
    if kind == "record":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(s / 2, s / 2), (s - 2 * m) / 2, (s - 2 * m) / 2)
    else:
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 3.0, 3.0)
    p.end()
    return pm


def make_icon(
    kind: str,
    color: str = "#3A3A3C",
    size: int = 18,
    weight: str = "medium",
    active_color: Optional[str] = None,
) -> QIcon:
    """Create a Retina macOS SF Symbol QIcon (with optional checked/active state tint)."""
    if kind == "record" and color == "#3A3A3C":
        color = "#FF3B30"
    elif kind == "stop_save" and color == "#3A3A3C":
        color = "#FF3B30"

    icon = QIcon(sf_symbol_pixmap(kind, color=color, size=size, weight=weight))
    if active_color:
        active_pm = sf_symbol_pixmap(kind, color=active_color, size=size, weight=weight)
        icon.addPixmap(active_pm, QIcon.Mode.Normal, QIcon.State.On)
        icon.addPixmap(active_pm, QIcon.Mode.Active, QIcon.State.On)
    return icon
