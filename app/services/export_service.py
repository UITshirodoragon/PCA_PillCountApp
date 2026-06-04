from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Iterable


def export_rows_to_csv(headers: list[str], rows: Iterable[Iterable], out_path: str) -> str:
    Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(list(r))
    return out_path
