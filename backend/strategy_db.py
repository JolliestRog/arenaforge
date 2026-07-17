import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

STRATEGY_DB_PATH = Path(__file__).parent / "strategy_data" / "strategy.db"

_conn: sqlite3.Connection | None = None


def init():
    global _conn
    if STRATEGY_DB_PATH.exists():
        # immutable=1 lets SQLite skip WAL/lock files — safe on read-only mounts
        uri = f"file://{STRATEGY_DB_PATH}?immutable=1"
        _conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        _conn.row_factory = sqlite3.Row


def close():
    global _conn
    if _conn:
        _conn.close()
        _conn = None


@contextmanager
def get_strategy_db() -> Generator[sqlite3.Connection | None, None, None]:
    yield _conn  # None if not available — callers must handle


def is_available() -> bool:
    return _conn is not None


def fetch_commander_strategies(commander_name: str) -> list[dict]:
    """Return available strategies for a commander, ordered by fit_score desc."""
    if _conn is None:
        return []
    rows = _conn.execute(
        """
        SELECT cs.strategy_template_id AS id,
               st.display_name,
               cs.fit_score,
               cs.status,
               st.macro_plan,
               st.description
        FROM commander_strategies cs
        JOIN cards c  ON c.oracle_id  = cs.commander_oracle_id
        JOIN strategy_templates st ON st.id = cs.strategy_template_id
        WHERE c.name = ?
          AND cs.status IN ('recommended', 'viable', 'experimental')
        ORDER BY cs.fit_score DESC
        """,
        (commander_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_strategy_card_weights(commander_name: str, strategy_id: str) -> dict[str, float]:
    """Return {card_name: card_weight} for a commander+strategy pair (non-lands only)."""
    if _conn is None:
        return {}
    rows = _conn.execute(
        """
        SELECT cc.name AS card_name, csc.card_weight
        FROM commander_strategy_cards csc
        JOIN cards cmdr ON cmdr.oracle_id = csc.commander_oracle_id
        JOIN cards cc   ON cc.oracle_id   = csc.card_oracle_id
        WHERE cmdr.name = ?
          AND csc.strategy_template_id = ?
          AND cc.is_land = 0
        ORDER BY csc.card_weight DESC
        """,
        (commander_name, strategy_id),
    ).fetchall()
    return {r["card_name"]: r["card_weight"] for r in rows}


def fetch_strategy_role_targets(strategy_id: str) -> list[dict]:
    """Return role target rows for a strategy template."""
    if _conn is None:
        return []
    rows = _conn.execute(
        """
        SELECT role, min_count, preferred_count, weight
        FROM strategy_role_targets
        WHERE strategy_template_id = ?
        ORDER BY weight DESC
        """,
        (strategy_id,),
    ).fetchall()
    return [dict(r) for r in rows]
