from __future__ import annotations

import logging
import os
import secrets
import shutil
from collections import Counter, deque
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSlot, Qt, QUrl
from PyQt6.QtGui import QImage, QPixmap, QDesktopServices
from PyQt6.QtWidgets import QApplication, QFileDialog

from app.core.bus import MessageBus
from app.core.config import AppConfig
from app.core.types import AppEvent, AppEventType, OpType, InferResult, Frame
from app.data import db as dbmod
from app.data.repositories.drug_repo import DrugRepository
from app.data.repositories.inventory_repo import InventoryRepository
from app.data.repositories.txn_repo import TransactionRepository
from app.data.repositories.log_repo import LogRepository
from app.services.camera_service import CameraConfig
from app.services.postprocess_utils import draw_overlay
from app.services.report_service import ReportService, ReportInfo
from app.services.qr_service import make_qr_png
from app.workers.camera_worker import CameraWorker
from app.workers.infer_worker import InferWorker
from app.workers.flask_worker import FlaskWorker
from app.workers.tunnel_worker import TunnelWorker
from app.ui.widgets.virtual_keyboard import KeyboardController

log = logging.getLogger("presenter")


def bgr_to_qimage(bgr: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()


def get_lan_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MainPresenter(QObject):
    def __init__(self, window, cfg: AppConfig):
        super().__init__()
        self.window = window
        self.cfg = cfg
        self.bus = MessageBus()

        dbmod.init_db(self.cfg.storage.root_dir)
        self.conn = dbmod.connect(self.cfg.storage.root_dir)
        self.repo_drug = DrugRepository(self.conn)
        self.repo_inv = InventoryRepository(self.conn)
        self.repo_txn = TransactionRepository(self.conn)
        self.repo_log = LogRepository(self.conn)

        self._op_type: str = OpType.COUNT_ONLY.value
        self._last_frame: Optional[Frame] = None
        self._frozen_frame: Optional[Frame] = None
        self._last_infer: Optional[InferResult] = None
        self._count_window: deque[int] = deque(maxlen=max(1, int(getattr(self.cfg.model, "count_queue_window", 7) or 7)))
        self._count_result_cache: dict[int, InferResult] = {}
        self._display_count: Optional[int] = None
        self._syncing_settings = False
        self._settings_arch: str = str(self.cfg.model.model_arch or "")
        self._lan_ip: str = get_lan_ip()
        self._share_visible_url: str = ""
        self._public_url: str = ""
        self._share_token: str = secrets.token_urlsafe(18)

        app = QApplication.instance()
        self.kb_ctrl = KeyboardController(self.window.kb_widget)
        self.kb_ctrl.install(app)
        self.window.btn_kb_toggle.toggled.connect(self._on_toggle_keyboard)
        self.kb_ctrl.visibility_changed.connect(self._sync_kb_button)

        self._init_workers()
        self._bind_ui()
        self._sync_settings_page_from_cfg()
        self.refresh_drugs()
        self.refresh_inventory()

        if self.cfg.share.enable_qr_share:
            self.start_share_server()
        if self.cfg.share.enable_qr_share and self.cfg.cloudflare.enabled and self.cfg.cloudflare.auto_start:
            self.start_tunnel()
        self.window.show_page("menu")

    def shutdown(self):
        for w in (getattr(self, "camera_worker", None), getattr(self, "infer_worker", None)):
            try:
                if w is not None:
                    w.stop()
            except Exception:
                pass
        try: self.flask_worker.stop()
        except Exception: pass
        try: self.tunnel_worker.stop()
        except Exception: pass
        for th in (getattr(self, "camera_thread", None), getattr(self, "infer_thread", None), getattr(self, "flask_thread", None), getattr(self, "tunnel_thread", None)):
            try:
                if th is not None:
                    th.quit(); th.wait(1000)
            except Exception:
                pass
        try: self.conn.close()
        except Exception: pass

    def _bind_ui(self):
        cp = self.window.page_count
        ip = self.window.page_inventory
        sp = self.window.page_settings

        self.window.sig_show_page.connect(self._on_show_page)
        cp.sig_start.connect(self.on_start)
        cp.sig_stop.connect(self.on_stop)
        cp.sig_freeze.connect(self.on_freeze)
        cp.sig_retake.connect(self.on_retake)
        cp.sig_confirm_save.connect(self.on_confirm_save)
        cp.sig_op_type.connect(self.on_op_type_changed)
        cp.sig_smoothing.connect(self.on_smoothing_changed)

        ip.sig_add_drug.connect(self.on_add_drug)
        ip.sig_edit_drug.connect(self.on_edit_drug)
        ip.sig_archive_drug.connect(self.on_archive_drug)
        ip.sig_search_drug.connect(self.on_search_drug)
        ip.sig_search_report.connect(self.on_search_report)
        ip.sig_select_report.connect(self.on_select_report)
        ip.sig_open_report.connect(self.on_open_report)
        ip.sig_delete_report.connect(self.on_delete_report)
        ip.sig_refresh_logs.connect(lambda: self.refresh_logs())
        ip.sig_clear_logs.connect(self.on_clear_logs)

        sp.sig_save.connect(self.on_save_settings)
        sp.sig_browse_model.connect(self.on_browse_model)
        sp.sig_browse_onnx.connect(self.on_browse_onnx_model)
        sp.sig_full_screen.connect(self.on_full_screen)
        sp.sig_windowed.connect(self.on_windowed)
        sp.sig_quit_app.connect(self.on_quit_app)
        sp.ed_model_arch.currentTextChanged.connect(self.on_settings_model_arch_changed)

        self.camera_worker.status_changed.connect(self._ui_camera_status)
        self.infer_worker.status_changed.connect(self._ui_model_status)
        self.flask_worker.status.connect(self._ui_share_status)
        self.tunnel_worker.status.connect(self._ui_tunnel_status)
        self.camera_worker.frame_ready.connect(self.on_frame)
        self.infer_worker.infer_ready.connect(self.on_infer)
        self.bus.event_published.connect(self.on_event)

    @pyqtSlot(str)
    def _on_show_page(self, name: str):
        self.window.show_page(name)

    @pyqtSlot(bool)
    def _on_toggle_keyboard(self, checked: bool):
        if checked:
            self.kb_ctrl.show_keyboard(auto=False)
            self.window.set_keyboard_visible(True)
        else:
            self.kb_ctrl.hide_keyboard(manual=True)
            self.window.set_keyboard_visible(False)

    @pyqtSlot(bool)
    def _sync_kb_button(self, vis: bool):
        btn = self.window.btn_kb_toggle
        if btn.isChecked() == vis:
            return
        btn.blockSignals(True); btn.setChecked(vis); btn.blockSignals(False)
        self.window.set_keyboard_visible(vis)

    def _sync_settings_page_from_cfg(self):
        sp = self.window.page_settings
        self._syncing_settings = True
        sp.sp_cam_idx.setValue(int(self.cfg.camera.device_index))
        sp.sp_cam_w.setValue(int(self.cfg.camera.width))
        sp.sp_cam_h.setValue(int(self.cfg.camera.height))
        sp.sp_cam_fps.setValue(int(self.cfg.camera.fps))
        sp.chk_share.setChecked(bool(self.cfg.share.enable_qr_share))
        sp.chk_token.setChecked(bool(self.cfg.share.token_required))
        sp.sp_share_port.setValue(int(self.cfg.share.port))
        sp.chk_tunnel.setChecked(bool(self.cfg.cloudflare.enabled))
        sp.ed_cloudflared.setText(self.cfg.cloudflare.cloudflared_path)
        ms = self.cfg.model
        sp.cb_runtime.setCurrentText(ms.runtime)
        sp.ed_model_path.setText(ms.model_path)
        sp.ed_onnx_path.setText(ms.onnx_model_path)
        sp.ed_model_arch.setCurrentText(ms.model_arch)
        self._settings_arch = str(ms.model_arch or "")
        self._set_postprocess_controls(ms.postprocess_dict())
        cp = self.window.page_count
        cp.chk_smoothing.blockSignals(True)
        cp.chk_smoothing.setChecked(float(ms.smoothing_alpha) > 0.0)
        cp.chk_smoothing.blockSignals(False)
        self._syncing_settings = False
        self._apply_model_settings_to_infer()

    def _postprocess_profile_from_settings(self) -> dict:
        sp = self.window.page_settings
        return {
            "threshold": float(sp.sp_thr.value()) / 100.0,
            "nms_ksize": int(sp.sp_ksize.value()),
            "min_peak": float(sp.sp_min_peak.value()),
            "max_peaks": int(sp.sp_max_peaks.value()),
            "realtime_fps": int(sp.sp_rt_fps.value()),
            "torch_num_threads": int(sp.sp_torch_threads.value()),
            "smoothing_alpha": float(sp.sp_smooth.value()),
            "count_queue_window": int(sp.sp_count_window.value()),
            "count_queue_min_votes": int(sp.sp_count_votes.value()),
            "roi_enabled": bool(sp.chk_roi.isChecked()),
            "roi_x": int(sp.sp_roi_x.value()),
            "roi_y": int(sp.sp_roi_y.value()),
            "roi_w": int(sp.sp_roi_w.value()),
            "roi_h": int(sp.sp_roi_h.value()),
        }

    def _set_postprocess_controls(self, profile: dict) -> None:
        sp = self.window.page_settings
        p = profile or {}
        sp.sp_rt_fps.setValue(int(p.get("realtime_fps", self.cfg.model.realtime_fps)))
        sp.sp_thr.setValue(int(round(float(p.get("threshold", self.cfg.model.threshold)) * 100)))
        sp.sp_ksize.setValue(int(p.get("nms_ksize", self.cfg.model.nms_ksize)))
        sp.sp_min_peak.setValue(float(p.get("min_peak", self.cfg.model.min_peak)))
        sp.sp_max_peaks.setValue(int(p.get("max_peaks", self.cfg.model.max_peaks)))
        sp.sp_torch_threads.setValue(int(p.get("torch_num_threads", self.cfg.model.torch_num_threads)))
        sp.sp_smooth.setValue(float(p.get("smoothing_alpha", self.cfg.model.smoothing_alpha)))
        sp.sp_count_window.setValue(int(p.get("count_queue_window", self.cfg.model.count_queue_window)))
        sp.sp_count_votes.setValue(int(p.get("count_queue_min_votes", self.cfg.model.count_queue_min_votes)))
        sp.chk_roi.setChecked(bool(p.get("roi_enabled", self.cfg.model.roi_enabled)))
        sp.sp_roi_x.setValue(int(p.get("roi_x", self.cfg.model.roi_x)))
        sp.sp_roi_y.setValue(int(p.get("roi_y", self.cfg.model.roi_y)))
        sp.sp_roi_w.setValue(int(p.get("roi_w", self.cfg.model.roi_w)))
        sp.sp_roi_h.setValue(int(p.get("roi_h", self.cfg.model.roi_h)))

    @pyqtSlot(str)
    def on_settings_model_arch_changed(self, arch: str):
        if self._syncing_settings:
            return
        old_arch = self._settings_arch or self.cfg.model.model_arch
        if old_arch:
            self.cfg.model.update_postprocess_profile(old_arch, self._postprocess_profile_from_settings())
        self._settings_arch = str(arch or "")
        self.cfg.model.ensure_postprocess_profiles(False)
        profile = self.cfg.model.postprocess_profiles.get(self._settings_arch, self.cfg.model.postprocess_dict())
        self._set_postprocess_controls(profile)

    def _apply_model_settings_to_infer(self):
        ms = self.cfg.model
        self.infer_worker.set_params(
            ms.realtime_fps,
            ms.torch_num_threads,
            ms.smoothing_alpha,
            ms.nms_ksize,
            ms.max_peaks,
            int(ms.threshold * 100),
            ms.min_peak,
            ms.roi_enabled,
            ms.roi_x,
            ms.roi_y,
            ms.roi_w,
            ms.roi_h,
        )
        self.infer_worker.set_model(ms.runtime, ms.model_path, ms.onnx_model_path, ms.model_arch)
        self._reset_count_stabilizer()

    def _reset_count_stabilizer(self):
        ms = self.cfg.model
        window = max(1, int(getattr(ms, "count_queue_window", 7) or 7))
        self._count_window = deque(maxlen=window)
        self._count_result_cache = {}
        self._display_count = None

    def _stabilize_infer_result(self, res: InferResult) -> InferResult:
        if self._frozen_frame is not None and res.ts_ms == self._frozen_frame.ts_ms:
            self._reset_count_stabilizer()
            self._count_window.append(int(res.count))
            self._count_result_cache[int(res.count)] = res
            self._display_count = int(res.count)
            return res

        ms = self.cfg.model
        min_votes = max(1, int(getattr(ms, "count_queue_min_votes", 1) or 1))
        min_votes = min(min_votes, max(1, self._count_window.maxlen or 1))
        raw_count = int(res.count)

        self._count_window.append(raw_count)
        self._count_result_cache[raw_count] = res
        votes = Counter(self._count_window)
        best_votes = max(votes.values())
        candidates = [c for c, v in votes.items() if v == best_votes]

        if self._display_count in candidates:
            chosen_count = int(self._display_count)
        elif raw_count in candidates:
            chosen_count = raw_count
        else:
            chosen_count = int(candidates[0])

        if best_votes < min_votes and self._display_count is not None:
            chosen_count = int(self._display_count)

        self._display_count = chosen_count
        return InferResult(
            ts_ms=res.ts_ms,
            count=chosen_count,
            centers=res.centers,
            mask_u8=res.mask_u8,
            score_map=res.score_map,
        )

    def _init_workers(self):
        self.camera_thread = QThread()
        cam = self.cfg.camera
        cam_cfg = CameraConfig(
            cam.device_index,
            cam.width,
            cam.height,
            cam.fps,
            cam.lock_controls,
            cam.auto_exposure_value,
            cam.exposure,
            cam.gain,
            cam.lock_white_balance,
            cam.white_balance_temperature,
        )
        self.camera_worker = CameraWorker(self.bus, cam_cfg)
        self.camera_worker.moveToThread(self.camera_thread)
        self.camera_thread.started.connect(self.camera_worker.start)

        self.infer_thread = QThread()
        self.infer_worker = InferWorker(self.bus)
        self.infer_worker.moveToThread(self.infer_thread)
        self.infer_thread.started.connect(self.infer_worker.start)

        self.flask_thread = QThread()
        self.flask_worker = FlaskWorker(self.bus, self.cfg.storage.reports_dir)
        self.flask_worker.moveToThread(self.flask_thread)

        self.tunnel_thread = QThread()
        self.tunnel_worker = TunnelWorker(self.bus, self.cfg.cloudflare.cloudflared_path)
        self.tunnel_worker.moveToThread(self.tunnel_thread)

        self.camera_thread.start(); self.infer_thread.start(); self.flask_thread.start(); self.tunnel_thread.start()

    @pyqtSlot(object)
    def on_event(self, ev: AppEvent):
        try:
            self.repo_log.add(ev.typ.value, ev.source, ev.message); self.conn.commit()
        except Exception:
            pass
        self.refresh_logs()

    @pyqtSlot(bool)
    def _ui_camera_status(self, ok: bool):
        self.window.lbl_cam.setText(f"Camera: {'OK' if ok else 'Disconnected'}")

    @pyqtSlot(bool)
    def _ui_model_status(self, ok: bool):
        self.window.lbl_model.setText(f"Model: {'OK' if ok else 'Error'}")

    @pyqtSlot(str)
    def _ui_share_status(self, url: str):
        if not url:
            self._share_visible_url = ""
            if not self._public_url:
                self.window.lbl_flask.setText("Tunnel: Off")
            return
        port = int(self.cfg.share.port)
        self._share_visible_url = f"http://{self._lan_ip}:{port}"
        if not self._public_url:
            self.window.lbl_flask.setText("Tunnel: local only")

    @pyqtSlot(str, str)
    def _ui_tunnel_status(self, state: str, public_url: str):
        self._public_url = public_url or ""
        self.window.lbl_flask.setText(f"Tunnel: {state}" + (f" · {public_url}" if public_url else ""))

    @pyqtSlot(object)
    def on_frame(self, fr: Frame):
        if self._frozen_frame is None:
            self._last_frame = fr
            fr_use = fr
        else:
            fr_use = self._frozen_frame
        bgr = fr_use.bgr
        if self._last_infer is not None:
            bgr = draw_overlay(bgr, self._last_infer.centers, self._last_infer.count, self._last_infer.mask_u8)
        qim = bgr_to_qimage(bgr)
        pix = QPixmap.fromImage(qim)
        self.window.page_count.preview.setPixmap(pix)

    @pyqtSlot(object)
    def on_infer(self, res: InferResult):
        if self._frozen_frame is not None and res.ts_ms != self._frozen_frame.ts_ms:
            return
        stable_res = self._stabilize_infer_result(res)
        self._last_infer = stable_res
        self.window.page_count.set_count(int(stable_res.count))
        self.window.page_count.set_state("Frozen" if self._frozen_frame is not None else "Counting")

    @pyqtSlot()
    def on_start(self):
        self.on_retake(); self.bus.publish(AppEvent(AppEventType.LOG, "app", "Start"))

    @pyqtSlot()
    def on_stop(self):
        self.bus.publish(AppEvent(AppEventType.LOG, "app", "Stop")); self.window.page_count.set_state("Stopped")

    @pyqtSlot(bool)
    def on_freeze(self, freeze: bool):
        if freeze:
            if self._last_frame is not None:
                self._frozen_frame = self._last_frame
                self._last_infer = None
                self._reset_count_stabilizer()
                self.infer_worker.set_freeze_frame(self._frozen_frame)
            self.infer_worker.set_freeze(True)
            self.window.page_count.set_state("Frozen")
            self.bus.publish(AppEvent(AppEventType.LOG, "app", "Capture/Freeze"))
        else:
            self.on_retake()

    @pyqtSlot()
    def on_retake(self):
        self._frozen_frame = None
        self._last_infer = None
        self._reset_count_stabilizer()
        self.infer_worker.set_freeze_frame(None)
        self.window.page_count.btn_freeze.setChecked(False)
        self.infer_worker.set_freeze(False)
        self.window.page_count.set_state("Ready")
        self.bus.publish(AppEvent(AppEventType.LOG, "app", "Retake"))

    @pyqtSlot(bool)
    def on_smoothing_changed(self, enabled: bool):
        self.cfg.model.smoothing_alpha = 0.35 if enabled else 0.0
        self._apply_model_settings_to_infer()

    @pyqtSlot(str)
    def on_op_type_changed(self, op: str):
        self._op_type = op

    @pyqtSlot()
    def on_confirm_save(self):
        fr = self._frozen_frame or self._last_frame
        if fr is None:
            self.bus.publish(AppEvent(AppEventType.ERROR, "app", "No frame to save")); self.window.page_count.set_state("No frame", True); return
        if self._last_infer is None:
            self.bus.publish(AppEvent(AppEventType.ERROR, "app", "No inference result yet")); self.window.page_count.set_state("No model result", True); return

        cp = self.window.page_count
        user = cp.ed_user.text().strip()
        drug_text = cp.cb_drug.currentText().strip()
        batch = cp.ed_batch.text().strip()
        notes = cp.ed_notes.toPlainText().strip()
        expected = int(cp.sp_expected.value())
        expected_val = expected if expected > 0 else None
        pred_count = int(cp.effective_count())
        delta = int(pred_count - expected_val) if expected_val is not None else None

        drug_id = None; drug_name = "(none)"; drug_code = ""
        if drug_text:
            for d in self.repo_drug.list_active():
                if drug_text.lower() == str(d["name"]).lower() or (d["code"] and drug_text.lower() == str(d["code"]).lower()):
                    drug_id = int(d["id"]); drug_name = str(d["name"]); drug_code = str(d["code"] or ""); break
            if drug_id is None:
                drug_id = int(self.repo_drug.create(drug_text, code="")); drug_name = drug_text

        inv_delta = +pred_count if self._op_type == OpType.RECEIVE.value else (-pred_count if self._op_type == OpType.DISPENSE.value else 0)
        ts_dt = datetime.now(); ts = ts_dt.isoformat(timespec="seconds")
        folder = ""
        try:
            self.conn.execute("BEGIN")
            txn_id = int(self.repo_txn.create(ts=ts, user_name=user, drug_id=drug_id, op_type=self._op_type,
                predicted_count=pred_count, expected_count=expected_val, delta=delta,
                weight_value=None, weight_stable=None,
                notes=(notes if not batch else f"batch={batch}; {notes}".strip()), raw_path="", overlay_path="", report_md_path="", report_pdf_path=""))
            rep = ReportService(self.cfg.storage.reports_dir)
            folder = rep.txn_folder(ts_dt, txn_id)
            raw_path = os.path.join(folder, "raw.jpg")
            overlay_path = os.path.join(folder, "overlay.jpg")
            cv2.imwrite(raw_path, fr.bgr)
            overlay = draw_overlay(fr.bgr, self._last_infer.centers, self._last_infer.count, self._last_infer.mask_u8)
            cv2.imwrite(overlay_path, overlay)
            info = ReportInfo(txn_id=txn_id, ts=ts, user_name=user, drug_name=drug_name, drug_code=drug_code,
                op_type=self._op_type, predicted_count=pred_count, expected_count=expected_val, delta=delta,
                weight_value=None, weight_stable=None, notes=(notes if not batch else f"batch={batch}; {notes}".strip()), raw_path=raw_path, overlay_path=overlay_path)
            md_path = rep.write_markdown(folder, info)
            pdf_path = rep.write_pdf(folder, info)
            self.conn.execute("UPDATE transactions SET raw_path=?, overlay_path=?, report_md_path=?, report_pdf_path=? WHERE id=?", (raw_path, overlay_path, md_path, pdf_path, int(txn_id)))
            if drug_id is not None and inv_delta != 0:
                self.repo_inv.apply_delta(int(drug_id), int(inv_delta))
            self.conn.commit()
            self.bus.publish(AppEvent(AppEventType.LOG, "app", f"Saved txn {txn_id}"))
            self.window.page_count.set_state("Saved")
            self.refresh_drugs(); self.refresh_inventory()
            folder_rel = os.path.relpath(folder, self.cfg.storage.reports_dir).replace("\\", "/")
            self._update_qr_for_report(folder_rel)
        except Exception as e:
            log.exception("Save failed")
            try: self.conn.rollback()
            except Exception: pass
            if folder and os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
            self.bus.publish(AppEvent(AppEventType.ERROR, "app", f"Save failed: {e}"))
            self.window.page_count.set_state("Save failed", True)

    def _base_share_url(self) -> str:
        if self._public_url:
            return self._public_url.rstrip("/")
        if self._share_visible_url:
            return self._share_visible_url.rstrip("/")
        return f"http://{self._lan_ip}:{int(self.cfg.share.port)}"

    def _qr_link_for_folder(self, folder_rel: str) -> str:
        if not self.cfg.share.enable_qr_share:
            return ""
        link = f"{self._base_share_url()}/reports/{folder_rel}/report.pdf"
        if self.cfg.share.token_required:
            link += f"?token={self._share_token}"
        return link

    def _update_qr_for_report(self, folder_rel: str):
        cp = self.window.page_count
        link = self._qr_link_for_folder(folder_rel)
        if not link:
            cp.lbl_share_url.setText("QR: sharing off"); cp.qr_label.clear(); return
        cp.lbl_share_url.setText(f"QR: {link}")
        qr_path = os.path.join(self.cfg.storage.reports_dir, folder_rel, "qr.png")
        try:
            make_qr_png(link, qr_path)
            pix = QPixmap(qr_path)
            cp.qr_label.setPixmap(pix.scaled(cp.qr_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception as e:
            self.bus.publish(AppEvent(AppEventType.ERROR, "app", f"QR gen failed: {e}"))

    def refresh_drugs(self):
        drugs = self.repo_drug.list_active(); cb = self.window.page_count.cb_drug; cur = cb.currentText(); cb.blockSignals(True); cb.clear()
        for d in drugs: cb.addItem(str(d["name"]), int(d["id"]))
        cb.blockSignals(False)
        if cur: cb.setCurrentText(cur)

    def refresh_inventory(self):
        self._inventory_rows = self.repo_inv.list_with_drugs(); self._reports_rows = self.repo_txn.list_recent(200)
        self.refresh_inventory_table(); self.refresh_reports_table(); self.refresh_logs()

    def refresh_inventory_table(self, q: str | None = None):
        ip = self.window.page_inventory; rows = list(self._inventory_rows); qv = (q if q is not None else ip.ed_search_drug.text()).strip().lower()
        if qv: rows = [r for r in rows if qv in str(r["name"]).lower() or qv in str(r["code"] or "").lower()]
        ip.set_drugs(rows)

    def refresh_reports_table(self, q: str | None = None):
        ip = self.window.page_inventory; qv = (q if q is not None else ip.ed_search_report.text()).strip(); rows = self.repo_txn.search(qv, limit=200); ip.set_reports(rows)
        if rows: ip.tbl_reports.selectRow(0)

    def refresh_logs(self):
        ip = self.window.page_inventory; logs = self.repo_log.list_recent(200); lines = [f"{r['ts']} [{r['level']}] {r['source']}: {r['message']}" for r in logs]; ip.set_logs("\n".join(lines))

    @pyqtSlot(str)
    def on_search_drug(self, q: str): self.refresh_inventory_table(q)
    @pyqtSlot(str)
    def on_search_report(self, q: str): self.refresh_reports_table(q)

    @pyqtSlot(int)
    def on_select_report(self, txn_id: int):
        ip = self.window.page_inventory; row = self.repo_txn.get_by_id(int(txn_id))
        if row is None: ip.set_report_details("(not found)"); ip.qr_preview.clear(); return
        details = [f"Txn ID: {row['id']}", f"Time: {row['ts']}", f"User: {row['user_name']}", f"Drug: {row['drug_name'] or ''} ({row['drug_code'] or ''})", f"Op: {row['op_type']}", f"Count: {row['predicted_count']}  Expected: {row['expected_count']}  Delta: {row['delta']}"]
        if row['notes']: details.append(f"Notes: {row['notes']}")
        ip.set_report_details("\n".join(details))
        pdf_path = str(row["report_pdf_path"] or "")
        if pdf_path and os.path.exists(pdf_path) and self.cfg.share.enable_qr_share:
            folder = os.path.dirname(pdf_path); folder_rel = os.path.relpath(folder, self.cfg.storage.reports_dir).replace("\\", "/"); link = self._qr_link_for_folder(folder_rel); qr_path = os.path.join(folder, "qr.png")
            try:
                make_qr_png(link, qr_path); pix = QPixmap(qr_path); ip.qr_preview.setPixmap(pix.scaled(ip.qr_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            except Exception: ip.qr_preview.clear()
        else: ip.qr_preview.clear()

    @pyqtSlot(int)
    def on_open_report(self, txn_id: int):
        row = self.repo_txn.get_by_id(int(txn_id))
        if row is None: return
        pdf_path = str(row["report_pdf_path"] or "")
        if not pdf_path or not os.path.exists(pdf_path): self.bus.publish(AppEvent(AppEventType.ERROR, "app", "PDF not found")); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

    @pyqtSlot(int)
    def on_delete_report(self, txn_id: int):
        row = self.repo_txn.get_by_id(int(txn_id))
        if row is None: return
        def _do_delete():
            try:
                self.conn.execute("BEGIN")
                drug_id = row["drug_id"]; pred = int(row["predicted_count"] or 0); op = str(row["op_type"] or "")
                if drug_id is not None and pred:
                    if op == OpType.RECEIVE.value: self.repo_inv.apply_delta(int(drug_id), -pred)
                    elif op == OpType.DISPENSE.value: self.repo_inv.apply_delta(int(drug_id), +pred)
                self.repo_txn.delete(int(txn_id)); self.conn.commit()
                pdf_path = str(row["report_pdf_path"] or ""); folder = os.path.dirname(pdf_path) if pdf_path else ""
                if folder and os.path.isdir(folder): shutil.rmtree(folder, ignore_errors=True)
                self.bus.publish(AppEvent(AppEventType.LOG, "app", f"Deleted txn {txn_id}")); self.refresh_inventory()
            except Exception as e:
                try: self.conn.rollback()
                except Exception: pass
                self.bus.publish(AppEvent(AppEventType.ERROR, "app", f"Delete failed: {e}"))
        self.window.overlay.show_confirm("Delete report", f"Delete transaction {txn_id}? Inventory will be adjusted if needed.", _do_delete, yes_text="Delete", no_text="Cancel")

    @pyqtSlot()
    def on_clear_logs(self):
        def _do_clear():
            try:
                self.conn.execute("BEGIN"); self.repo_log.clear_all(); self.conn.commit(); self.refresh_logs()
            except Exception as e:
                try: self.conn.rollback()
                except Exception: pass
                self.bus.publish(AppEvent(AppEventType.ERROR, "app", f"Clear logs failed: {e}"))
        self.window.overlay.show_confirm("Clear logs", "Delete all system logs?", _do_clear, yes_text="Clear", no_text="Cancel")

    def on_add_drug(self):
        def _save(name: str, code: str, reorder: int):
            if name:
                self.repo_drug.create(name, code, reorder); self.conn.commit(); self.refresh_drugs(); self.refresh_inventory()
        self.window.overlay.show_drug_form("Add drug", "", "", 0, _save)

    def on_edit_drug(self):
        ip = self.window.page_inventory; drug_id = ip.selected_drug_id()
        if drug_id is None: return
        d = self.repo_drug.get(int(drug_id))
        if d is None: return
        def _save(name: str, code: str, reorder: int):
            if name:
                self.repo_drug.update(int(drug_id), name, code, reorder, is_archived=False); self.conn.commit(); self.refresh_drugs(); self.refresh_inventory()
        self.window.overlay.show_drug_form("Edit drug", str(d["name"]), str(d["code"] or ""), int(d["reorder_level"] or 0), _save)

    def on_archive_drug(self):
        ip = self.window.page_inventory; drug_id = ip.selected_drug_id()
        if drug_id is None: return
        d = self.repo_drug.get(int(drug_id))
        if d is None: return
        def _do_archive():
            self.repo_drug.update(int(drug_id), str(d["name"]), str(d["code"] or ""), int(d["reorder_level"] or 0), is_archived=True); self.conn.commit(); self.refresh_drugs(); self.refresh_inventory()
        self.window.overlay.show_confirm("Archive drug", f"Archive {d['name']}?", _do_archive, yes_text="Archive", no_text="Cancel")

    def on_browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Select model (.pth)", "", "PyTorch model (*.pth)")
        if path: self.window.page_settings.ed_model_path.setText(path)

    def on_browse_onnx_model(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Select model (.onnx)", "", "ONNX model (*.onnx)")
        if path: self.window.page_settings.ed_onnx_path.setText(path)

    @pyqtSlot()
    def on_full_screen(self):
        self.window.show_app_full_screen()
        self.bus.publish(AppEvent(AppEventType.LOG, "app", "Switched to full screen"))

    @pyqtSlot()
    def on_windowed(self):
        self.window.show_app_windowed()
        self.bus.publish(AppEvent(AppEventType.LOG, "app", "Switched to 1024x600 windowed mode"))

    @pyqtSlot()
    def on_quit_app(self):
        self.bus.publish(AppEvent(AppEventType.LOG, "app", "Quit app requested"))
        QApplication.quit()

    def on_save_settings(self):
        sp = self.window.page_settings
        self.cfg.camera.device_index = int(sp.sp_cam_idx.value()); self.cfg.camera.width = int(sp.sp_cam_w.value()); self.cfg.camera.height = int(sp.sp_cam_h.value()); self.cfg.camera.fps = int(sp.sp_cam_fps.value())
        arch = sp.ed_model_arch.currentText().strip()
        profile = self._postprocess_profile_from_settings()
        self.cfg.model.runtime = sp.cb_runtime.currentText().strip().lower()
        self.cfg.model.model_path = sp.ed_model_path.text().strip()
        self.cfg.model.onnx_model_path = sp.ed_onnx_path.text().strip()
        self.cfg.model.model_arch = arch
        self.cfg.model.update_postprocess_profile(arch, profile)
        self.cfg.model.set_postprocess_dict(profile)
        self._settings_arch = arch
        self.cfg.share.enable_qr_share = bool(sp.chk_share.isChecked()); self.cfg.share.port = int(sp.sp_share_port.value()); self.cfg.share.token_required = bool(sp.chk_token.isChecked()); self.cfg.share.bind_all = True
        self.cfg.cloudflare.enabled = bool(sp.chk_tunnel.isChecked()); self.cfg.cloudflare.cloudflared_path = sp.ed_cloudflared.text().strip() or "cloudflared"; self.cfg.cloudflare.auto_start = bool(sp.chk_tunnel.isChecked())
        self.cfg.serial.enabled = False; self.cfg.serial.stream_weight = False
        self.cfg.save("config.json")
        self._apply_model_settings_to_infer()
        if self.cfg.share.enable_qr_share: self.start_share_server()
        else: self.stop_share_server()
        if self.cfg.share.enable_qr_share and self.cfg.cloudflare.enabled: self.start_tunnel()
        else: self.stop_tunnel()
        self.bus.publish(AppEvent(AppEventType.LOG, "app", "Settings saved. Restart app to fully apply camera resolution/index changes."))

    def start_share_server(self):
        host = "0.0.0.0" if self.cfg.share.bind_all else "127.0.0.1"
        self.flask_worker.configure(host, int(self.cfg.share.port), bool(self.cfg.share.token_required), self._share_token)
        self.flask_worker.start()

    def stop_share_server(self): self.flask_worker.stop()

    def start_tunnel(self):
        self.tunnel_worker.configure(self.cfg.cloudflare.cloudflared_path, int(self.cfg.share.port)); self.tunnel_worker.start()

    def stop_tunnel(self): self.tunnel_worker.stop()
