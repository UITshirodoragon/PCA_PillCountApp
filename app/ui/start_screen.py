from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class StartScreen(QWidget):
    start_requested = pyqtSignal()

    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(1024, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        lbl = QLabel(title)
        lbl.setObjectName("TitleLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 48px; font-weight: 700;")  # bigger title

        hint = QLabel("Touch anywhere to start")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 26px;")  # bigger hint

        root.addStretch(1)
        root.addWidget(lbl)
        root.addWidget(hint)
        root.addStretch(2)

    def mousePressEvent(self, ev):
        self.start_requested.emit()
        super().mousePressEvent(ev)
