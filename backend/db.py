import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).parent / "data" / "cards.db"

_conn: sqlite3.Connection | None = None


def init():
    global _conn
    _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA query_only=ON")


def close():
    global _conn
    if _conn:
        _conn.close()
        _conn = None


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    if _conn is None:
        raise RuntimeError("Database not initialized")
    yield _conn
