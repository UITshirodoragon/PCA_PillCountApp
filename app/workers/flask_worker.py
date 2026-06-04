from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from flask import Flask, send_from_directory, abort, request
from werkzeug.serving import make_server

from app.core.bus import MessageBus
from app.core.types import AppEvent, AppEventType

log = logging.getLogger("flask_worker")


def _safe_join(root: str, subpath: str) -> tuple[str, str]:
    root_p = Path(root).resolve()
    target = (root_p / subpath).resolve()
    if root_p not in target.parents and target != root_p:
        raise ValueError("Path traversal blocked")
    return str(target.parent), target.name


def _create_app(reports_root: str, token_required: bool = True, token: str = "") -> Flask:
    app = Flask(__name__)
    reports_root = os.path.abspath(reports_root)
    token = token or ""

    def _authorized() -> bool:
        if not token_required:
            return True
        return bool(token) and request.args.get("token", "") == token

    @app.get("/")
    def index():
        if token_required:
            return "<html><body><h2>Pill Counter Share</h2><p>Direct report token required.</p></body></html>"
        items = []
        for dirpath, dirnames, filenames in os.walk(reports_root):
            if "report.pdf" in filenames:
                rel = os.path.relpath(dirpath, reports_root)
                items.append(rel.replace("\\", "/"))
        items = sorted(items, reverse=True)[:30]
        html = ["<html><head><meta charset='utf-8'><title>Pill Counter Reports</title></head><body>"]
        html.append("<h2>Pill Counter Reports</h2>")
        if not items:
            html.append("<p>No reports found.</p>")
        else:
            html.append("<ul>")
            for rel in items:
                html.append(f"<li><a href='/reports/{rel}/report.pdf'>{rel}/report.pdf</a></li>")
            html.append("</ul>")
        html.append("</body></html>")
        return "\n".join(html)

    @app.get("/reports/<path:subpath>")
    def reports(subpath: str):
        if not _authorized():
            abort(403)
        try:
            full_dir, fname = _safe_join(reports_root, subpath)
        except ValueError:
            abort(403)
        if not os.path.exists(os.path.join(full_dir, fname)):
            abort(404)
        return send_from_directory(full_dir, fname, as_attachment=False)

    return app


class FlaskWorker(QObject):
    status = pyqtSignal(str)  # base_url

    def __init__(self, bus: MessageBus, reports_root: str):
        super().__init__()
        self.bus = bus
        self.reports_root = reports_root
        self._srv = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._host = "127.0.0.1"
        self._port = 5000
        self._token_required = True
        self._token = ""

    @pyqtSlot(str, int)
    def configure(self, host: str, port: int, token_required: bool = True, token: str = ""):
        self._host = host
        self._port = int(port)
        self._token_required = bool(token_required)
        self._token = token or ""

    @pyqtSlot()
    def start(self):
        if self._running:
            return
        self._running = True
        app = _create_app(self.reports_root, self._token_required, self._token)
        try:
            self._srv = make_server(self._host, self._port, app, threaded=True)
        except Exception as e:
            self.bus.publish(AppEvent(AppEventType.ERROR, "share", f"Cannot start server: {e}"))
            self._running = False
            return

        def _run():
            log.info("Share server at http://%s:%d", self._host, self._port)
            self.bus.publish(AppEvent(AppEventType.FLASK_STATUS, "share", "running"))
            self._srv.serve_forever()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self.status.emit(f"http://{self._host}:{self._port}")

    @pyqtSlot()
    def stop(self):
        if not self._running:
            return
        self._running = False
        try:
            if self._srv is not None:
                self._srv.shutdown()
        except Exception:
            pass
        self._srv = None
        self.status.emit("")
        self.bus.publish(AppEvent(AppEventType.FLASK_STATUS, "share", "stopped"))
