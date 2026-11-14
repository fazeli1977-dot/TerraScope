# -*- coding: utf-8 -*-
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "data" / "database" / "terrascope.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM satellite_observations LIMIT 1")
row = cur.fetchone()
if row:
    print("[EO COLUMNS]:", list(dict(row).keys()))
    print("[SAMPLE ROW]:", dict(row))
conn.close()