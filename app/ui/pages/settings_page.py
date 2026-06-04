from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QCheckBox, QFrame
)
from PyQt6.QtCore import pyqtSignal


class SettingsPage(QWidget):
    sig_save = pyqtSignal()
    sig_browse_model = pyqtSignal()

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        card = QFrame(); card.setObjectName("SettingsCard")
        grid = QGridLayout(card)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setContentsMargins(18, 16, 18, 16)

        self.sp_cam_idx = QSpinBox(); self.sp_cam_idx.setProperty("kb_label", "Camera index"); self.sp_cam_idx.setRange(0, 10)
        self.sp_cam_w = QSpinBox(); self.sp_cam_w.setProperty("kb_label", "Camera width"); self.sp_cam_w.setRange(320, 1920); self.sp_cam_w.setSingleStep(160)
        self.sp_cam_h = QSpinBox(); self.sp_cam_h.setProperty("kb_label", "Camera height"); self.sp_cam_h.setRange(240, 1080); self.sp_cam_h.setSingleStep(120)
        self.sp_cam_fps = QSpinBox(); self.sp_cam_fps.setProperty("kb_label", "Camera FPS"); self.sp_cam_fps.setRange(1, 60)

        self.ed_model_path = QLineEdit(); self.ed_model_path.setProperty("kb_label", "Model path")
        self.btn_browse = QPushButton("Browse")
        self.ed_model_arch = QLineEdit(); self.ed_model_arch.setProperty("kb_label", "Model arch"); self.ed_model_arch.setPlaceholderText("PANet")
        self.sp_thr = QSpinBox(); self.sp_thr.setProperty("kb_label", "Threshold percent"); self.sp_thr.setRange(1, 99)
        self.sp_ksize = QSpinBox(); self.sp_ksize.setProperty("kb_label", "NMS kernel size"); self.sp_ksize.setRange(3, 21); self.sp_ksize.setSingleStep(2)
        self.sp_min_peak = QDoubleSpinBox(); self.sp_min_peak.setProperty("kb_label", "Minimum peak score"); self.sp_min_peak.setRange(0.0, 5.0); self.sp_min_peak.setDecimals(3); self.sp_min_peak.setSingleStep(0.05)
        self.sp_max_peaks = QSpinBox(); self.sp_max_peaks.setProperty("kb_label", "Max peaks"); self.sp_max_peaks.setRange(10, 5000)
        self.sp_rt_fps = QSpinBox(); self.sp_rt_fps.setProperty("kb_label", "Realtime inference FPS"); self.sp_rt_fps.setRange(1, 30)
        self.sp_smooth = QDoubleSpinBox(); self.sp_smooth.setProperty("kb_label", "Smoothing alpha"); self.sp_smooth.setRange(0.0, 0.95); self.sp_smooth.setSingleStep(0.05)
        self.sp_count_window = QSpinBox(); self.sp_count_window.setProperty("kb_label", "Count queue window"); self.sp_count_window.setRange(1, 31); self.sp_count_window.setSingleStep(2)
        self.sp_count_votes = QSpinBox(); self.sp_count_votes.setProperty("kb_label", "Count min votes"); self.sp_count_votes.setRange(1, 31)
        self.chk_roi = QCheckBox("Enable ROI")
        self.sp_roi_x = QSpinBox(); self.sp_roi_x.setProperty("kb_label", "ROI x"); self.sp_roi_x.setRange(0, 320)
        self.sp_roi_y = QSpinBox(); self.sp_roi_y.setProperty("kb_label", "ROI y"); self.sp_roi_y.setRange(0, 240)
        self.sp_roi_w = QSpinBox(); self.sp_roi_w.setProperty("kb_label", "ROI width"); self.sp_roi_w.setRange(1, 320)
        self.sp_roi_h = QSpinBox(); self.sp_roi_h.setProperty("kb_label", "ROI height"); self.sp_roi_h.setRange(1, 240)

        self.chk_share = QCheckBox("Enable report sharing")
        self.chk_token = QCheckBox("Require token in report URL")
        self.sp_share_port = QSpinBox(); self.sp_share_port.setProperty("kb_label", "Share port"); self.sp_share_port.setRange(1024, 65535)
        self.chk_tunnel = QCheckBox("Use Cloudflare Quick Tunnel by default")
        self.ed_cloudflared = QLineEdit(); self.ed_cloudflared.setProperty("kb_label", "cloudflared path"); self.ed_cloudflared.setPlaceholderText("cloudflared")

        r = 0
        grid.addWidget(QLabel("Camera index"), r, 0); grid.addWidget(self.sp_cam_idx, r, 1)
        grid.addWidget(QLabel("Resolution"), r, 2); grid.addWidget(self.sp_cam_w, r, 3); grid.addWidget(self.sp_cam_h, r, 4)
        grid.addWidget(QLabel("FPS"), r, 5); grid.addWidget(self.sp_cam_fps, r, 6); r += 1
        grid.addWidget(QLabel("Model path"), r, 0); grid.addWidget(self.ed_model_path, r, 1, 1, 5); grid.addWidget(self.btn_browse, r, 6); r += 1
        grid.addWidget(QLabel("Model arch"), r, 0); grid.addWidget(self.ed_model_arch, r, 1, 1, 2)
        grid.addWidget(QLabel("Threshold (%)"), r, 3); grid.addWidget(self.sp_thr, r, 4)
        grid.addWidget(QLabel("NMS"), r, 5); grid.addWidget(self.sp_ksize, r, 6); r += 1
        grid.addWidget(QLabel("Realtime FPS"), r, 0); grid.addWidget(self.sp_rt_fps, r, 1)
        grid.addWidget(QLabel("Max peaks"), r, 2); grid.addWidget(self.sp_max_peaks, r, 3)
        grid.addWidget(QLabel("Min peak"), r, 4); grid.addWidget(self.sp_min_peak, r, 5); r += 1
        grid.addWidget(QLabel("Smoothing"), r, 0); grid.addWidget(self.sp_smooth, r, 1)
        grid.addWidget(QLabel("Queue"), r, 2); grid.addWidget(self.sp_count_window, r, 3)
        grid.addWidget(QLabel("Votes"), r, 4); grid.addWidget(self.sp_count_votes, r, 5)
        grid.addWidget(self.chk_roi, r, 6); r += 1
        grid.addWidget(QLabel("ROI x/y"), r, 0); grid.addWidget(self.sp_roi_x, r, 1); grid.addWidget(self.sp_roi_y, r, 2)
        grid.addWidget(QLabel("ROI w/h"), r, 3); grid.addWidget(self.sp_roi_w, r, 4); grid.addWidget(self.sp_roi_h, r, 5); r += 1
        grid.addWidget(self.chk_share, r, 0, 1, 2); grid.addWidget(QLabel("Port"), r, 2); grid.addWidget(self.sp_share_port, r, 3); grid.addWidget(self.chk_token, r, 4, 1, 3); r += 1
        grid.addWidget(self.chk_tunnel, r, 0, 1, 3); grid.addWidget(QLabel("cloudflared"), r, 3); grid.addWidget(self.ed_cloudflared, r, 4, 1, 3); r += 1

        root.addWidget(card, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.setMinimumHeight(58)
        bottom.addWidget(self.btn_save)
        root.addLayout(bottom)

        self.btn_save.clicked.connect(self.sig_save)
        self.btn_browse.clicked.connect(self.sig_browse_model)
