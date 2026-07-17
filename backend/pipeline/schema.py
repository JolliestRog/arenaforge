"""SQLite schema for the ArenaForge card database."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "cards.db"

DDL = """
CREATE TABLE IF NOT EXISTS cards (
    name            TEXT PRIMARY KEY,
    mana_cost       TEXT,
    cmc             REAL NOT NULL DEFAULT 0,
    color_identity  TEXT NOT NULL DEFAULT '[]',   -- JSON array, e.g. ["U","B"]
    type_line       TEXT NOT NULL DEFAULT '',
    rarity          TEXT NOT NULL,                -- common/uncommon/rare/mythic
    oracle_text     TEXT NOT NULL DEFAULT '',
    keywords        TEXT NOT NULL DEFAULT '[]',   -- JSON array
    power           TEXT,
    toughness       TEXT,
    is_land         INTEGER NOT NULL DEFAULT 0,
    is_creature     INTEGER NOT NULL DEFAULT 0,
    is_legendary    INTEGER NOT NULL DEFAULT 0,
    is_commander    INTEGER NOT NULL DEFAULT 0    -- legendary creature or planeswalker w/ ability
);

CREATE INDEX IF NOT EXISTS idx_color_identity ON cards (color_identity);
CREATE INDEX IF NOT EXISTS idx_rarity ON cards (rarity);
CREATE INDEX IF NOT EXISTS idx_cmc ON cards (cmc);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(DDL)
    conn.commit()
    return conn
