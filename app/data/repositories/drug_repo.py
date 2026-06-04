from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple


class DrugRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_active(self) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT * FROM drugs WHERE is_archived=0 ORDER BY name COLLATE NOCASE"
        )
        return cur.fetchall()

    def list_all(self) -> List[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM drugs ORDER BY name COLLATE NOCASE")
        return cur.fetchall()

    def create(self, name: str, code: str = "", reorder_level: int = 0) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "INSERT INTO drugs(name, code, reorder_level, is_archived, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (name, code, int(reorder_level), 0, now, now),
        )
        return int(cur.lastrowid)

    def update(self, drug_id: int, name: str, code: str = "", reorder_level: int = 0, is_archived: bool = False) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE drugs SET name=?, code=?, reorder_level=?, is_archived=?, updated_at=? WHERE id=?",
            (name, code, int(reorder_level), 1 if is_archived else 0, now, int(drug_id)),
        )

    def archive(self, drug_id: int) -> None:
        self.update(drug_id, name=self.get(drug_id)["name"], code=self.get(drug_id)["code"], reorder_level=self.get(drug_id)["reorder_level"], is_archived=True)

    def get(self, drug_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM drugs WHERE id=?", (int(drug_id),))
        return cur.fetchone()
