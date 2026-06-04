from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QLibraryInfo
from PyQt6.QtWidgets import QApplication

from app.core.config import AppConfig
from app.core.logger import setup_logging
from app.ui.main_window import MainWindow
from app.presenters.main_presenter import MainPresenter

# Make PyQt plugin path explicit on Raspberry Pi / venv installs.
os.environ["QT_PLUGIN_PATH"] = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
# Use the app-owned keyboard. Native Qt virtual keyboard is disabled to avoid focus conflicts.
os.environ["QT_IM_MODULE"] = ""
os.environ["QT_VIRTUALKEYBOARD_DESKTOP_DISABLE"] = "1"


def main():
    cfg = AppConfig.load("config.json")
    setup_logging(cfg.storage.logs_dir)
    app = QApplication(sys.argv)
    win = MainWindow(qss_path="resources/styles/app.qss")
    presenter = MainPresenter(win, cfg)
    win.showFullScreen()

    def _shutdown():
        try:
            presenter.shutdown()
        except Exception:
            pass
    app.aboutToQuit.connect(_shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
