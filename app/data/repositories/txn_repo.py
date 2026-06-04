from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional


class TransactionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        ts: str,
        user_name: str,
        drug_id: Optional[int],
        op_type: str,
        predicted_count: int,
        expected_count: Optional[int],
        delta: Optional[int],
        weight_value: Optional[float],
        weight_stable: Optional[bool],
        notes: str,
        raw_path: str,
        overlay_path: str,
        report_md_path: str,
        report_pdf_path: str,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO transactions(ts,user_name,drug_id,op_type,predicted_count,expected_count,delta,"
            "weight_value,weight_stable,notes,raw_path,overlay_path,report_md_path,report_pdf_path) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ts, user_name, drug_id, op_type, int(predicted_count),
                expected_count, delta,
                weight_value, 1 if weight_stable else 0 if weight_stable is not None else None,
                notes, raw_path, overlay_path, report_md_path, report_pdf_path
            ),
        )
        return int(cur.lastrowid)

    def list_recent(self, limit: int = 50) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT t.*, d.name as drug_name, d.code as drug_code "
            "FROM transactions t LEFT JOIN drugs d ON d.id=t.drug_id "
            "ORDER BY t.id DESC LIMIT ?",
            (int(limit),),
        )
        return cur.fetchall()

    def list_filtered(self, drug_id: Optional[int] = None, op_type: Optional[str] = None, limit: int = 200) -> List[sqlite3.Row]:
        where = []
        params = []
        if drug_id is not None:
            where.append("t.drug_id=?")
            params.append(int(drug_id))
        if op_type:
            where.append("t.op_type=?")
            params.append(op_type)
        sql = (
            "SELECT t.*, d.name as drug_name, d.code as drug_code "
            "FROM transactions t LEFT JOIN drugs d ON d.id=t.drug_id "
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY t.id DESC LIMIT ?"
        params.append(int(limit))
        cur = self.conn.execute(sql, tuple(params))
        return cur.fetchall()

    def get_by_id(self, txn_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT t.*, d.name as drug_name, d.code as drug_code "
            "FROM transactions t LEFT JOIN drugs d ON d.id=t.drug_id WHERE t.id=?",
            (int(txn_id),),
        )
        return cur.fetchone()

    def delete(self, txn_id: int) -> None:
        self.conn.execute("DELETE FROM transactions WHERE id=?", (int(txn_id),))

    def search(self, q: str, limit: int = 200) -> List[sqlite3.Row]:
        q = (q or "").strip()
        if not q:
            return self.list_recent(limit=limit)
        like = f"%{q}%"
        cur = self.conn.execute(
            "SELECT t.*, d.name as drug_name, d.code as drug_code "
            "FROM transactions t LEFT JOIN drugs d ON d.id=t.drug_id "
            "WHERE CAST(t.id AS TEXT) LIKE ? OR t.user_name LIKE ? OR t.op_type LIKE ? OR t.ts LIKE ? "
            "OR d.name LIKE ? OR d.code LIKE ? "
            "ORDER BY t.id DESC LIMIT ?",
            (like, like, like, like, like, like, int(limit)),
        )
        return cur.fetchall()
