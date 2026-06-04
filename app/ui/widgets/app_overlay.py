from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGridLayout, QLineEdit, QSpinBox,
)


class AppOverlay(QWidget):
    """In-app modal overlay; avoids native QDialog so the internal keyboard can type into fields."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("AppOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()
        self._card = QFrame(self)
        self._card.setObjectName("OverlayCard")
        self._root = QVBoxLayout(self._card)
        self._root.setContentsMargins(24, 20, 24, 20)
        self._root.setSpacing(14)

    def resize_to_parent(self):
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        card_w = min(620, max(420, self.width() - 160))
        card_h = min(430, max(240, self.height() - 120))
        self._card.setGeometry((self.width() - card_w) // 2, (self.height() - card_h) // 2, card_w, card_h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.resize_to_parent()

    def _clear(self):
        while self._root.count():
            item = self._root.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def show_confirm(self, title: str, message: str, on_yes: Callable[[], None], yes_text: str = "OK", no_text: str = "Cancel"):
        self._clear()
        lbl_title = QLabel(title)
        lbl_title.setObjectName("OverlayTitle")
        lbl_msg = QLabel(message)
        lbl_msg.setObjectName("OverlayMessage")
        lbl_msg.setWordWrap(True)
        self._root.addWidget(lbl_title)
        self._root.addWidget(lbl_msg, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_no = QPushButton(no_text)
        btn_yes = QPushButton(yes_text)
        btn_yes.setObjectName("DangerButton" if yes_text.lower().startswith(("delete", "clear")) else "PrimaryButton")
        btns.addWidget(btn_no)
        btns.addWidget(btn_yes)
        self._root.addLayout(btns)
        btn_no.clicked.connect(self.hide)
        btn_yes.clicked.connect(lambda: (self.hide(), on_yes()))
        self.resize_to_parent()
        self.show()
        self.raise_()

    def show_drug_form(self, title: str, name: str, code: str, reorder: int, on_save: Callable[[str, str, int], None]):
        self._clear()
        lbl_title = QLabel(title)
        lbl_title.setObjectName("OverlayTitle")
        self._root.addWidget(lbl_title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        ed_name = QLineEdit(); ed_name.setProperty("kb_label", "Drug name"); ed_name.setText(name); ed_name.setPlaceholderText("Drug name")
        ed_code = QLineEdit(); ed_code.setProperty("kb_label", "Drug code"); ed_code.setText(code); ed_code.setPlaceholderText("Drug code")
        sp_reorder = QSpinBox(); sp_reorder.setProperty("kb_label", "Reorder level"); sp_reorder.setRange(0, 100000); sp_reorder.setValue(int(reorder))
        grid.addWidget(QLabel("Name"), 0, 0); grid.addWidget(ed_name, 0, 1)
        grid.addWidget(QLabel("Code"), 1, 0); grid.addWidget(ed_code, 1, 1)
        grid.addWidget(QLabel("Reorder"), 2, 0); grid.addWidget(sp_reorder, 2, 1)
        self._root.addLayout(grid)
        self._root.addStretch(1)
        btns = QHBoxLayout(); btns.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_save = QPushButton("Save")
        btn_save.setObjectName("PrimaryButton")
        btns.addWidget(btn_cancel); btns.addWidget(btn_save)
        self._root.addLayout(btns)
        btn_cancel.clicked.connect(self.hide)
        btn_save.clicked.connect(lambda: (self.hide(), on_save(ed_name.text().strip(), ed_code.text().strip(), int(sp_reorder.value()))))
        self.resize_to_parent()
        self.show()
        self.raise_()
        QTimer.singleShot(0, lambda: (ed_name.setFocus(Qt.FocusReason.MouseFocusReason), ed_name.selectAll()))
