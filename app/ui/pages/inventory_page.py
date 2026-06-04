from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextEdit, QLabel, QSplitter, QGroupBox
)


class InventoryPage(QWidget):
    # Drugs CRUD
    sig_add_drug = pyqtSignal()
    sig_edit_drug = pyqtSignal()
    sig_archive_drug = pyqtSignal()
    sig_search_drug = pyqtSignal(str)

    # Reports (transactions)
    sig_search_report = pyqtSignal(str)
    sig_select_report = pyqtSignal(int)
    sig_open_report = pyqtSignal(int)
    sig_delete_report = pyqtSignal(int)

    # Logs
    sig_clear_logs = pyqtSignal()
    sig_refresh_logs = pyqtSignal()

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # ---------------- Drugs tab ----------------
        tab_drugs = QWidget()
        dl = QVBoxLayout(tab_drugs)
        dl.setSpacing(8)

        top = QHBoxLayout()
        self.ed_search_drug = QLineEdit(); self.ed_search_drug.setProperty("kb_label", "Search drug")
        self.ed_search_drug.setPlaceholderText("Search drug...")
        self.btn_add = QPushButton("Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_archive = QPushButton("Archive")
        top.addWidget(self.ed_search_drug, 1)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_edit)
        top.addWidget(self.btn_archive)
        dl.addLayout(top)

        self.tbl_drugs = QTableWidget(0, 5)
        self.tbl_drugs.setHorizontalHeaderLabels(["Name", "Code", "On-hand", "Reorder", "Updated"])
        self.tbl_drugs.setSelectionBehavior(self.tbl_drugs.SelectionBehavior.SelectRows)
        self.tbl_drugs.setEditTriggers(self.tbl_drugs.EditTrigger.NoEditTriggers)
        dl.addWidget(self.tbl_drugs, 1)
        self.tabs.addTab(tab_drugs, "Drugs")

        # ---------------- Reports tab ----------------
        tab_reports = QWidget()
        rl = QVBoxLayout(tab_reports)
        rl.setSpacing(8)

        rtop = QHBoxLayout()
        self.ed_search_report = QLineEdit(); self.ed_search_report.setProperty("kb_label", "Search report")
        self.ed_search_report.setPlaceholderText("Search reports (drug/user/op/id)...")
        self.btn_open_report = QPushButton("Open PDF")
        self.btn_delete_report = QPushButton("Delete")
        rtop.addWidget(self.ed_search_report, 1)
        rtop.addWidget(self.btn_open_report)
        rtop.addWidget(self.btn_delete_report)
        rl.addLayout(rtop)

        spl = QSplitter(Qt.Orientation.Horizontal)
        rl.addWidget(spl, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.tbl_reports = QTableWidget(0, 6)
        self.tbl_reports.setHorizontalHeaderLabels(["ID", "Time", "Drug", "Op", "Count", "User"])
        self.tbl_reports.setSelectionBehavior(self.tbl_reports.SelectionBehavior.SelectRows)
        self.tbl_reports.setEditTriggers(self.tbl_reports.EditTrigger.NoEditTriggers)
        ll.addWidget(self.tbl_reports, 1)
        spl.addWidget(left)

        right = QWidget()
        rr = QVBoxLayout(right)
        rr.setContentsMargins(6, 0, 0, 0)
        rr.setSpacing(8)

        box = QGroupBox("Selected report")
        bl = QVBoxLayout(box)
        self.lbl_report_info = QLabel("(none)")
        self.lbl_report_info.setWordWrap(True)
        self.qr_report = QLabel()
        self.qr_report.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_report.setMinimumHeight(200)

        # Backwards-compatible alias expected by MainPresenter
        self.qr_preview = self.qr_report

        bl.addWidget(self.lbl_report_info)
        bl.addWidget(self.qr_report, 1)
        rr.addWidget(box, 1)
        spl.addWidget(right)

        spl.setStretchFactor(0, 7)
        spl.setStretchFactor(1, 3)

        self.tabs.addTab(tab_reports, "Reports")

        # ---------------- Logs tab ----------------
        tab_logs = QWidget()
        lg = QVBoxLayout(tab_logs)
        lg.setSpacing(8)
        ltop = QHBoxLayout()
        self.btn_refresh_logs = QPushButton("Refresh")
        self.btn_clear_logs = QPushButton("Clear logs")
        ltop.addStretch(1)
        ltop.addWidget(self.btn_refresh_logs)
        ltop.addWidget(self.btn_clear_logs)
        lg.addLayout(ltop)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        lg.addWidget(self.txt_logs, 1)
        self.tabs.addTab(tab_logs, "Logs")

        # Wiring
        self.btn_add.clicked.connect(self.sig_add_drug)
        self.btn_edit.clicked.connect(self.sig_edit_drug)
        self.btn_archive.clicked.connect(self.sig_archive_drug)
        self.ed_search_drug.textChanged.connect(lambda t: self.sig_search_drug.emit(str(t)))

        self.ed_search_report.textChanged.connect(lambda t: self.sig_search_report.emit(str(t)))
        self.btn_open_report.clicked.connect(self._emit_open_selected_report)
        self.btn_delete_report.clicked.connect(self._emit_delete_selected_report)
        self.tbl_reports.itemSelectionChanged.connect(self._emit_select_report)

        self.btn_clear_logs.clicked.connect(self.sig_clear_logs)
        self.btn_refresh_logs.clicked.connect(self.sig_refresh_logs)

    # ---------- Drugs ----------
    def selected_drug_id(self) -> int | None:
        rows = self.tbl_drugs.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.tbl_drugs.item(rows[0].row(), 0).data(256))  # Qt.UserRole

    def set_drugs(self, rows):
        self.tbl_drugs.setRowCount(0)
        for r in rows:
            rid = int(r["id"])
            row = self.tbl_drugs.rowCount()
            self.tbl_drugs.insertRow(row)

            it0 = QTableWidgetItem(str(r["name"]))
            it0.setData(256, rid)
            self.tbl_drugs.setItem(row, 0, it0)
            self.tbl_drugs.setItem(row, 1, QTableWidgetItem(str(r["code"] or "")))
            self.tbl_drugs.setItem(row, 2, QTableWidgetItem(str(int(r["on_hand"]))))
            self.tbl_drugs.setItem(row, 3, QTableWidgetItem(str(int(r["reorder_level"]))))
            self.tbl_drugs.setItem(row, 4, QTableWidgetItem(str(r["updated_at"])))

    # ---------- Reports ----------
    @staticmethod
    def _row_get(r, key: str, default=None):
        """Read from sqlite3.Row or dict safely (no .get() assumption)."""
        try:
            # sqlite3.Row supports `keys()` and `__getitem__`
            if hasattr(r, "keys") and key in r.keys():
                return r[key]
        except Exception:
            pass
        try:
            if isinstance(r, dict):
                return r.get(key, default)
        except Exception:
            pass
        return default

    def selected_txn_id(self) -> int | None:
        rows = self.tbl_reports.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.tbl_reports.item(rows[0].row(), 0).data(256))

    def set_reports(self, rows):
        self.tbl_reports.setRowCount(0)
        for r in rows:
            txn_id = int(self._row_get(r, "id", 0) or 0)

            row = self.tbl_reports.rowCount()
            self.tbl_reports.insertRow(row)

            it0 = QTableWidgetItem(str(txn_id))
            it0.setData(256, txn_id)
            self.tbl_reports.setItem(row, 0, it0)

            self.tbl_reports.setItem(row, 1, QTableWidgetItem(str(self._row_get(r, "ts", "") or "")))
            self.tbl_reports.setItem(row, 2, QTableWidgetItem(str(self._row_get(r, "drug_name", "") or "")))
            self.tbl_reports.setItem(row, 3, QTableWidgetItem(str(self._row_get(r, "op_type", "") or "")))
            self.tbl_reports.setItem(
                row, 4,
                QTableWidgetItem(str(int(self._row_get(r, "predicted_count", 0) or 0)))
            )
            self.tbl_reports.setItem(row, 5, QTableWidgetItem(str(self._row_get(r, "user_name", "") or "")))

    def set_report_details(self, info_text: str) -> None:
        """Backwards-compatible API expected by MainPresenter."""
        self.set_report_side(info_text, qr_pixmap=None)

    def set_report_side(self, info_text: str, qr_pixmap=None):
        self.lbl_report_info.setText(info_text)
        if qr_pixmap is None:
            self.qr_report.clear()
        else:
            self.qr_report.setPixmap(qr_pixmap)

    def _emit_select_report(self):
        tid = self.selected_txn_id()
        if tid is not None:
            self.sig_select_report.emit(int(tid))

    def _emit_open_selected_report(self):
        tid = self.selected_txn_id()
        if tid is not None:
            self.sig_open_report.emit(int(tid))

    def _emit_delete_selected_report(self):
        tid = self.selected_txn_id()
        if tid is not None:
            self.sig_delete_report.emit(int(tid))

    # ---------- Logs ----------
    def set_logs(self, text: str) -> None:
        """Set logs textbox content."""
        self.txt_logs.setPlainText(text)
        # optional: scroll to bottom
        c = self.txt_logs.textCursor()
        c.movePosition(c.MoveOperation.End)
        self.txt_logs.setTextCursor(c)
