from __future__ import annotations

import os
import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS drugs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  code TEXT DEFAULT '',
  reorder_level INTEGER DEFAULT 0,
  is_archived INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  user_name TEXT DEFAULT '',
  drug_id INTEGER,
  op_type TEXT NOT NULL,
  predicted_count INTEGER NOT NULL,
  expected_count INTEGER,
  delta INTEGER,
  weight_value REAL,
  weight_stable INTEGER,
  notes TEXT DEFAULT '',
  raw_path TEXT NOT NULL,
  overlay_path TEXT NOT NULL,
  report_md_path TEXT NOT NULL,
  report_pdf_path TEXT NOT NULL,
  FOREIGN KEY(drug_id) REFERENCES drugs(id)
);

CREATE TABLE IF NOT EXISTS inventory_snapshot (
  drug_id INTEGER PRIMARY KEY,
  on_hand INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(drug_id) REFERENCES drugs(id)
);

CREATE TABLE IF NOT EXISTS system_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,
  source TEXT NOT NULL,
  message TEXT NOT NULL
);
"""


def db_path(storage_root: str) -> str:
    Path(storage_root).mkdir(parents=True, exist_ok=True)
    return os.path.join(storage_root, "pill_counter.sqlite3")


def connect(storage_root: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(storage_root), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(storage_root: str) -> None:
    conn = connect(storage_root)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
