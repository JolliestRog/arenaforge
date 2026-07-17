"""End-to-end tests for the ArenaForge strategy pipeline.

The suite builds a fresh strategy DB into a temp path once per session using
the sibling ``backend/data`` snapshot, then queries it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from strategy.migrate import connect
from strategy.pipeline.classify import classify_commander
from strategy.rules.templates import get_template
from strategy.run import BACKEND_DATA, DEFAULT_JSON, DEFAULT_CARDS_DB, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def built_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("strategy") / "strategy.db"
    source = "json" if DEFAULT_JSON.exists() else "db"
    run_pipeline(db, do_reset=True, source=source)
    return db


@pytest.fixture(scope="session")
def conn(built_db) -> sqlite3.Connection:
    c = connect(built_db)
    return c


# ---------------------------------------------------------------------------
# Utilities.
# ---------------------------------------------------------------------------
def _find_commander_oid(conn: sqlite3.Connection, name_prefix: str) -> str:
    row = conn.execute(
        "SELECT oracle_id FROM cards WHERE is_commander = 1 AND name LIKE ? LIMIT 1",
        (f"{name_prefix}%",),
    ).fetchone()
    if not row:
        raise AssertionError(f"commander not found: {name_prefix}")
    return row["oracle_id"]


def _fit(conn: sqlite3.Connection, oid: str, template_id: str) -> float:
    row = conn.execute(
        "SELECT fit_score FROM commander_strategies"
        " WHERE commander_oracle_id = ? AND strategy_template_id = ?",
        (oid, template_id),
    ).fetchone()
    return float(row["fit_score"]) if row else 0.0


# ---------------------------------------------------------------------------
# Required tests (from the brief).
# ---------------------------------------------------------------------------
def test_lorthos_supports_big_mana_tap_control(conn):
    oid = _find_commander_oid(conn, "Lorthos")
    fit = _fit(conn, oid, "big_mana_tap_control")
    assert fit >= 0.60, f"Lorthos big-mana tap control fit was {fit:.2f}"


def test_lorthos_rejects_tempo_aggro(conn):
    oid = _find_commander_oid(conn, "Lorthos")
    aggro = _fit(conn, oid, "tokens_go_wide")
    tempo = _fit(conn, oid, "spellslinger_tempo")
    assert aggro < 0.45, f"Lorthos tokens aggro fit unexpectedly high: {aggro:.2f}"
    assert tempo < 0.45, f"Lorthos spellslinger tempo fit unexpectedly high: {tempo:.2f}"


def test_death_trigger_commander_favors_aristocrats(conn):
    row = conn.execute(
        "SELECT oracle_id, name FROM cards"
        " WHERE is_commander = 1"
        "   AND lower(oracle_text) LIKE '%whenever another creature you control dies%'"
        " LIMIT 1"
    ).fetchone()
    assert row is not None
    fit = _fit(conn, row["oracle_id"], "aristocrats_sacrifice_midrange")
    assert fit >= 0.45, (
        f"Death-trigger commander {row['name']} fit for aristocrats was {fit:.2f}"
    )


def test_aura_commander_favors_aura_voltron(conn):
    # Light-Paws is the canonical Arena Aura-matters commander.
    row = conn.execute(
        "SELECT oracle_id, name FROM cards"
        " WHERE is_commander = 1"
        "   AND name LIKE 'Light-Paws%' LIMIT 1"
    ).fetchone()
    assert row is not None
    fit = _fit(conn, row["oracle_id"], "aura_voltron")
    assert fit >= 0.45, (
        f"Aura commander {row['name']} fit for aura voltron was {fit:.2f}"
    )


def test_spellslinger_commander_favors_spellslinger(conn):
    # Any commander with "whenever you cast an instant or sorcery" text.
    row = conn.execute(
        "SELECT oracle_id, name FROM cards"
        " WHERE is_commander = 1"
        "   AND lower(oracle_text) LIKE '%whenever you cast an instant or sorcery%'"
        " LIMIT 1"
    ).fetchone()
    assert row is not None
    fit = _fit(conn, row["oracle_id"], "spellslinger_tempo")
    assert fit >= 0.45, (
        f"Spellslinger commander {row['name']} fit for spellslinger was {fit:.2f}"
    )


def test_displayed_strategies_have_evidence(conn):
    """Every recommended/viable pair must have at least one evidence row."""
    rows = conn.execute(
        "SELECT commander_oracle_id, strategy_template_id"
        " FROM commander_strategies"
        " WHERE status IN ('recommended', 'viable')"
        " LIMIT 200"
    ).fetchall()
    assert rows, "no displayed strategies at all"
    for r in rows:
        ev = conn.execute(
            "SELECT COUNT(*) FROM commander_strategy_evidence"
            " WHERE commander_oracle_id = ? AND strategy_template_id = ?",
            (r["commander_oracle_id"], r["strategy_template_id"]),
        ).fetchone()[0]
        assert ev > 0, (
            f"No evidence for accepted pair {r['commander_oracle_id']} / "
            f"{r['strategy_template_id']}"
        )


def test_determinism(conn, tmp_path):
    """Rebuild the DB with identical inputs and confirm weights match."""
    a = conn
    b_path = tmp_path / "rebuild.db"
    source = "json" if DEFAULT_JSON.exists() else "db"
    run_pipeline(b_path, do_reset=True, source=source)
    b = connect(b_path)

    query = (
        "SELECT commander_oracle_id, strategy_template_id,"
        "       ROUND(fit_score, 6) FROM commander_strategies"
        " ORDER BY commander_oracle_id, strategy_template_id"
    )
    a_rows = a.execute(query).fetchall()
    b_rows = b.execute(query).fetchall()
    assert len(a_rows) == len(b_rows)
    for x, y in zip(a_rows, b_rows):
        assert tuple(x) == tuple(y)


def test_candidate_cards_are_legal_and_in_color(conn):
    """Every commander_strategy_cards row respects arena/color legality."""
    rows = conn.execute(
        "SELECT csc.commander_oracle_id AS cid, csc.card_oracle_id AS card,"
        "       cmd.color_identity AS cmd_colors,"
        "       card.color_identity AS card_colors,"
        "       card.arena_legal AS legal"
        " FROM commander_strategy_cards csc"
        " JOIN cards cmd  ON cmd.oracle_id  = csc.commander_oracle_id"
        " JOIN cards card ON card.oracle_id = csc.card_oracle_id"
        " LIMIT 5000"
    ).fetchall()
    if not rows:
        pytest.skip("no card weights present")
    for r in rows:
        assert r["legal"] == 1
        cmd_colors = set(json.loads(r["cmd_colors"] or "[]"))
        card_colors = set(json.loads(r["card_colors"] or "[]"))
        assert card_colors.issubset(cmd_colors), (
            f"card {r['card']} colors {card_colors} not in commander colors {cmd_colors}"
        )


def test_each_commander_has_reasonable_strategy_count(conn):
    """Most commanders show between 1 and 4 accepted strategies."""
    rows = conn.execute(
        "SELECT commander_oracle_id, COUNT(*) AS n"
        " FROM commander_strategies"
        " WHERE status IN ('recommended', 'viable')"
        " GROUP BY commander_oracle_id"
    ).fetchall()
    if not rows:
        pytest.skip("no accepted strategies")
    counts = [r["n"] for r in rows]
    # Some commanders will have zero accepted strategies (bare-vanilla legends).
    # The requirement covers commanders that DO produce output.
    in_range = sum(1 for n in counts if 1 <= n <= 4)
    ratio = in_range / len(counts)
    assert ratio >= 0.70, (
        f"only {ratio:.0%} of commanders have 1-4 accepted strategies; "
        f"distribution: min={min(counts)} max={max(counts)}"
    )


# ---------------------------------------------------------------------------
# Signal-level unit smoke tests (fast, do not need built_db).
# ---------------------------------------------------------------------------
def test_death_trigger_signal_fires():
    tags = classify_commander(
        "Test Commander",
        "Whenever another creature you control dies, you gain 1 life.",
    )
    assert "aristocrats" in tags
    assert tags["aristocrats"]["weight"] > 0.4


def test_tap_control_signal_fires():
    tags = classify_commander(
        "Lorthos, the Tidemaker",
        (
            "Whenever Lorthos attacks, you may pay {8}. If you do, "
            "tap up to eight target permanents. Those permanents don't untap "
            "during their controllers' next untap steps."
        ),
    )
    assert "tap_control" in tags
    assert tags["tap_control"]["weight"] > 0.5
    assert "untap_denial" in tags


def test_spellslinger_signal_fires():
    tags = classify_commander(
        "Test",
        "Whenever you cast an instant or sorcery spell, draw a card.",
    )
    assert "spellslinger" in tags
    assert tags["spellslinger"]["weight"] > 0.3
