from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List


class LogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, level: str, source: str, message: str) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO system_logs(ts, level, source, message) VALUES(?,?,?,?)",
            (ts, level, source, message),
        )

    def list_recent(self, limit: int = 200) -> List[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (int(limit),))
        return cur.fetchall()

    def clear_all(self) -> None:
        self.conn.execute("DELETE FROM system_logs")
