from __future__ import annotations

import os
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QFrame
)

from app.ui.pages.menu_page import MenuPage
from app.ui.pages.count_page import CountPage
from app.ui.pages.inventory_page import InventoryPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.widgets.virtual_keyboard import VirtualKeyboardWidget
from app.ui.widgets.app_overlay import AppOverlay


APP_WINDOW_WIDTH = 1024
APP_WINDOW_HEIGHT = 600
QT_WIDGET_MAX_SIZE = 16777215


class MainWindow(QMainWindow):
    sig_show_page = pyqtSignal(str)

    def __init__(self, qss_path: str):
        super().__init__()
        self.setWindowTitle("Pill Counter")
        self.setFixedSize(APP_WINDOW_WIDTH, APP_WINDOW_HEIGHT)

        cw = QWidget()
        cw.setObjectName("RootWidget")
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Lightweight header for non-menu screens only; no global camera/model/tunnel statuses here.
        self.header = QFrame()
        self.header.setObjectName("ScreenHeader")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(10)
        self.btn_drawer = QPushButton("☰")
        self.btn_drawer.setObjectName("MenuIconButton")
        self.lbl_screen_title = QLabel("Menu")
        self.lbl_screen_title.setObjectName("ScreenTitle")
        hl.addWidget(self.btn_drawer)
        hl.addWidget(self.lbl_screen_title)
        hl.addStretch(1)
        # Header is kept for compatibility but hidden in v0.1.3 to maximize 1024x600 workspace.
        self.header.hide()

        self.stack = QStackedWidget()
        self.page_menu = MenuPage()
        self.page_count = CountPage()
        self.page_inventory = InventoryPage()
        self.page_settings = SettingsPage()
        # Diagnostics is currently mapped to settings/log workflow; kept as a navigation target.
        self.stack.addWidget(self.page_menu)
        self.stack.addWidget(self.page_count)
        self.stack.addWidget(self.page_inventory)
        self.stack.addWidget(self.page_settings)
        root.addWidget(self.stack, 1)

        # Floating translucent menu button. It overlays the current page and does not consume layout height.
        self.btn_floating_menu = QPushButton("☰", cw)
        self.btn_floating_menu.setObjectName("FloatingMenuButton")
        self.btn_floating_menu.setFixedSize(44, 38)
        self.btn_floating_menu.clicked.connect(self.toggle_drawer)
        self.btn_floating_menu.hide()

        # Backwards-compatible status aliases, but visually they live only on MenuPage.
        self.lbl_cam = self.page_menu.lbl_cam
        self.lbl_model = self.page_menu.lbl_model
        self.lbl_flask = self.page_menu.lbl_tunnel
        self.lbl_time = self.page_menu.lbl_time

        # Overlay quick menu: absolute-positioned drawer, animated, does not alter page layout.
        self.drawer = QFrame(cw)
        self.drawer.setObjectName("SideDrawer")
        self.drawer.hide()
        dl = QVBoxLayout(self.drawer)
        dl.setContentsMargins(14, 14, 14, 14)
        dl.setSpacing(8)
        self.btn_drawer_home = QPushButton("Menu")
        self.btn_drawer_count = QPushButton("Count")
        self.btn_drawer_inventory = QPushButton("Inventory")
        self.btn_drawer_reports = QPushButton("Reports / Logs")
        self.btn_drawer_settings = QPushButton("Settings")
        self.btn_drawer_diag = QPushButton("Diagnostics")
        self.btn_kb_toggle = QPushButton("Keyboard")
        self.btn_kb_toggle.setCheckable(True)
        for b in (
            self.btn_drawer_home, self.btn_drawer_count, self.btn_drawer_inventory,
            self.btn_drawer_reports, self.btn_drawer_settings, self.btn_drawer_diag,
            self.btn_kb_toggle,
        ):
            b.setMinimumHeight(44)
            dl.addWidget(b)
        dl.addStretch(1)

        self._drawer_anim: QPropertyAnimation | None = None
        self._keyboard_anim: QPropertyAnimation | None = None
        self.btn_drawer.clicked.connect(self.toggle_drawer)
        self.btn_drawer_home.clicked.connect(lambda: self._drawer_nav("menu"))
        self.btn_drawer_count.clicked.connect(lambda: self._drawer_nav("count"))
        self.btn_drawer_inventory.clicked.connect(lambda: self._drawer_nav("inventory"))
        self.btn_drawer_reports.clicked.connect(lambda: self._drawer_nav("inventory"))
        self.btn_drawer_settings.clicked.connect(lambda: self._drawer_nav("settings"))
        self.btn_drawer_diag.clicked.connect(lambda: self._drawer_nav("settings"))

        # In-app overlay dialogs and keyboard are both children of cw, not native dialogs.
        self.overlay = AppOverlay(cw)
        self.keyboard = VirtualKeyboardWidget(cw)
        self.kb_widget = self.keyboard
        self.keyboard.setVisible(False)
        self.keyboard.raise_()

        self.page_menu.sig_open.connect(lambda name: self.sig_show_page.emit(name))

        if qss_path and os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

        self._t = QTimer(self)
        self._t.setInterval(500)
        self._t.timeout.connect(self._tick_time)
        self._t.start()
        self.show_page("menu")

    def show_app_windowed(self) -> None:
        self.showNormal()
        self.setFixedSize(APP_WINDOW_WIDTH, APP_WINDOW_HEIGHT)
        self.resize(APP_WINDOW_WIDTH, APP_WINDOW_HEIGHT)
        self.show()
        self._place_floating_menu()
        self._place_keyboard_overlay()
        self._place_drawer(0 if self.drawer.isVisible() else -224)

    def show_app_full_screen(self) -> None:
        self.setMinimumSize(APP_WINDOW_WIDTH, APP_WINDOW_HEIGHT)
        self.setMaximumSize(QT_WIDGET_MAX_SIZE, QT_WIDGET_MAX_SIZE)
        self.showFullScreen()
        self._place_floating_menu()
        self._place_keyboard_overlay()
        self._place_drawer(0 if self.drawer.isVisible() else -224)

    def _drawer_nav(self, name: str) -> None:
        self.close_drawer()
        self.sig_show_page.emit(name)

    def show_page(self, name: str) -> None:
        if name == "count":
            page = self.page_count
            title = "Count"
        elif name in ("inventory", "reports", "logs"):
            page = self.page_inventory
            title = "Inventory / Reports / Logs"
            if name == "reports":
                self.page_inventory.tabs.setCurrentIndex(1)
            elif name == "logs":
                self.page_inventory.tabs.setCurrentIndex(2)
        elif name in ("settings", "diagnostics"):
            page = self.page_settings
            title = "Settings / Diagnostics"
        else:
            page = self.page_menu
            title = "Menu"
        self.stack.setCurrentWidget(page)
        self.lbl_screen_title.setText(title)
        self.header.hide()
        self.btn_floating_menu.setVisible(page is not self.page_menu)
        self._place_floating_menu()
        if page is not self.page_menu:
            self.btn_floating_menu.raise_()

    def _tick_time(self):
        from datetime import datetime
        self.page_menu.lbl_time.setText(datetime.now().strftime("%H:%M:%S"))

    def _keyboard_height(self) -> int:
        return int(self.keyboard.maximumHeight() if self.keyboard.maximumHeight() < 16000 else self.keyboard.sizeHint().height())

    def _keyboard_rects(self) -> tuple[QRect, QRect] | None:
        cw = self.centralWidget()
        if cw is None:
            return None
        m = 8
        h = self._keyboard_height()
        w = max(100, cw.width() - 2 * m)
        shown = QRect(m, max(m, cw.height() - h - m), w, h)
        hidden = QRect(m, cw.height() + m, w, h)
        return hidden, shown

    def _place_keyboard_overlay(self) -> None:
        if not self.keyboard.isVisible():
            return
        rects = self._keyboard_rects()
        if rects is None:
            return
        _, shown = rects
        self.keyboard.setGeometry(shown)
        self.keyboard.raise_()

    def _animate_keyboard_visible(self, visible: bool, animate: bool = True) -> None:
        rects = self._keyboard_rects()
        if rects is None:
            return
        hidden, shown = rects
        if self._keyboard_anim is not None:
            self._keyboard_anim.stop()
        if visible:
            already_shown = self.keyboard.isVisible() and abs(self.keyboard.geometry().y() - shown.y()) <= 2
            if already_shown:
                self.keyboard.setGeometry(shown)
                self.keyboard.raise_()
                return
            start = self.keyboard.geometry() if self.keyboard.isVisible() else hidden
            self.keyboard.setGeometry(start)
            self.keyboard.show()
            self.keyboard.raise_()
            if not animate:
                self.keyboard.setGeometry(shown)
                return
            self._keyboard_anim = QPropertyAnimation(self.keyboard, b"geometry", self)
            self._keyboard_anim.setDuration(190)
            self._keyboard_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._keyboard_anim.setStartValue(start)
            self._keyboard_anim.setEndValue(shown)
            self._keyboard_anim.start()
            return

        if not self.keyboard.isVisible():
            self.keyboard.hide()
            return
        if not animate:
            self.keyboard.setGeometry(hidden)
            self.keyboard.hide()
            return
        self._keyboard_anim = QPropertyAnimation(self.keyboard, b"geometry", self)
        self._keyboard_anim.setDuration(170)
        self._keyboard_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._keyboard_anim.setStartValue(self.keyboard.geometry())
        self._keyboard_anim.setEndValue(hidden)
        self._keyboard_anim.finished.connect(self.keyboard.hide)
        self._keyboard_anim.start()

    def _place_drawer(self, visible_x: int | None = None):
        cw = self.centralWidget()
        if cw is None:
            return
        w = 224
        x = visible_x if visible_x is not None else (0 if self.drawer.isVisible() else -w)
        self.drawer.setGeometry(x, 0, w, cw.height())
        self.drawer.raise_()

    def _place_floating_menu(self) -> None:
        cw = self.centralWidget()
        if cw is None:
            return
        self.btn_floating_menu.setGeometry(max(0, cw.width() - 52), 10, 44, 38)
        self.btn_floating_menu.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.overlay.resize_to_parent()
        self._place_floating_menu()
        self._place_keyboard_overlay()
        self._place_drawer(0 if self.drawer.isVisible() else -224)

    def toggle_drawer(self):
        if self.drawer.isVisible() and self.drawer.x() >= 0:
            self.close_drawer()
        else:
            self.open_drawer()

    def open_drawer(self):
        cw = self.centralWidget()
        if cw is None:
            return
        w = 224
        self.drawer.setGeometry(-w, 0, w, cw.height())
        self.drawer.show()
        self.drawer.raise_()
        self._drawer_anim = QPropertyAnimation(self.drawer, b"geometry", self)
        self._drawer_anim.setDuration(190)
        self._drawer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._drawer_anim.setStartValue(QRect(-w, 0, w, cw.height()))
        self._drawer_anim.setEndValue(QRect(0, 0, w, cw.height()))
        self._drawer_anim.start()

    def close_drawer(self):
        if not self.drawer.isVisible():
            return
        cw = self.centralWidget()
        if cw is None:
            self.drawer.hide(); return
        w = 224
        self._drawer_anim = QPropertyAnimation(self.drawer, b"geometry", self)
        self._drawer_anim.setDuration(170)
        self._drawer_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._drawer_anim.setStartValue(self.drawer.geometry())
        self._drawer_anim.setEndValue(QRect(-w, 0, w, cw.height()))
        self._drawer_anim.finished.connect(self.drawer.hide)
        self._drawer_anim.start()

    def _on_kb_toggle(self, on: bool) -> None:
        self.set_keyboard_visible(bool(on))

    def set_keyboard_visible(self, visible: bool) -> None:
        self._animate_keyboard_visible(bool(visible), animate=True)
