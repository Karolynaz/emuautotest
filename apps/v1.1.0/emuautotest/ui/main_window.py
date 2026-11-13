import subprocess
import threading
import time
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from emuautotest.adapters.azahar_3ds import Azahar3DSAdapter
from emuautotest.config import RECORDINGS_DIR, ROMS_DIR
from emuautotest.core.input_manager import _app_services, kCGHIDEventTap
from emuautotest.ui.gameplay_widget import GameplayWidget
from emuautotest.ui.icons import sf_symbol_pixmap
from emuautotest.ui.rom_metadata import RomInfo, discover_all_roms, discover_recent_roms
from emuautotest.ui.theme import (
    MacTheme,
    apply_macos_window_glass,
    get_theme,
    set_glass_enabled,
)
from emuautotest.ui.widgets import (
    DraggableHeader,
    GameCard,
    GameListRow,
    GameTabBar,
    SearchField,
    SegmentedControl,
    SettingsCard,
    SettingsRow,
    SidebarNavItem,
    ToastOverlay,
    ToolbarIconButton,
    make_keycap,
)

SIDEBAR_WIDTH = 244
GAMEPLAY_BG = "#111215"


@dataclass
class GameTabSession:
    tab_id: int
    rom: Optional[RomInfo]
    title: str


class EmuautotestMainWindow(QMainWindow):
    """Native macOS desktop UI for Emuautotest with frosted glass sidebar, SF Symbols, and browser game tabs."""

    game_launched = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.adapter = Azahar3DSAdapter()
        self._theme: MacTheme = get_theme()
        self._glass_applied = False
        self._sidebar_visible = True
        self._view_mode = "grid"  # "grid" or "list"
        self._library_section = "home"  # "home" or "recent"
        self._search_query = ""
        self._cover_size = 152
        self._is_muted = False
        self._is_recording = False
        self._rec_format = "mp4"
        self._rec_fps = 30
        self._rec_scale = 1

        self._tabs: List[GameTabSession] = []
        self._active_tab_id: Optional[int] = None
        self._next_tab_id = 1
        self._in_gameplay = False

        self._all_roms: List[RomInfo] = []
        self._filtered_roms: List[RomInfo] = []
        self._cards: List[GameCard] = []
        self._list_rows: List[GameListRow] = []
        self._settings_cards: List[SettingsCard] = []
        self._settings_rows: List[SettingsRow] = []
        self._settings_section_labels: List[QLabel] = []
        self._settings_action_btns: List[QPushButton] = []

        self.setWindowTitle("Emuautotest")
        self.setMinimumSize(880, 560)
        self.resize(1080, 710)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.game_launched.connect(self._on_game_launched)

        app = QGuiApplication.instance()
        if app is not None and hasattr(app.styleHints(), "colorSchemeChanged"):
            app.styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)

        self._build_body()
        self._apply_theme()
        self._reload_library()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._glass_applied:
            apply_macos_window_glass(self)
            self._glass_applied = True

    def _on_system_theme_changed(self, *_args) -> None:
        self._theme = get_theme()
        self._apply_theme()
        self._rebuild_cards_and_list()

    # --- UI Construction ---

    def _build_body(self) -> None:
        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Left Frosted Glass Sidebar (backed by NSVisualEffectView)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("glassSidebar")
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sb_layout = QVBoxLayout(self.sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 12)
        sb_layout.setSpacing(0)

        # Sidebar top header (46px unified row: traffic lights + Show/Hide + FullScreen + Save + Load + Record)
        self.sb_header = DraggableHeader()
        self.sb_header.setFixedHeight(46)
        self.sb_head_lay = QHBoxLayout(self.sb_header)
        self.sb_head_lay.setContentsMargins(10, 0, 8, 0)
        self.sb_head_lay.setSpacing(2)

        # Shared left control cluster (reparents seamlessly to right header when sidebar is collapsed)
        self.left_controls = QWidget()
        self.left_controls.setStyleSheet("background: transparent;")
        lc_lay = QHBoxLayout(self.left_controls)
        lc_lay.setContentsMargins(0, 0, 0, 0)
        lc_lay.setSpacing(2)

        self.traffic_spacer = QWidget()
        self.traffic_spacer.setFixedWidth(64)
        lc_lay.addWidget(self.traffic_spacer)

        self.btn_sidebar = ToolbarIconButton("sidebar", "Show / Hide Sidebar", size=16)
        self.btn_sidebar.clicked.connect(self._toggle_sidebar)
        lc_lay.addWidget(self.btn_sidebar)

        self.btn_fullscreen = ToolbarIconButton("fullscreen", "Full Screen", size=14)
        self.btn_fullscreen.setVisible(False)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        lc_lay.addWidget(self.btn_fullscreen)

        self.btn_quick_save = ToolbarIconButton("quick_save", "Quick Save (⌘C)", size=15)
        self.btn_quick_save.setVisible(False)
        self.btn_quick_save.clicked.connect(self._quick_save)
        lc_lay.addWidget(self.btn_quick_save)

        self.btn_quick_load = ToolbarIconButton("quick_load", "Quick Load (⌘V)", size=15)
        self.btn_quick_load.setVisible(False)
        self.btn_quick_load.clicked.connect(self._quick_load)
        lc_lay.addWidget(self.btn_quick_load)

        self.btn_record = ToolbarIconButton("record", "Record Gameplay / Pause", size=15)
        self.btn_record.setVisible(False)
        self.btn_record.clicked.connect(self._toggle_record)
        lc_lay.addWidget(self.btn_record)

        self.btn_stop_record = ToolbarIconButton("stop_save", "Stop Recording & Save", size=15)
        self.btn_stop_record.setVisible(False)
        self.btn_stop_record.clicked.connect(self._stop_and_save_recording)
        lc_lay.addWidget(self.btn_stop_record)

        self.sb_head_lay.addWidget(self.left_controls)
        self.sb_head_lay.addStretch()
        sb_layout.addWidget(self.sb_header)

        # Sidebar navigation list (Home + Recently Played at top; Settings pinned at bottom)
        nav_wrap = QWidget()
        nav_wrap.setStyleSheet("background: transparent;")
        nav_lay = QVBoxLayout(nav_wrap)
        nav_lay.setContentsMargins(10, 8, 10, 4)
        nav_lay.setSpacing(4)

        self.lbl_lib_section = QLabel("LIBRARY")
        self.lbl_lib_section.setContentsMargins(10, 2, 10, 4)
        nav_lay.addWidget(self.lbl_lib_section)

        self.btn_home = SidebarNavItem("home", "All Games")
        self.btn_home.setChecked(True)
        self.btn_home.clicked.connect(lambda: self._switch_sidebar("home"))
        nav_lay.addWidget(self.btn_home)

        self.btn_recent = SidebarNavItem("recent", "Recently Played")
        self.btn_recent.clicked.connect(lambda: self._switch_sidebar("recent"))
        nav_lay.addWidget(self.btn_recent)

        nav_lay.addStretch()

        self.btn_settings = SidebarNavItem("settings", "Settings")
        self.btn_settings.clicked.connect(lambda: self._switch_sidebar("settings"))
        nav_lay.addWidget(self.btn_settings)

        sb_layout.addWidget(nav_wrap, 1)
        root_layout.addWidget(self.sidebar)

        # Right Main Content Pane
        self.right_pane = QFrame()
        self.right_pane.setObjectName("rightPane")
        self.right_pane.setAutoFillBackground(True)
        right_lay = QVBoxLayout(self.right_pane)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        # Unified 46px Top Header over the right pane (matches Gameplay dark bg during gameplay!)
        self.header = DraggableHeader()
        self.header.setObjectName("unifiedHeader")
        self.header.setFixedHeight(46)
        self.head_lay = QHBoxLayout(self.header)
        self.head_lay.setContentsMargins(14, 0, 14, 0)
        self.head_lay.setSpacing(8)

        self.header_title = QLabel("All Games")
        self.head_lay.addWidget(self.header_title)

        self.tab_bar = GameTabBar()
        self.tab_bar.setVisible(False)
        self.tab_bar.tab_selected.connect(self._on_tab_selected)
        self.tab_bar.tab_closed.connect(self._close_tab)
        self.tab_bar.new_tab_requested.connect(self._on_new_tab_requested)
        self.head_lay.addWidget(self.tab_bar)

        self.rec_badge = QLabel("● REC")
        self.rec_badge.setVisible(False)
        self.head_lay.addWidget(self.rec_badge)

        self.head_lay.addStretch()

        self.search_field = SearchField("Search games")
        self.search_field.textChanged.connect(self._on_search_changed)
        self.head_lay.addWidget(self.search_field)

        self.view_seg = SegmentedControl(
            [
                ("grid", "Thumbnails View", "grid"),
                ("list", "List View", "list"),
            ],
            initial="grid",
        )
        self.view_seg.changed.connect(self._set_view_mode)
        self.head_lay.addWidget(self.view_seg)

        # Cover size slider (shown in header during Library Grid view)
        self.slider_wrap = QWidget()
        self.slider_wrap.setStyleSheet("background: transparent;")
        slider_lay = QHBoxLayout(self.slider_wrap)
        slider_lay.setContentsMargins(4, 0, 2, 0)
        slider_lay.setSpacing(6)

        self.lbl_small_grid = QLabel()
        self.lbl_small_grid.setFixedSize(13, 13)
        slider_lay.addWidget(self.lbl_small_grid)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(104, 216)
        self.size_slider.setValue(self._cover_size)
        self.size_slider.setFixedWidth(96)
        self.size_slider.setToolTip("Cover Size")
        self.size_slider.valueChanged.connect(self._on_cover_size_changed)
        slider_lay.addWidget(self.size_slider)

        self.lbl_large_grid = QLabel()
        self.lbl_large_grid.setFixedSize(16, 16)
        slider_lay.addWidget(self.lbl_large_grid)

        self.head_lay.addWidget(self.slider_wrap)

        self.header_sep = QFrame()
        self.header_sep.setFixedSize(1, 16)
        self.head_lay.addWidget(self.header_sep)

        # Right-side action buttons: Mute always visible; Restart and Close (X) shown when game is active
        self.btn_mute = ToolbarIconButton("sound_on", "Mute All Sounds (⌘M)", size=15)
        self.btn_mute.clicked.connect(self._toggle_mute)
        self.head_lay.addWidget(self.btn_mute)

        self.btn_restart = ToolbarIconButton("restart", "Restart Emulation", size=15)
        self.btn_restart.setVisible(False)
        self.btn_restart.clicked.connect(self._restart_emulation)
        self.head_lay.addWidget(self.btn_restart)

        self.btn_close_game = ToolbarIconButton("xmark", "Close Game / Back to Games", size=14)
        self.btn_close_game.setVisible(False)
        self.btn_close_game.clicked.connect(self._close_active_or_stop_game)
        self.head_lay.addWidget(self.btn_close_game)

        right_lay.addWidget(self.header)

        # Main Content Stack (0: Library, 1: Gameplay, 2: Settings)
        self.stack = QStackedWidget()
        self.library_page = self._build_library_page()
        self.gameplay_page = GameplayWidget(self.adapter)
        self.gameplay_page.stop_requested.connect(self._close_active_or_stop_game)
        self.gameplay_page.fullscreen_requested.connect(self._toggle_fullscreen)
        self.settings_page = self._build_settings_page()

        self.stack.addWidget(self.library_page)   # index 0
        self.stack.addWidget(self.gameplay_page)  # index 1
        self.stack.addWidget(self.settings_page)  # index 2
        right_lay.addWidget(self.stack, 1)

        root_layout.addWidget(self.right_pane, 1)

        # Floating HUD toast pill over the right content pane
        self.toast = ToastOverlay(self.right_pane)

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("libraryPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 14, 24, 16)
        layout.setSpacing(10)

        sub_bar = QHBoxLayout()
        sub_bar.setContentsMargins(2, 0, 2, 0)

        self.lib_count_lbl = QLabel("0 games")
        sub_bar.addWidget(self.lib_count_lbl)
        sub_bar.addStretch()
        layout.addLayout(sub_bar)

        self.view_stack = QStackedWidget()

        # Grid ScrollArea
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setObjectName("gridScroll")
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.grid_container = QWidget()
        self.grid_container.setObjectName("gridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 2, 8, 12)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.grid_scroll.setWidget(self.grid_container)
        self.view_stack.addWidget(self.grid_scroll)

        # List ScrollArea
        self.list_scroll = QScrollArea()
        self.list_scroll.setObjectName("listScroll")
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.list_container = QWidget()
        self.list_container.setObjectName("listContainer")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 2, 6, 12)
        self.list_layout.setSpacing(4)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_scroll.setWidget(self.list_container)
        self.view_stack.addWidget(self.list_scroll)

        # Empty State
        self.empty_state = QWidget()
        empty_lay = QVBoxLayout(self.empty_state)
        empty_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lay.setSpacing(8)
        self.empty_icon_lbl = QLabel()
        self.empty_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lay.addWidget(self.empty_icon_lbl)
        self.empty_title_lbl = QLabel("No Games Found")
        self.empty_title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lay.addWidget(self.empty_title_lbl)
        self.empty_sub_lbl = QLabel("Add .3ds or .3dsx files to your ROMs directory to get started.")
        self.empty_sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lay.addWidget(self.empty_sub_lbl)
        self.view_stack.addWidget(self.empty_state)

        layout.addWidget(self.view_stack, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(32, 24, 32, 32)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        column = QWidget()
        column.setMaximumWidth(640)
        column.setMinimumWidth(520)
        col_lay = QVBoxLayout(column)
        col_lay.setContentsMargins(0, 0, 0, 0)
        col_lay.setSpacing(18)

        lbl_rec = QLabel("VIDEO RECORDING")
        lbl_rec.setContentsMargins(8, 0, 0, 0)
        self._settings_section_labels.append(lbl_rec)
        col_lay.addWidget(lbl_rec)

        rec_card = SettingsCard()
        self.seg_format = SegmentedControl([("mp4", "MP4", None), ("gif", "GIF", None)], initial="mp4")
        self.seg_format.changed.connect(self._on_rec_format_changed)
        row_fmt = SettingsRow(
            "video",
            "#FF3B30",
            "Recording Format",
            "MP4 for crisp 60fps video, GIF for lightweight shareable clips",
            control=self.seg_format,
        )
        rec_card.add_row(row_fmt)
        self._settings_rows.append(row_fmt)

        self.seg_fps = SegmentedControl([(15, "15 fps", None), (30, "30 fps", None), (60, "60 fps", None)], initial=30)
        self.seg_fps.changed.connect(self._on_rec_fps_changed)
        row_fps = SettingsRow(
            "recent",
            "#FF9500",
            "Frame Rate",
            "Target capture frame rate during gameplay recording",
            control=self.seg_fps,
        )
        rec_card.add_row(row_fps)
        self._settings_rows.append(row_fps)

        self.seg_scale = SegmentedControl([(1, "1× Native", None), (2, "2× HD", None)], initial=1)
        self.seg_scale.changed.connect(self._on_rec_scale_changed)
        row_scale = SettingsRow(
            "grid",
            "#5856D6",
            "Capture Resolution",
            "Output scaling factor relative to native 3DS 400×480 pixels",
            control=self.seg_scale,
        )
        rec_card.add_row(row_scale)
        self._settings_rows.append(row_scale)

        self._settings_cards.append(rec_card)
        col_lay.addWidget(rec_card)

        lbl_paths = QLabel("STORAGE & FOLDERS")
        lbl_paths.setContentsMargins(8, 6, 0, 0)
        self._settings_section_labels.append(lbl_paths)
        col_lay.addWidget(lbl_paths)

        paths_card = SettingsCard()
        btn_open_roms = QPushButton("Show in Finder")
        btn_open_roms.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_roms.clicked.connect(lambda: subprocess.Popen(["open", str(ROMS_DIR)]))
        self._settings_action_btns.append(btn_open_roms)
        row_roms = SettingsRow(
            "home",
            "#007AFF",
            "ROMs Directory",
            str(ROMS_DIR),
            control=btn_open_roms,
        )
        paths_card.add_row(row_roms)
        self._settings_rows.append(row_roms)

        btn_open_rec = QPushButton("Show in Finder")
        btn_open_rec.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_rec.clicked.connect(lambda: subprocess.Popen(["open", str(RECORDINGS_DIR)]))
        self._settings_action_btns.append(btn_open_rec)
        row_rec_dir = SettingsRow(
            "folder",
            "#34C759",
            "Recordings Folder",
            str(RECORDINGS_DIR),
            control=btn_open_rec,
        )
        paths_card.add_row(row_rec_dir)
        self._settings_rows.append(row_rec_dir)

        self._settings_cards.append(paths_card)
        col_lay.addWidget(paths_card)

        lbl_ctrl = QLabel("KEYBOARD & TOUCH CONTROLS")
        lbl_ctrl.setContentsMargins(8, 6, 0, 0)
        self._settings_section_labels.append(lbl_ctrl)
        col_lay.addWidget(lbl_ctrl)

        self.controls_card = SettingsCard()
        self._controls_specs = [
            ("home", "#5E5CE6", "Circle Pad", "Analog directional movement", ["↑  ↓  ←  →"]),
            ("keyboard", "#32ADE6", "Face Buttons (A / B / X / Y)", "Standard 3DS action buttons", ["A", "S", "W", "D"]),
            ("keyboard", "#AF52DE", "Shoulder Triggers (L / R)", "Left and right bumpers", ["Q", "E"]),
            ("keyboard", "#8E8E93", "Start & Select", "System pause and menu keys", ["Return", "Shift"]),
            ("quick_save", "#30B0C7", "Quick Save / Load", "Instant state save & restore", ["⌘C", "⌘V"]),
        ]
        self._keycap_containers: List[tuple[QHBoxLayout, List[str]]] = []
        for icon_kind, badge_bg, title, sub, keys in self._controls_specs:
            key_wrap = QWidget()
            key_lay = QHBoxLayout(key_wrap)
            key_lay.setContentsMargins(0, 0, 0, 0)
            key_lay.setSpacing(5)
            self._keycap_containers.append((key_lay, keys))
            row = SettingsRow(icon_kind, badge_bg, title, sub, control=key_wrap)
            self.controls_card.add_row(row)
            self._settings_rows.append(row)

        self._settings_cards.append(self.controls_card)
        col_lay.addWidget(self.controls_card)
        col_lay.addStretch()

        outer.addWidget(column)
        scroll.setWidget(container)
        self._settings_container = container
        self._settings_scroll = scroll
        return scroll

    # --- Theme Application ---

    def _apply_theme(self) -> None:
        t = self._theme

        scrollbar_qss = (
            "QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px 4px 0; }"
            "QScrollBar::handle:vertical { background: rgba(128,128,128,0.32); border-radius: 4px; min-height: 28px; }"
            "QScrollBar::handle:vertical:hover { background: rgba(128,128,128,0.52); }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, "
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; height: 0px; }"
        )
        self.setStyleSheet(scrollbar_qss)

        # Frosted glass sidebar
        self.sidebar.setStyleSheet(
            f"#glassSidebar {{ background: transparent; border-right: 1px solid {t.sidebar_divider}; }}"
        )
        section_lbl_css = f"color: {t.text_muted}; font-size: 11px; font-weight: 600; letter-spacing: 0.4px; background: transparent; border: none;"
        self.lbl_lib_section.setStyleSheet(section_lbl_css)

        for item in (self.btn_home, self.btn_recent, self.btn_settings):
            item.apply_theme(t)

        # Right pane & header (in Gameplay mode, header blends seamlessly into #111215 with zero white strip!)
        self._apply_header_theme()

        # Library page (scoped by objectName so background doesn't cascade into rounded cards)
        self.library_page.setStyleSheet(f"#libraryPage {{ background-color: {t.content_bg}; }}")
        self.grid_scroll.setStyleSheet(f"#gridScroll {{ background-color: {t.content_bg}; border: none; }}")
        self.grid_container.setStyleSheet(f"#gridContainer {{ background-color: {t.content_bg}; }}")
        self.list_scroll.setStyleSheet(f"#listScroll {{ background-color: {t.content_bg}; border: none; }}")
        self.list_container.setStyleSheet(f"#listContainer {{ background-color: {t.content_bg}; }}")
        self.lib_count_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px; font-weight: 500;")
        self.lbl_small_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_small_grid.setPixmap(sf_symbol_pixmap("grid", color=t.text_muted, size=10))
        self.lbl_large_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_large_grid.setPixmap(sf_symbol_pixmap("grid", color=t.text_muted, size=16))

        thumb_border = "rgba(255,255,255,0.22)" if t.is_dark else "rgba(0,0,0,0.18)"
        self.size_slider.setStyleSheet(
            "QSlider { background: transparent; }"
            f"QSlider::groove:horizontal {{ height: 4px; background: {t.segment_track}; border-radius: 2px; }}"
            f"QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; "
            f"background: {t.segment_thumb}; border: 1px solid {thumb_border}; }}"
        )

        self.empty_icon_lbl.setPixmap(sf_symbol_pixmap("home_outline", color=t.text_muted, size=42))
        self.empty_title_lbl.setStyleSheet(f"color: {t.text_primary}; font-size: 15px; font-weight: 600;")
        self.empty_sub_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")

        # Settings page
        self._settings_scroll.setStyleSheet(f"background-color: {t.grouped_bg}; border: none;")
        self._settings_container.setStyleSheet(f"background-color: {t.grouped_bg};")
        for lbl in self._settings_section_labels:
            lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 11px; font-weight: 600; letter-spacing: 0.4px;")
        for card in self._settings_cards:
            card.apply_theme(t)
        for row in self._settings_rows:
            row.apply_theme(t)
        for seg in (self.seg_format, self.seg_fps, self.seg_scale):
            seg.apply_theme(t)
        for btn in self._settings_action_btns:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {t.pill_bg}; color: {t.text_primary}; "
                f"border: 1px solid {t.pill_border}; border-radius: 7px; padding: 5px 12px; font-size: 12px; font-weight: 500; }}"
                f"QPushButton:hover {{ background-color: {t.toolbar_hover}; }}"
            )
        for key_lay, keys in self._keycap_containers:
            while key_lay.count():
                item = key_lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for k in keys:
                key_lay.addWidget(make_keycap(k, t))

    def _apply_header_theme(self) -> None:
        t = self._theme
        dark_gp = self._in_gameplay

        pane_bg = GAMEPLAY_BG if dark_gp else t.content_bg
        self.right_pane.setStyleSheet(f"#rightPane {{ background-color: {pane_bg}; border: none; }}")

        if dark_gp:
            self.header.setStyleSheet(f"#unifiedHeader {{ background-color: {GAMEPLAY_BG}; border: none; }}")
        else:
            hdr_bg = t.grouped_bg if self.stack.currentIndex() == 2 else t.content_bg
            self.header.setStyleSheet(
                f"#unifiedHeader {{ background-color: {hdr_bg}; border-bottom: 1px solid {t.separator}; }}"
            )

        self.header_title.setStyleSheet(
            f"color: {t.text_primary}; font-size: 15px; font-weight: 600; background: transparent;"
        )
        self.rec_badge.setStyleSheet(
            f"color: {t.danger}; background-color: {t.danger_soft}; border-radius: 9px; "
            "padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        self.header_sep.setStyleSheet(f"background-color: {t.separator};")

        # Left controls adapt if moved into dark gameplay header when sidebar is hidden
        left_in_dark = dark_gp and not self._sidebar_visible
        for btn in (
            self.btn_sidebar,
            self.btn_fullscreen,
            self.btn_quick_save,
            self.btn_quick_load,
            self.btn_record,
            self.btn_stop_record,
        ):
            btn.apply_theme(t, force_dark=left_in_dark)

        for btn in (self.btn_mute, self.btn_restart, self.btn_close_game):
            btn.apply_theme(t, force_dark=dark_gp)

        self.tab_bar.apply_theme(t, force_dark=dark_gp)
        self.search_field.apply_theme(t)
        self.view_seg.apply_theme(t)

    # --- Status & Notifications ---

    def _notify(self, message: str, icon_kind: str = "sparkles", color: str = "#FFFFFF") -> None:
        self.toast.show_message(message, icon_kind=icon_kind, accent_color=color)

    # --- Sidebar & View Controls ---

    def _toggle_sidebar(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        if self._sidebar_visible:
            self.head_lay.removeWidget(self.left_controls)
            self.sb_head_lay.insertWidget(0, self.left_controls)
            self.sidebar.setVisible(True)
        else:
            self.sb_head_lay.removeWidget(self.left_controls)
            self.head_lay.insertWidget(0, self.left_controls)
            self.sidebar.setVisible(False)
        self._apply_header_theme()
        if self._cards:
            self._relayout_grid()
        self.toast.reposition()

    def _switch_sidebar(self, section: str) -> None:
        self._in_gameplay = False
        self.btn_home.setChecked(section == "home")
        self.btn_recent.setChecked(section == "recent")
        self.btn_settings.setChecked(section == "settings")

        is_lib = section in ("home", "recent")
        has_tabs = len(self._tabs) > 0
        self.header_title.setVisible(not has_tabs)
        self.tab_bar.setVisible(has_tabs)
        self.search_field.setVisible(is_lib)
        self.view_seg.setVisible(is_lib)
        self.slider_wrap.setVisible(is_lib and self._view_mode == "grid")
        self.header_sep.setVisible(is_lib)
        self.btn_fullscreen.setVisible(False)
        self.btn_quick_save.setVisible(False)
        self.btn_quick_load.setVisible(False)
        self.btn_record.setVisible(self._is_recording)
        self.btn_stop_record.setVisible(self._is_recording)
        self.btn_restart.setVisible(False)
        self.btn_close_game.setVisible(False)

        if section == "settings":
            self.header_title.setText("Settings")
            self.stack.setCurrentIndex(2)
            self._apply_header_theme()
            return

        self._library_section = section
        self.header_title.setText("Recently Played" if section == "recent" else "All Games")
        self._reload_library()
        self.stack.setCurrentIndex(0)
        self._apply_header_theme()

    def _set_view_mode(self, mode: str) -> None:
        self._view_mode = mode
        self.slider_wrap.setVisible((not self._in_gameplay) and (self.stack.currentIndex() == 0) and (mode == "grid"))
        self._update_library_empty_or_view()

    def _on_search_changed(self, text: str) -> None:
        self._search_query = text.strip().lower()
        self._apply_search_filter()

    def _on_cover_size_changed(self, value: int) -> None:
        self._cover_size = value
        for card in self._cards:
            card.set_cover_size(value)
        self._relayout_grid()

    def _on_rec_format_changed(self, fmt: str) -> None:
        self._rec_format = fmt
        self._notify(f"Recording format set to {fmt.upper()}", icon_kind="video")

    def _on_rec_fps_changed(self, fps: int) -> None:
        self._rec_fps = int(fps)
        self._notify(f"Recording frame rate set to {fps} fps", icon_kind="recent")

    def _on_rec_scale_changed(self, scale: int) -> None:
        self._rec_scale = int(scale)
        self._notify(f"Capture scale set to {scale}×", icon_kind="grid")

    def _reload_library(self) -> None:
        self._all_roms = discover_recent_roms(5) if self._library_section == "recent" else discover_all_roms()
        if self._library_section == "home":
            self.btn_home.set_badge(str(len(self._all_roms)) if self._all_roms else "")
        self._apply_search_filter()

    def _apply_search_filter(self) -> None:
        if self._search_query:
            q = self._search_query
            self._filtered_roms = [
                r for r in self._all_roms
                if q in r.title.lower() or q in r.publisher.lower() or q in r.file_type.lower()
            ]
        else:
            self._filtered_roms = list(self._all_roms)
        self._rebuild_cards_and_list()

    def _rebuild_cards_and_list(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._list_rows.clear()

        for rom in self._filtered_roms:
            card = GameCard(rom, cover_size=self._cover_size, theme=self._theme)
            card.clicked.connect(self._launch_rom)
            self._cards.append(card)

            row = GameListRow(rom, theme=self._theme)
            row.play_clicked.connect(self._launch_rom)
            self._list_rows.append(row)
            self.list_layout.addWidget(row)

        count = len(self._filtered_roms)
        self.lib_count_lbl.setText(f"{count} {'game' if count == 1 else 'games'}")
        self._relayout_grid()
        self._update_library_empty_or_view()

    def _update_library_empty_or_view(self) -> None:
        if not self._filtered_roms:
            if self._search_query:
                self.empty_title_lbl.setText("No Matching Games")
                self.empty_sub_lbl.setText(f'Nothing matched "{self._search_query}".')
            elif self._library_section == "recent":
                self.empty_title_lbl.setText("No Recently Played Games")
                self.empty_sub_lbl.setText("Launch a game from All Games to see it here.")
            else:
                self.empty_title_lbl.setText("No ROMs Found")
                self.empty_sub_lbl.setText(f"Place .3ds or .3dsx files in {ROMS_DIR}")
            self.view_stack.setCurrentIndex(2)
        else:
            self.view_stack.setCurrentIndex(0 if self._view_mode == "grid" else 1)

    def _relayout_grid(self) -> None:
        avail_w = max(300, self.grid_scroll.viewport().width() - 24)
        card_w = self._cover_size + 30
        cols = max(1, avail_w // card_w)
        for idx, card in enumerate(self._cards):
            self.grid_layout.addWidget(card, idx // cols, idx % cols)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._cards:
            self._relayout_grid()
        if hasattr(self, "toast"):
            self.toast.reposition()

    # --- Browser-style Game Tabs ---

    def _sync_tab_bar(self) -> None:
        items = [(t.tab_id, t.title) for t in self._tabs]
        self.tab_bar.set_tabs(items, self._active_tab_id)
        has_tabs = len(self._tabs) > 0
        self.tab_bar.setVisible(has_tabs)
        self.header_title.setVisible(not has_tabs)

    def _get_tab(self, tab_id: Optional[int]) -> Optional[GameTabSession]:
        for t in self._tabs:
            if t.tab_id == tab_id:
                return t
        return None

    def _on_new_tab_requested(self) -> None:
        tid = self._next_tab_id
        self._next_tab_id += 1
        self._tabs.append(GameTabSession(tab_id=tid, rom=None, title="New Tab"))
        self._active_tab_id = tid
        self._sync_tab_bar()
        self._switch_sidebar("home")

    def _on_tab_selected(self, tab_id: int) -> None:
        tab = self._get_tab(tab_id)
        if tab is None:
            return
        self._active_tab_id = tab_id
        self._sync_tab_bar()

        if tab.rom is None:
            self._switch_sidebar("home")
            return

        self._enter_gameplay_chrome()
        current_rom = self.adapter.current_rom
        if not self.adapter.is_running() or current_rom != tab.rom.path:
            self._start_adapter_for_rom(tab.rom)

    def _close_tab(self, tab_id: int) -> None:
        idx = next((i for i, t in enumerate(self._tabs) if t.tab_id == tab_id), None)
        if idx is None:
            return
        closing = self._tabs.pop(idx)
        was_active = tab_id == self._active_tab_id

        if not self._tabs:
            self._active_tab_id = None
            self._stop_emulation_only()
            self._sync_tab_bar()
            self._switch_sidebar(self._library_section)
            return

        if was_active:
            next_idx = min(idx, len(self._tabs) - 1)
            next_tab = self._tabs[next_idx]
            if closing.rom is not None and (next_tab.rom is None or next_tab.rom.path != closing.rom.path):
                self._stop_emulation_only()
            self._on_tab_selected(next_tab.tab_id)
        else:
            self._sync_tab_bar()

    def _close_active_or_stop_game(self) -> None:
        if self._active_tab_id is not None:
            self._close_tab(self._active_tab_id)
        else:
            self._stop_emulation_only()
            self._switch_sidebar(self._library_section)

    # --- Emulation Launch & Embedded Playback ---

    def _enter_gameplay_chrome(self) -> None:
        self._in_gameplay = True
        self.header_title.setVisible(False)
        self.tab_bar.setVisible(True)
        self.search_field.setVisible(False)
        self.view_seg.setVisible(False)
        self.slider_wrap.setVisible(False)
        self.header_sep.setVisible(False)
        self.btn_fullscreen.setVisible(True)
        self.btn_quick_save.setVisible(True)
        self.btn_quick_load.setVisible(True)
        self.btn_record.setVisible(True)
        self.btn_stop_record.setVisible(self._is_recording)
        self.btn_restart.setVisible(True)
        self.btn_close_game.setVisible(True)
        self.stack.setCurrentIndex(1)
        self._apply_header_theme()

    def _launch_rom(self, rom: RomInfo) -> None:
        active_tab = self._get_tab(self._active_tab_id)
        if active_tab is not None and active_tab.rom is None:
            active_tab.rom = rom
            active_tab.title = rom.title
        else:
            tid = self._next_tab_id
            self._next_tab_id += 1
            self._tabs.append(GameTabSession(tab_id=tid, rom=rom, title=rom.title))
            self._active_tab_id = tid

        self._sync_tab_bar()
        self._enter_gameplay_chrome()
        self._start_adapter_for_rom(rom)

    def _start_adapter_for_rom(self, rom: RomInfo) -> None:
        self.gameplay_page.start_streaming()
        self._notify(f"Launching {rom.title}...", icon_kind="play_circle", color="#30D158")

        def _worker():
            try:
                ok = self.adapter.launch(str(rom.path))
                self.game_launched.emit(ok, rom.title)
            except Exception as e:
                self.game_launched.emit(False, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_game_launched(self, ok: bool, info: str) -> None:
        if ok:
            self.gameplay_page.setFocus()
            self._notify(f"Playing {info}", icon_kind="home", color="#30D158")
        else:
            self.gameplay_page.stop_streaming()
            self._notify(f"Launch failed: {info}", icon_kind="stop_save", color="#FF453A")

    def _stop_emulation_only(self) -> None:
        if self._is_recording:
            self._stop_and_save_recording()
        self.gameplay_page.stop_streaming()
        if self.adapter.is_running():
            threading.Thread(target=self.adapter.stop, daemon=True).start()
        self._notify("Emulation stopped", icon_kind="stop_save")

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            is_fs = self.isFullScreen()
            self.header.setVisible(not is_fs)
            self.sidebar.setVisible((not is_fs) and self._sidebar_visible)
            set_glass_enabled(self, not is_fs)
            self.btn_fullscreen.set_icon_kind("exit_fullscreen" if is_fs else "fullscreen")
            self.gameplay_page.set_fullscreen_mode(is_fs)
        super().changeEvent(event)

    # --- Toolbar Actions ---

    def _send_mac_shortcut(self, keycode: int, with_cmd: bool = False) -> None:
        if not self.adapter.is_running():
            return
        cmd_kc = 55  # kVK_Command
        if with_cmd:
            ev_cmd = _app_services.CGEventCreateKeyboardEvent(None, cmd_kc, True)
            if ev_cmd:
                _app_services.CGEventPostToPid(self.adapter.input_mgr.target_pid or 0, ev_cmd)
                _app_services.CFRelease(ev_cmd)

        ev_down = _app_services.CGEventCreateKeyboardEvent(None, keycode, True)
        ev_up = _app_services.CGEventCreateKeyboardEvent(None, keycode, False)
        pid = self.adapter.input_mgr.target_pid
        for ev in (ev_down, ev_up):
            if ev:
                if pid:
                    _app_services.CGEventPostToPid(pid, ev)
                else:
                    _app_services.CGEventPost(kCGHIDEventTap, ev)
                _app_services.CFRelease(ev)
                time.sleep(0.03)

        if with_cmd:
            ev_cmd_up = _app_services.CGEventCreateKeyboardEvent(None, cmd_kc, False)
            if ev_cmd_up:
                _app_services.CGEventPostToPid(self.adapter.input_mgr.target_pid or 0, ev_cmd_up)
                _app_services.CFRelease(ev_cmd_up)

    def _quick_save(self) -> None:
        if not self.adapter.is_running():
            self._notify("Start a game first to Quick Save", icon_kind="quick_save", color="#64D2FF")
            return
        self._send_mac_shortcut(8, with_cmd=True)  # 'C' = 8 -> Cmd+C
        self._notify("Quick Save triggered", icon_kind="quick_save", color="#64D2FF")

    def _quick_load(self) -> None:
        if not self.adapter.is_running():
            self._notify("Start a game first to Quick Load", icon_kind="quick_load", color="#64D2FF")
            return
        self._send_mac_shortcut(9, with_cmd=True)  # 'V' = 9 -> Cmd+V
        self._notify("Quick Load triggered", icon_kind="quick_load", color="#64D2FF")

    def _toggle_record(self) -> None:
        if not self.adapter.is_running():
            self._notify("Start a game first to record gameplay", icon_kind="record", color="#FF453A")
            return

        if not self._is_recording:
            try:
                res = self.adapter.start_recording(
                    target="both",
                    fps=self._rec_fps,
                    format=self._rec_format,
                    scale=self._rec_scale,
                )
                self._is_recording = True
                self.btn_record.set_icon_kind("pause")
                self.btn_record.set_state_colors(danger=True)
                self.btn_record.setToolTip("Pause / Recording Active")
                self.btn_stop_record.setVisible(True)
                self.rec_badge.setVisible(True)
                self._notify(f"Recording started: {res['file_name']}", icon_kind="record", color="#FF453A")
            except Exception as e:
                self._notify(f"Record error: {e}", icon_kind="stop_save", color="#FF453A")
        else:
            self._send_mac_shortcut(118, with_cmd=False)
            self._notify("Toggled emulation pause", icon_kind="pause")

    def _stop_and_save_recording(self) -> None:
        if not self._is_recording:
            return
        try:
            res = self.adapter.stop_recording()
            self._notify(
                f"Saved: {res['file_name']} ({res['duration_seconds']}s · {res['file_size_human']})",
                icon_kind="video",
                color="#30D158",
            )
        except Exception as e:
            self._notify(f"Stop recording error: {e}", icon_kind="stop_save", color="#FF453A")
        finally:
            self._is_recording = False
            self.btn_record.set_icon_kind("record")
            self.btn_record.set_state_colors(danger=False)
            self.btn_record.setToolTip("Record Gameplay / Pause")
            self.btn_stop_record.setVisible(False)
            self.rec_badge.setVisible(False)

    def _toggle_mute(self) -> None:
        self._is_muted = not self._is_muted
        self.btn_mute.set_icon_kind("sound_off" if self._is_muted else "sound_on")
        self.btn_mute.set_state_colors(accent=self._is_muted)
        if self.adapter.is_running():
            self._send_mac_shortcut(46, with_cmd=True)  # 'M' = 46 -> Cmd+M
        self._notify("Audio muted" if self._is_muted else "Audio unmuted", icon_kind="sound_off" if self._is_muted else "sound_on")

    def _restart_emulation(self) -> None:
        if not self.adapter.is_running():
            self._notify("No active game to restart", icon_kind="restart")
            return
        self._send_mac_shortcut(97, with_cmd=False)  # F6 = 97
        self._notify("Emulation restarted", icon_kind="restart", color="#64D2FF")

    def closeEvent(self, event) -> None:
        if self._is_recording:
            self._stop_and_save_recording()
        self.gameplay_page.stop_streaming()
        if self.adapter.is_running():
            self.adapter.stop()
        super().closeEvent(event)
