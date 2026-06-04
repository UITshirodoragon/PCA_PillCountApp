from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class InventoryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_on_hand(self, drug_id: int) -> int:
        cur = self.conn.execute("SELECT on_hand FROM inventory_snapshot WHERE drug_id=?", (int(drug_id),))
        row = cur.fetchone()
        return int(row["on_hand"]) if row else 0

    def set_on_hand(self, drug_id: int, on_hand: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO inventory_snapshot(drug_id,on_hand,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(drug_id) DO UPDATE SET on_hand=excluded.on_hand, updated_at=excluded.updated_at",
            (int(drug_id), int(on_hand), now),
        )

    def apply_delta(self, drug_id: int, delta: int) -> int:
        current = self.get_on_hand(drug_id)
        newv = current + int(delta)
        if newv < 0:
            newv = 0
        self.set_on_hand(drug_id, newv)
        return newv

    def list_with_drugs(self) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT d.id, d.name, d.code, d.reorder_level, d.updated_at, "
            "COALESCE(s.on_hand,0) as on_hand "
            "FROM drugs d LEFT JOIN inventory_snapshot s ON s.drug_id=d.id "
            "WHERE d.is_archived=0 "
            "ORDER BY d.name COLLATE NOCASE"
        )
        return cur.fetchall()
