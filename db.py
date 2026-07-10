#!/usr/bin/env python3
"""SQLite-слой карты: схема + upsert с дедупом. Простой, без ORM (§1 минимум)."""

import sqlite3, hashlib, re
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id                 TEXT PRIMARY KEY,
    title              TEXT,
    authors            TEXT,
    date               TEXT,          -- YYYY-MM-DD | YYYY-MM | YYYY | NULL
    source_name        TEXT,
    category           TEXT,          -- A|B|C|D|E
    type               TEXT,
    area               TEXT,
    url                TEXT,
    summary            TEXT,
    breadth_score      INTEGER,       -- 0..5 (мастер-ворота)
    significance_score INTEGER,       -- 0..5
    tags               TEXT,          -- csv
    notes              TEXT,
    retrieved_at       TEXT
);
CREATE INDEX IF NOT EXISTS ix_cat  ON materials(category);
CREATE INDEX IF NOT EXISTS ix_area ON materials(area);
CREATE INDEX IF NOT EXISTS ix_date ON materials(date);
"""

def _norm_url(u):
    if not u:
        return ""
    u = u.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = re.sub(r"#.*$", "", u)          # снять фрагмент
    u = re.sub(r"\?.*$", "", u)         # снять query
    return u.rstrip("/")                # путь (в т.ч. полный DOI) сохраняем!

def dedup_key(row):
    """Ключ дедупа = нормализ.url + нормализ.title. Схлопываем только полные дубли
    (один материал из двух механизмов). Разные доклады с общим URL программы
    (Bourbaki) НЕ схлопываются — их различает title."""
    u = _norm_url(row.get("url"))
    t = re.sub(r"\W+", "", str(row.get("title", "")).lower())[:60]
    return f"{u}||{t}"

def make_id(row):
    """id = хэш ключа дедупа -> id уникален ровно там, где строка уникальна."""
    return hashlib.sha1(dedup_key(row).encode("utf-8")).hexdigest()[:16]

def connect():
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    return con

COLS = ["id","title","authors","date","source_name","category","type","area",
        "url","summary","breadth_score","significance_score","tags","notes","retrieved_at"]

def upsert_many(con, rows):
    """INSERT OR REPLACE по id. rows — list of dict с ключами COLS."""
    payload = []
    for r in rows:
        payload.append(tuple(r.get(c) for c in COLS))
    con.executemany(
        f"INSERT OR REPLACE INTO materials ({','.join(COLS)}) VALUES ({','.join(['?']*len(COLS))})",
        payload)
    con.commit()
    return len(payload)

def count(con):
    return con.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
