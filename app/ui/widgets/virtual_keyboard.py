from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import Qt, QObject, QEvent, pyqtSignal, QProcess
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout,
    QSizePolicy, QFrame,
)


@dataclass
class KeyboardTarget:
    widget: QWidget
    label: str


class VirtualKeyboardWidget(QWidget):
    """Compact 1024x600-safe keyboard overlay.

    v0.1.3 reduces height and key count to prevent overlap on a 7-inch
    1024x600 touch display. It keeps preview/context visible and avoids
    internal scrolling entirely.
    """

    hide_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("VirtualKeyboard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._target: Optional[KeyboardTarget] = None
        self._shift = False
        self._height_expanded = 246
        self._height_compact = 208
        self._expanded = True
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(5)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.lbl_ctx = QLabel("Input")
        self.lbl_ctx.setObjectName("KeyboardContext")
        self.lbl_ctx.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_preview = QLabel(" ")
        self.lbl_preview.setObjectName("KeyboardPreview")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_preview.setWordWrap(False)
        self.btn_shift = QPushButton("Shift")
        self.btn_shift.setObjectName("KeyboardUtilityKey")
        self.btn_shift.setCheckable(True)
        self.btn_expand = QPushButton("Small")
        self.btn_expand.setObjectName("KeyboardUtilityKey")
        self.btn_hide = QPushButton("Hide")
        self.btn_hide.setObjectName("KeyboardHideKey")
        for b in (self.btn_shift, self.btn_expand, self.btn_hide):
            b.setFixedHeight(32)
        self.lbl_ctx.setFixedHeight(32)
        self.lbl_preview.setFixedHeight(32)
        header.addWidget(self.lbl_ctx, 2)
        header.addWidget(self.lbl_preview, 5)
        header.addWidget(self.btn_shift)
        header.addWidget(self.btn_expand)
        header.addWidget(self.btn_hide)
        root.addLayout(header)

        line = QFrame()
        line.setObjectName("KeyboardDivider")
        line.setFixedHeight(2)
        root.addWidget(line)

        self.keys_widget = QWidget()
        self.keys_widget.setObjectName("KeyboardKeyGrid")
        self.grid = QGridLayout(self.keys_widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(4)
        self.grid.setVerticalSpacing(4)
        for c in range(10):
            self.grid.setColumnStretch(c, 1)
        root.addWidget(self.keys_widget, 1)

        self._buttons: dict[str, QPushButton] = {}
        self._build_keys()

        self.btn_shift.toggled.connect(self._set_shift)
        self.btn_expand.clicked.connect(self.toggle_size)
        self.btn_hide.clicked.connect(self.request_hide)
        self.set_expanded(True)

    def sizeHint(self):  # type: ignore[override]
        s = super().sizeHint()
        s.setHeight(self._height_expanded if self._expanded else self._height_compact)
        return s

    def toggle_size(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        h = self._height_expanded if self._expanded else self._height_compact
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        self.btn_expand.setText("Small" if self._expanded else "Full")
        key_h = 34 if self._expanded else 28
        for btn in self._buttons.values():
            btn.setFixedHeight(key_h)

    def _set_shift(self, on: bool) -> None:
        self._shift = bool(on)
        self._refresh_key_caps()

    def _mk_key(self, text: str, *, accent: bool = False, danger: bool = False, hide: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedHeight(34)
        if hide:
            obj = "KeyboardHideKey"
        elif accent:
            obj = "KeyboardAccentKey"
        elif danger:
            obj = "KeyboardDangerKey"
        else:
            obj = "KeyboardKey"
        btn.setObjectName(obj)
        return btn

    def _add_key(self, btn: QPushButton, row: int, col: int, colspan: int = 1, key: str | None = None) -> None:
        self.grid.addWidget(btn, row, col, 1, colspan)
        if key:
            self._buttons[key] = btn

    def _build_keys(self) -> None:
        rows = [
            list("1234567890"),
            list("qwertyuiop"),
            list("asdfghjkl") + ["bksp"],
            list("zxcvbnm") + ["clear", "space", "done"],
        ]
        for r, row in enumerate(rows):
            self.grid.setRowStretch(r, 1)
            c = 0
            for key in row:
                if key == "bksp":
                    btn = self._mk_key("⌫", danger=True)
                    btn.clicked.connect(self._backspace)
                    self._add_key(btn, r, c, 1, "bksp")
                    c += 1
                elif key == "clear":
                    btn = self._mk_key("Clr", danger=True)
                    btn.clicked.connect(self._clear_text)
                    self._add_key(btn, r, c, 1, "clear")
                    c += 1
                elif key == "space":
                    btn = self._mk_key("Space")
                    btn.clicked.connect(lambda _=False: self._insert(" "))
                    self._add_key(btn, r, c, 1, "space")
                    c += 1
                elif key == "done":
                    btn = self._mk_key("Done", accent=True)
                    btn.clicked.connect(self._enter)
                    self._add_key(btn, r, c, 1, "done")
                    c += 1
                else:
                    btn = self._mk_key(key)
                    btn.clicked.connect(lambda _=False, ch=key: self._insert_char(ch))
                    self._add_key(btn, r, c, 1, key)
                    c += 1

    def _refresh_key_caps(self) -> None:
        for k, btn in self._buttons.items():
            if len(k) == 1 and k.isalpha():
                btn.setText(k.upper() if self._shift else k.lower())

    def set_target(self, target: KeyboardTarget) -> None:
        self._target = target
        self.lbl_ctx.setText(target.label[:18])
        self._update_preview()

    def _target_text(self) -> str:
        if self._target is None:
            return ""
        w = self._target.widget
        if hasattr(w, "lineEdit"):
            try:
                return str(w.lineEdit().text())
            except Exception:
                pass
        if hasattr(w, "text"):
            try:
                return str(w.text())
            except Exception:
                pass
        if hasattr(w, "toPlainText"):
            return str(w.toPlainText())
        return ""

    def _update_preview(self) -> None:
        text = self._target_text()
        if len(text) > 64:
            text = "…" + text[-63:]
        self.lbl_preview.setText(text if text else " ")

    def _insert_char(self, ch: str) -> None:
        if self._shift and ch.isalpha():
            ch = ch.upper()
        else:
            ch = ch.lower() if ch.isalpha() else ch
        self._insert(ch)

    def _insert(self, s: str) -> None:
        if self._target is None:
            return
        w = self._target.widget
        if hasattr(w, "lineEdit"):
            try:
                w.lineEdit().insert(s)
            except Exception:
                pass
        elif hasattr(w, "insert"):
            w.insert(s)
        elif hasattr(w, "textCursor"):
            w.insertPlainText(s)
        self._update_preview()

    def _backspace(self) -> None:
        if self._target is None:
            return
        w = self._target.widget
        if hasattr(w, "lineEdit"):
            try:
                w.lineEdit().backspace()
            except Exception:
                pass
        elif hasattr(w, "backspace"):
            w.backspace()
        elif hasattr(w, "textCursor"):
            cur: QTextCursor = w.textCursor()
            cur.deletePreviousChar()
            w.setTextCursor(cur)
        self._update_preview()

    def _clear_text(self) -> None:
        if self._target is None:
            return
        w = self._target.widget
        if hasattr(w, "lineEdit"):
            try:
                w.lineEdit().clear()
            except Exception:
                pass
        elif hasattr(w, "clear"):
            try:
                w.clear()
            except Exception:
                pass
        self._update_preview()

    def _enter(self) -> None:
        self.request_hide()

    def request_hide(self) -> None:
        self.hide_requested.emit()


class KeyboardController(QObject):
    """Application-wide focus watcher that routes input to the internal keyboard."""

    visibility_changed = pyqtSignal(bool)

    def __init__(self, keyboard: VirtualKeyboardWidget, external_kb_cmd: Optional[list[str]] = None):
        super().__init__()
        self.kb = keyboard
        self._manual_hidden = True
        self._external_kb_cmd = external_kb_cmd
        self._external_proc: Optional[QProcess] = None
        if self._external_kb_cmd:
            self._external_proc = QProcess(self)
            self._external_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.kb.hide_requested.connect(self.hide)

    def install(self, app) -> None:
        app.installEventFilter(self)

    def _start_external_keyboard(self) -> None:
        if not self._external_proc or not self._external_kb_cmd:
            return
        if self._external_proc.state() != QProcess.ProcessState.NotRunning:
            return
        self._external_proc.start(self._external_kb_cmd[0], self._external_kb_cmd[1:])

    def _stop_external_keyboard(self) -> None:
        if not self._external_proc:
            return
        if self._external_proc.state() == QProcess.ProcessState.NotRunning:
            return
        self._external_proc.terminate()
        if not self._external_proc.waitForFinished(500):
            self._external_proc.kill()
            self._external_proc.waitForFinished(500)

    def toggle(self):
        if self.kb.isVisible():
            self.hide_keyboard(manual=True)
        else:
            self.show_keyboard(auto=False)

    def show_keyboard(self, auto: bool = False):
        if self._external_kb_cmd:
            self._start_external_keyboard()
            self._manual_hidden = False
            self.visibility_changed.emit(True)
            return
        self._manual_hidden = False
        self.visibility_changed.emit(True)

    def hide_keyboard(self, manual: bool = True):
        if self._external_kb_cmd:
            self._stop_external_keyboard()
            self._manual_hidden = bool(manual)
            self.visibility_changed.emit(False)
            return
        self._manual_hidden = bool(manual)
        self.visibility_changed.emit(False)

    def show(self):
        self.show_keyboard(auto=False)

    def hide(self):
        self.hide_keyboard(manual=True)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.FocusIn:
            if self._is_text_input(obj):
                label = self._label_for(obj)
                self.kb.set_target(KeyboardTarget(widget=obj, label=label))
                self._manual_hidden = False
                if self._external_kb_cmd:
                    self._start_external_keyboard()
                    self.visibility_changed.emit(True)
                else:
                    self.visibility_changed.emit(True)
        return super().eventFilter(obj, ev)

    @staticmethod
    def _is_text_input(w: object) -> bool:
        # Avoid catching generic widgets that only expose text(); require editable APIs.
        return hasattr(w, "lineEdit") or hasattr(w, "insert") or hasattr(w, "textCursor") or hasattr(w, "backspace")

    @staticmethod
    def _label_for(w: object) -> str:
        try:
            if hasattr(w, "property"):
                v = w.property("kb_label")
                if isinstance(v, str) and v.strip():
                    return v.strip()
            if hasattr(w, "accessibleName"):
                v = str(w.accessibleName() or "").strip()
                if v:
                    return v
            if hasattr(w, "placeholderText"):
                v = str(w.placeholderText() or "").strip()
                if v:
                    return v
            if hasattr(w, "objectName"):
                v = str(w.objectName() or "").strip()
                if v:
                    return v
        except Exception:
            pass
        return "Input"
