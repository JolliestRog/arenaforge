"""ArenaForge strategy pipeline CLI.

Usage:
    python -m strategy.run [--db path] [--reset] [--source auto|json|db]

The pipeline is fully deterministic: given the same schema.sql, rules,
templates, and card data, it produces identical weights.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sqlite3
from pathlib import Path

from .migrate import DEFAULT_DB, apply_schema, connect, reset
from .pipeline.cards import build_commander_strategy_cards, classify_all_cards
from .pipeline.classify import classify_all_commanders, seed_tag_catalog
from .pipeline.ingest import load_cards
from .pipeline.strategies import score_all_commanders, seed_templates
from .rules.signals import SIGNAL_RULE_VERSION
from .rules.templates import TEMPLATE_VERSION

PIPELINE_VERSION = "0.1.0"

HERE = Path(__file__).resolve().parent
BACKEND_DATA = HERE.parent / "backend" / "data"
DEFAULT_JSON = BACKEND_DATA / "oracle_cards.json"
DEFAULT_CARDS_DB = BACKEND_DATA / "cards.db"


def _scryfall_snapshot() -> str:
    meta = BACKEND_DATA / "oracle_meta.json"
    if meta.exists():
        try:
            import json
            return json.loads(meta.read_text()).get("updated_at", "unknown")
        except Exception:
            return "unknown"
    return "unknown"


def run_pipeline(
    db_path: Path,
    do_reset: bool,
    source: str = "auto",
    *,
    scryfall_json: Path | None = None,
    cards_db_path: Path | None = None,
) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log = logging.getLogger("strategy.run")

    conn = connect(db_path)
    if do_reset:
        reset(conn)
    else:
        apply_schema(conn)

    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    seed_tag_catalog(conn)
    seed_templates(conn)

    scryfall = (scryfall_json or DEFAULT_JSON) if source in ("auto", "json") else None
    cards_db = (cards_db_path or DEFAULT_CARDS_DB) if source in ("auto", "db") else None
    if source == "json":
        cards_db = None
    if source == "db":
        scryfall = None
    card_count, source_label = load_cards(conn, scryfall, cards_db)
    log.info("ingested %d cards from %s", card_count, source_label)

    commander_count = classify_all_commanders(conn)
    log.info("classified %d commanders", commander_count)

    role_rows = classify_all_cards(conn)
    log.info("classified %d cards' roles", role_rows)

    score_all_commanders(conn)

    pair_count = build_commander_strategy_cards(conn)

    finished = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    with conn:
        conn.execute(
            "INSERT INTO build_metadata"
            " (pipeline_version, signal_rule_version, template_version,"
            "  scryfall_snapshot, run_started_at, run_finished_at,"
            "  card_count, commander_count, strategy_pair_count)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (PIPELINE_VERSION, SIGNAL_RULE_VERSION, TEMPLATE_VERSION,
             _scryfall_snapshot(), started, finished,
             card_count, commander_count, pair_count),
        )

    accepted = conn.execute(
        "SELECT COUNT(*) FROM commander_strategies "
        "WHERE status IN ('recommended', 'viable')"
    ).fetchone()[0]

    summary = {
        "db":                 str(db_path),
        "pipeline_version":   PIPELINE_VERSION,
        "signal_version":     SIGNAL_RULE_VERSION,
        "template_version":   TEMPLATE_VERSION,
        "cards":              card_count,
        "commanders":         commander_count,
        "accepted_strategies": accepted,
        "card_weights":       pair_count,
        "source":             source_label,
    }
    log.info("pipeline summary: %s", summary)
    conn.close()
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--source", choices=["auto", "json", "db"], default="auto")
    args = ap.parse_args()
    run_pipeline(args.db, args.reset, args.source)


if __name__ == "__main__":
    main()
