from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QSize, QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QFrame,
    QCheckBox, QGridLayout, QSizePolicy,
)


class RoundedPreviewLabel(QLabel):
    """Preview label that clips live camera frames to the same radius as its shell."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self._pixmap = QPixmap()
        self._radius = 16
        self._border = 2

    def setPixmap(self, pixmap: QPixmap) -> None:  # type: ignore[override]
        self._pixmap = QPixmap(pixmap)
        self.update()

    def clear(self) -> None:  # type: ignore[override]
        self._pixmap = QPixmap()
        super().clear()
        self.update()

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        outer_path = QPainterPath()
        outer_path.addRoundedRect(outer, self._radius, self._radius)
        painter.fillPath(outer_path, QColor("#0c151c"))

        inner = outer.adjusted(self._border, self._border, -self._border, -self._border)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(inner, max(1, self._radius - self._border), max(1, self._radius - self._border))
        painter.save()
        painter.setClipPath(inner_path)
        if self._pixmap.isNull():
            painter.fillRect(inner, QColor("#0c151c"))
            painter.setPen(QColor("#fffeef"))
            painter.drawText(inner, self.alignment(), self.text() or "No camera")
        else:
            scaled = self._pixmap.scaled(
                inner.size().toSize(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = int(inner.x() + (inner.width() - scaled.width()) / 2)
            y = int(inner.y() + (inner.height() - scaled.height()) / 2)
            painter.drawPixmap(x, y, scaled)
        painter.restore()

        painter.setPen(QPen(QColor("#ccede6"), self._border))
        painter.drawPath(outer_path)


class CountPage(QWidget):
    """1024x600 landscape Count screen.

    v0.1.3 constraints:
    - camera preview is a rounded 4:3 canvas sized for the 1024x600 shell;
    - no persistent header/taskbar inside this page;
    - session data is a compact overlay opened only when needed;
    - buttons/fonts are reduced to avoid overlap on 7-inch 1024x600 screens.
    """

    sig_start = pyqtSignal()
    sig_stop = pyqtSignal()
    sig_freeze = pyqtSignal(bool)
    sig_retake = pyqtSignal()
    sig_smoothing = pyqtSignal(bool)
    sig_txn_changed = pyqtSignal()
    sig_confirm_save = pyqtSignal()
    sig_op_type = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("CountPage")
        self._session_open = False
        self._session_anim: QPropertyAnimation | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        content = QHBoxLayout()
        content.setSpacing(4)
        content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addLayout(content, 1)

        # Left compact count/status strip.
        left_card = QFrame()
        left_card.setObjectName("CountCard")
        left_card.setFixedSize(154, 570)
        left = QVBoxLayout(left_card)
        left.setContentsMargins(8, 8, 8, 8)
        left.setSpacing(6)

        title = QLabel("COUNT")
        title.setObjectName("SmallCaps")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(title)

        self.lbl_count = QLabel("--")
        self.lbl_count.setObjectName("BigCount")
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_count.setFixedHeight(126)
        left.addWidget(self.lbl_count)

        self.lbl_state = QLabel("READY")
        self.lbl_state.setObjectName("StatePill")
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_state.setFixedHeight(36)
        left.addWidget(self.lbl_state)

        self.lbl_total = QLabel("Total 0")
        self.lbl_total.setObjectName("MetricLabel")
        self.lbl_delta = QLabel("Δ --")
        self.lbl_delta.setObjectName("MetricLabel")
        self.lbl_target_summary = QLabel("Target not set")
        self.lbl_target_summary.setObjectName("MetricLabel")
        for w in (self.lbl_total, self.lbl_target_summary, self.lbl_delta):
            w.setFixedHeight(34)
            left.addWidget(w)

        self.preview_plus = QLabel("+ → --")
        self.preview_plus.setObjectName("CalcPreview")
        self.preview_minus = QLabel("− → --")
        self.preview_minus.setObjectName("CalcPreview")
        for w in (self.preview_plus, self.preview_minus):
            w.setFixedHeight(32)
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left.addWidget(w)

        left.addStretch(1)
        content.addWidget(left_card)

        # Camera module: controls wrap the rounded live preview without covering the image.
        camera_card = QFrame()
        camera_card.setObjectName("CameraCard")
        camera_card.setFixedSize(616, 570)
        cam_l = QVBoxLayout(camera_card)
        cam_l.setContentsMargins(8, 8, 8, 8)
        cam_l.setSpacing(6)

        top_bar = QFrame()
        top_bar.setObjectName("CameraTopBar")
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(4, 3, 4, 3)
        top.setSpacing(5)
        self.btn_start = QPushButton("Live")
        self.btn_start.setObjectName("CameraToolButton")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("CameraToolButton")
        self.btn_retake = QPushButton("Retake")
        self.btn_retake.setObjectName("CameraToolButton")
        self.chk_smoothing = QCheckBox("Stable")
        self.chk_smoothing.setChecked(True)
        for b in (self.btn_start, self.btn_stop, self.btn_retake):
            b.setFixedHeight(32)
            top.addWidget(b)
        top.addStretch(1)
        self.chk_smoothing.setFixedHeight(28)
        top.addWidget(self.chk_smoothing)
        cam_l.addWidget(top_bar)

        self.preview = RoundedPreviewLabel("No camera")
        self.preview.setObjectName("PreviewLabel")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(600, 450)
        self.preview.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        cam_l.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignCenter)

        capture_bar = QFrame()
        capture_bar.setObjectName("CaptureBar")
        cap = QHBoxLayout(capture_bar)
        cap.setContentsMargins(4, 2, 4, 2)
        cap.setSpacing(8)
        self.btn_sub_batch = QPushButton("−")
        self.btn_sub_batch.setObjectName("RoundCalcButton")
        self.btn_freeze = QPushButton("CAPTURE")
        self.btn_freeze.setCheckable(True)
        self.btn_freeze.setObjectName("ShutterButton")
        self.btn_add_batch = QPushButton("+")
        self.btn_add_batch.setObjectName("RoundCalcButton")
        self.btn_sub_batch.setFixedSize(78, 50)
        self.btn_add_batch.setFixedSize(78, 50)
        self.btn_freeze.setFixedHeight(50)
        cap.addWidget(self.btn_sub_batch)
        cap.addWidget(self.btn_freeze, 1)
        cap.addWidget(self.btn_add_batch)
        cam_l.addWidget(capture_bar)
        content.addWidget(camera_card)

        # Right workflow rail. Secondary actions stay beside the preview, not mixed into the camera canvas.
        right_card = QFrame()
        right_card.setObjectName("ActionRail")
        right_card.setFixedSize(222, 570)
        right = QVBoxLayout(right_card)
        right.setContentsMargins(9, 9, 9, 9)
        right.setSpacing(7)

        actions_title = QLabel("ACTIONS")
        actions_title.setObjectName("RailTitle")
        actions_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        actions_title.setFixedHeight(26)
        rail_head = QHBoxLayout()
        rail_head.setContentsMargins(0, 0, 0, 0)
        rail_head.setSpacing(6)
        rail_head.addWidget(actions_title, 1)
        rail_head.addSpacing(48)
        right.addLayout(rail_head)

        self.btn_verify = QPushButton("Verify")
        self.btn_verify.setObjectName("CameraToolButton")
        self.btn_session = QPushButton("Session")
        self.btn_session.setObjectName("AccentButton")
        self.btn_undo_batch = QPushButton("Undo")
        self.btn_undo_batch.setObjectName("SecondaryButton")
        self.btn_reset_session = QPushButton("Reset")
        self.btn_reset_session.setObjectName("SecondaryButton")
        self.btn_confirm = QPushButton("COMPLETE")
        self.btn_confirm.setObjectName("PrimaryButton")

        for b in (self.btn_verify, self.btn_session, self.btn_undo_batch, self.btn_reset_session):
            b.setFixedHeight(42)
        self.btn_confirm.setFixedHeight(54)

        for b in (self.btn_verify, self.btn_session, self.btn_undo_batch, self.btn_reset_session):
            right.addWidget(b)
        right.addStretch(1)
        right.addWidget(self.btn_confirm)
        content.addWidget(right_card)

        # Floating session panel. Hidden by default; it overlays count page without changing layout.
        self.session_panel = QFrame(self)
        self.session_panel.setObjectName("FloatingSessionPanel")
        self.session_panel.hide()
        sp = QVBoxLayout(self.session_panel)
        sp.setContentsMargins(12, 10, 12, 10)
        sp.setSpacing(6)
        panel_head = QHBoxLayout()
        lbl = QLabel("SESSION")
        lbl.setObjectName("FloatingTitle")
        self.btn_close_session = QPushButton("×")
        self.btn_close_session.setObjectName("ClosePopupButton")
        self.btn_close_session.setFixedSize(36, 34)
        panel_head.addWidget(lbl)
        panel_head.addStretch(1)
        panel_head.addWidget(self.btn_close_session)
        sp.addLayout(panel_head)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        self.ed_user = QLineEdit(); self.ed_user.setProperty("kb_label", "User name"); self.ed_user.setPlaceholderText("User")
        self.cb_drug = QComboBox(); self.cb_drug.setProperty("kb_label", "Drug name/code"); self.cb_drug.setEditable(True); self.cb_drug.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ed_batch = QLineEdit(); self.ed_batch.setProperty("kb_label", "Lot/Batch"); self.ed_batch.setPlaceholderText("Lot/Batch")
        self.sp_expected = QSpinBox(); self.sp_expected.setProperty("kb_label", "Target count"); self.sp_expected.setRange(0, 100000); self.sp_expected.setValue(0)
        self.ed_notes = QTextEdit(); self.ed_notes.setProperty("kb_label", "Notes"); self.ed_notes.setPlaceholderText("Notes"); self.ed_notes.setFixedHeight(58)
        form.addWidget(QLabel("User"), 0, 0); form.addWidget(self.ed_user, 0, 1)
        form.addWidget(QLabel("Drug"), 1, 0); form.addWidget(self.cb_drug, 1, 1)
        form.addWidget(QLabel("Batch"), 2, 0); form.addWidget(self.ed_batch, 2, 1)
        form.addWidget(QLabel("Target"), 3, 0); form.addWidget(self.sp_expected, 3, 1)
        form.addWidget(QLabel("Notes"), 4, 0); form.addWidget(self.ed_notes, 4, 1)
        sp.addLayout(form)

        op_box = QFrame(); op_box.setObjectName("SegmentBox")
        op_l = QHBoxLayout(op_box); op_l.setContentsMargins(3, 3, 3, 3); op_l.setSpacing(4)
        self.btn_op_count = QPushButton("Count")
        self.btn_op_add = QPushButton("Receive")
        self.btn_op_remove = QPushButton("Dispense")
        for b in (self.btn_op_count, self.btn_op_add, self.btn_op_remove):
            b.setCheckable(True); b.setFixedHeight(34); op_l.addWidget(b)
        self.btn_op_count.setChecked(True)
        sp.addWidget(op_box)

        self.lbl_share_url = QLabel("QR: --")
        self.lbl_share_url.setObjectName("ShareText")
        self.lbl_share_url.setWordWrap(True)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedHeight(60)
        sp.addWidget(self.lbl_share_url)
        sp.addWidget(self.qr_label)
        sp.addStretch(1)

        self._count_value = 0
        self._total_value = 0
        self._batch_stack: list[tuple[str, int]] = []

        self.btn_start.clicked.connect(self.sig_start)
        self.btn_stop.clicked.connect(self.sig_stop)
        self.btn_freeze.toggled.connect(self._freeze_changed)
        self.btn_retake.clicked.connect(self.sig_retake)
        self.btn_verify.clicked.connect(self.toggle_session_panel)
        self.chk_smoothing.toggled.connect(self.sig_smoothing)
        self.btn_confirm.clicked.connect(self.sig_confirm_save)
        self.btn_add_batch.clicked.connect(lambda: self._apply_batch("+"))
        self.btn_sub_batch.clicked.connect(lambda: self._apply_batch("-"))
        self.btn_undo_batch.clicked.connect(self._undo_batch)
        self.btn_reset_session.clicked.connect(self._reset_batch)
        self.btn_session.clicked.connect(self.toggle_session_panel)
        self.btn_close_session.clicked.connect(self.close_session_panel)
        self.btn_op_add.clicked.connect(lambda: self._set_op("add"))
        self.btn_op_remove.clicked.connect(lambda: self._set_op("remove"))
        self.btn_op_count.clicked.connect(lambda: self._set_op("count_only"))
        self.sp_expected.valueChanged.connect(lambda _=0: self._refresh_delta())

    def sizeHint(self):  # type: ignore[override]
        return QSize(1024, 600)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._position_session_panel(opened=self._session_open, animate=False)

    def _session_geometry(self, opened: bool) -> QRect:
        w = 316
        h = min(382, max(340, self.height() - 36))
        y = 14
        x = self.width() - w - 54 if opened else self.width() + 12
        return QRect(x, y, w, h)

    def _position_session_panel(self, opened: bool, animate: bool) -> None:
        if opened:
            self.session_panel.show()
            self.session_panel.raise_()
        end = self._session_geometry(opened)
        if animate:
            self._session_anim = QPropertyAnimation(self.session_panel, b"geometry", self)
            self._session_anim.setDuration(190)
            self._session_anim.setEasingCurve(QEasingCurve.Type.OutCubic if opened else QEasingCurve.Type.InCubic)
            self._session_anim.setStartValue(self.session_panel.geometry())
            self._session_anim.setEndValue(end)
            if not opened:
                self._session_anim.finished.connect(self.session_panel.hide)
            self._session_anim.start()
        else:
            self.session_panel.setGeometry(end)
            if not opened:
                self.session_panel.hide()

    def toggle_session_panel(self):
        if self._session_open:
            self.close_session_panel()
        else:
            self.open_session_panel()

    def open_session_panel(self):
        self._session_open = True
        self._position_session_panel(opened=True, animate=True)

    def close_session_panel(self):
        self._session_open = False
        self._position_session_panel(opened=False, animate=True)

    def _freeze_changed(self, checked: bool):
        self.btn_freeze.setText("FROZEN" if checked else "CAPTURE")
        self.sig_freeze.emit(bool(checked))

    def set_count(self, value: int):
        self._count_value = int(value)
        self.lbl_count.setText(str(int(value)))
        self._refresh_delta()

    def set_state(self, text: str, danger: bool = False):
        self.lbl_state.setText(str(text).upper())
        self.lbl_state.setProperty("danger", bool(danger))
        self.lbl_state.style().unpolish(self.lbl_state)
        self.lbl_state.style().polish(self.lbl_state)

    def _refresh_delta(self):
        target = int(self.sp_expected.value())
        effective = self._total_value if self._total_value > 0 else self._count_value
        self.lbl_total.setText(f"Total {self._total_value}")
        self.lbl_target_summary.setText("Target --" if target <= 0 else f"Target {target}")
        self.lbl_delta.setText("Δ --" if target <= 0 else f"Δ {effective - target:+d}")
        self.preview_plus.setText(f"+ → {self._total_value + self._count_value}")
        self.preview_minus.setText(f"− → {max(0, self._total_value - self._count_value)}")

    def _apply_batch(self, op: str):
        c = int(self._count_value)
        if c <= 0:
            return
        self._batch_stack.append((op, c))
        self._total_value = self._total_value + c if op == "+" else max(0, self._total_value - c)
        self._refresh_delta()

    def _undo_batch(self):
        if not self._batch_stack:
            return
        op, c = self._batch_stack.pop()
        self._total_value = max(0, self._total_value - c) if op == "+" else self._total_value + c
        self._refresh_delta()

    def _reset_batch(self):
        self._batch_stack.clear()
        self._total_value = 0
        self._refresh_delta()

    def effective_count(self) -> int:
        return int(self._total_value if self._total_value > 0 else self._count_value)

    def _set_op(self, op: str):
        self.btn_op_add.setChecked(op == "add")
        self.btn_op_remove.setChecked(op == "remove")
        self.btn_op_count.setChecked(op == "count_only")
        self.sig_op_type.emit(op)
