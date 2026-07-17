"""Apply schema.sql to a SQLite database.

Usage:
    python -m strategy.migrate [--db path] [--reset]
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE / "data" / "strategy.db"
SCHEMA_PATH = HERE / "schema.sql"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    ddl = SCHEMA_PATH.read_text()
    with conn:
        conn.executescript(ddl)


def reset(conn: sqlite3.Connection) -> None:
    """Drop all pipeline-managed tables (keeps overrides)."""
    tables = [
        "commander_strategy_cards",
        "commander_strategy_evidence",
        "commander_strategies",
        "commander_tag_weights",
        "card_role_weights",
        "strategy_role_targets",
        "strategy_templates",
        "strategy_tags",
        "cards",
        "build_metadata",
    ]
    with conn:
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
    apply_schema(conn)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--reset", action="store_true", help="Drop and recreate tables")
    args = ap.parse_args()
    conn = connect(args.db)
    if args.reset:
        reset(conn)
        print(f"[migrate] reset + applied schema at {args.db}")
    else:
        apply_schema(conn)
        print(f"[migrate] applied schema at {args.db}")


if __name__ == "__main__":
    main()
