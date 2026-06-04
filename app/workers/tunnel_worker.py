from __future__ import annotations

import re
import shutil
from typing import Optional

from PyQt6.QtCore import QObject, QProcess, pyqtSignal, pyqtSlot

from app.core.bus import MessageBus
from app.core.types import AppEvent, AppEventType


class TunnelWorker(QObject):
    """Manage Cloudflare Quick Tunnel via cloudflared.

    This is intentionally defensive: if cloudflared is missing or the network is unavailable,
    the local counting workflow must continue normally.
    """

    status = pyqtSignal(str, str)  # state, public_url

    def __init__(self, bus: MessageBus, cloudflared_path: str = "cloudflared"):
        super().__init__()
        self.bus = bus
        self.cloudflared_path = cloudflared_path or "cloudflared"
        self._proc: Optional[QProcess] = None
        self._public_url = ""
        self._local_url = "http://127.0.0.1:5000"

    @pyqtSlot(str, int)
    def configure(self, cloudflared_path: str, local_port: int):
        self.cloudflared_path = cloudflared_path or "cloudflared"
        self._local_url = f"http://127.0.0.1:{int(local_port)}"

    @pyqtSlot()
    def start(self):
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            return

        program = self.cloudflared_path
        if shutil.which(program) is None and not program.startswith("/"):
            self.status.emit("Error", "")
            self.bus.publish(AppEvent(AppEventType.ERROR, "cloudflare", "cloudflared not found; install cloudflared or set path in Settings"))
            return

        self._public_url = ""
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_output)
        self._proc.finished.connect(self._finished)
        self._proc.start(program, ["tunnel", "--url", self._local_url, "--no-autoupdate"])
        self.status.emit("Starting", "")
        self.bus.publish(AppEvent(AppEventType.FLASK_STATUS, "cloudflare", "starting quick tunnel"))

    @pyqtSlot()
    def stop(self):
        if self._proc is None:
            self.status.emit("Off", "")
            return
        if self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
            if not self._proc.waitForFinished(1500):
                self._proc.kill()
        self._public_url = ""
        self.status.emit("Off", "")
        self.bus.publish(AppEvent(AppEventType.FLASK_STATUS, "cloudflare", "stopped"))

    def public_url(self) -> str:
        return self._public_url

    def _read_output(self):
        if self._proc is None:
            return
        text = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        m = re.search(r"https://[-a-zA-Z0-9.]+\.trycloudflare\.com", text)
        if m:
            self._public_url = m.group(0).rstrip("/")
            self.status.emit("Online", self._public_url)
            self.bus.publish(AppEvent(AppEventType.FLASK_STATUS, "cloudflare", f"online: {self._public_url}"))

    def _finished(self, *args):
        if self._public_url:
            self.bus.publish(AppEvent(AppEventType.FLASK_STATUS, "cloudflare", "tunnel exited"))
        self._public_url = ""
        self.status.emit("Off", "")
