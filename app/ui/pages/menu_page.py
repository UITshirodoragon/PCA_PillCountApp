from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout

from app.core.constants import APP_VERSION


class MenuPage(QWidget):
    sig_open = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(20)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        self.lbl_title = QLabel("Pill Counter")
        self.lbl_title.setObjectName("MenuTitle")
        self.lbl_version = QLabel(APP_VERSION)
        self.lbl_version.setObjectName("VersionTiny")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_version)
        top.addLayout(title_box)
        top.addStretch(1)

        self.lbl_time = QLabel("--:--:--")
        self.lbl_time.setObjectName("MenuTime")
        top.addWidget(self.lbl_time)
        root.addLayout(top)

        status = QHBoxLayout()
        status.setSpacing(12)
        self.lbl_cam = QLabel("Camera: --")
        self.lbl_model = QLabel("Model: --")
        self.lbl_tunnel = QLabel("Tunnel: --")
        for w in (self.lbl_cam, self.lbl_model, self.lbl_tunnel):
            w.setObjectName("StatusBadge")
            status.addWidget(w)
        status.addStretch(1)
        root.addLayout(status)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(20)
        self.buttons: dict[str, QPushButton] = {}
        specs = [
            ("count", "COUNT", "Live camera"),
            ("inventory", "INVENTORY", "Stock"),
            ("reports", "REPORTS", "Audit"),
            ("logs", "LOGS", "System"),
            ("settings", "SETTINGS", "Config"),
            ("diagnostics", "DIAGNOSTICS", "Checks"),
        ]
        for idx, (key, title, sub) in enumerate(specs):
            btn = QPushButton(f"{title}\n{sub}")
            btn.setObjectName("MenuButton")
            btn.setMinimumHeight(118)
            btn.clicked.connect(lambda _=False, k=key: self.sig_open.emit(k))
            self.buttons[key] = btn
            grid.addWidget(btn, idx // 3, idx % 3)
        root.addLayout(grid, 1)
