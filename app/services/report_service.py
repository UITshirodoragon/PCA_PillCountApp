from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


@dataclass
class ReportInfo:
    txn_id: int
    ts: str
    user_name: str
    drug_name: str
    drug_code: str
    op_type: str
    predicted_count: int
    expected_count: Optional[int]
    delta: Optional[int]
    weight_value: Optional[float]
    weight_stable: Optional[bool]
    notes: str
    raw_path: str
    overlay_path: str


class ReportService:
    def __init__(self, reports_root: str):
        self.reports_root = reports_root

    def txn_folder(self, ts: datetime, txn_id: int) -> str:
        day = ts.strftime("%Y%m%d")
        folder = os.path.join(self.reports_root, day, f"txn_{txn_id:06d}")
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder

    def write_markdown(self, folder: str, info: ReportInfo) -> str:
        md_path = os.path.join(folder, "report.md")
        lines = []
        lines.append(f"# Pill Counter Report")
        lines.append("")
        lines.append(f"- Transaction ID: **{info.txn_id}**")
        lines.append(f"- Timestamp: {info.ts}")
        lines.append(f"- User: {info.user_name}")
        lines.append(f"- Drug: {info.drug_name} ({info.drug_code})")
        lines.append(f"- Operation: {info.op_type}")
        lines.append(f"- Predicted count: {info.predicted_count}")
        if info.expected_count is not None:
            lines.append(f"- Expected: {info.expected_count} (delta={info.delta})")
        if info.weight_value is not None:
            lines.append(f"- Weight(g): {info.weight_value:.2f} (stable={bool(info.weight_stable)})")
        if info.notes:
            lines.append(f"- Notes: {info.notes}")
        lines.append("")
        lines.append("## Images")
        lines.append(f"- Raw: {os.path.basename(info.raw_path)}")
        lines.append(f"- Overlay: {os.path.basename(info.overlay_path)}")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return md_path

    def write_pdf(self, folder: str, info: ReportInfo) -> str:
        pdf_path = os.path.join(folder, "report.pdf")
        c = canvas.Canvas(pdf_path, pagesize=A4)
        w, h = A4
        y = h - 48

        def line(txt: str, size: int = 12):
            nonlocal y
            c.setFont("Helvetica", size)
            c.drawString(48, y, txt)
            y -= (size + 8)

        line("Pill Counter Report", 18)
        line(f"Transaction ID: {info.txn_id}")
        line(f"Timestamp: {info.ts}")
        line(f"User: {info.user_name}")
        line(f"Drug: {info.drug_name} ({info.drug_code})")
        line(f"Operation: {info.op_type}")
        line(f"Predicted count: {info.predicted_count}")
        if info.expected_count is not None:
            line(f"Expected: {info.expected_count} (delta={info.delta})")
        if info.weight_value is not None:
            line(f"Weight(g): {info.weight_value:.2f} (stable={bool(info.weight_stable)})")
        if info.notes:
            line("Notes:", 12)
            for chunk in _wrap(info.notes, 70):
                line(chunk, 11)

        # Images embedded (raw, overlay, qr)
        y -= 8
        c.setFont("Helvetica", 12)
        c.drawString(48, y, "Images:")
        y -= 18

        def _draw_img(path: str, x: float, y_top: float, max_w: float, max_h: float) -> float:
            if not path or not os.path.exists(path):
                c.setFont("Helvetica", 10)
                c.drawString(x, y_top, f"(missing) {os.path.basename(path) if path else ''}")
                return 0.0
            try:
                img = ImageReader(path)
                iw, ih = img.getSize()
                if iw <= 0 or ih <= 0:
                    return 0.0
                scale = min(max_w / iw, max_h / ih)
                dw, dh = iw * scale, ih * scale
                c.drawImage(img, x, y_top - dh, width=dw, height=dh, preserveAspectRatio=True, mask='auto')
                return dh
            except Exception:
                c.setFont("Helvetica", 10)
                c.drawString(x, y_top, f"(failed) {os.path.basename(path)}")
                return 0.0

        # Layout: raw + overlay side-by-side, qr on right/below depending on space
        margin_x = 48
        gap = 16
        img_w = (w - 2 * margin_x - gap) / 2.0
        img_h = 240

        y_top = y
        dh1 = _draw_img(info.raw_path, margin_x, y_top, img_w, img_h)
        dh2 = _draw_img(info.overlay_path, margin_x + img_w + gap, y_top, img_w, img_h)
        y = y_top - max(dh1, dh2) - 14

        qr_path = os.path.join(folder, "qr.png")
        if os.path.exists(qr_path):
            c.setFont("Helvetica", 11)
            c.drawString(margin_x, y, "QR code:")
            y -= 12
            _draw_img(qr_path, margin_x, y, 160, 160)

        c.showPage()
        c.save()
        return pdf_path


def _wrap(s: str, n: int):
    s = s or ""
    out = []
    cur = ""
    for word in s.split():
        if len(cur) + len(word) + 1 > n:
            out.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        out.append(cur)
    return out
