from __future__ import annotations

import os
from pathlib import Path

import qrcode


def make_qr_png(text: str, out_path: str) -> str:
    Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)
    img = qrcode.make(text)
    img.save(out_path)
    return out_path
