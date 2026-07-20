"""Required end-to-end coverage that runs without ignored runtime data."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ci_fixtures.cards import fixture_cards, write_snapshot


def _build_cards_db(snapshot: Path, db_path: Path) -> None:
    from pipeline.ingest import UPSERT, _card_to_row, _iter_hb_cards
    from pipeline.schema import init_db

    rows = [_card_to_row(card) for card in _iter_hb_cards(snapshot)]
    assert len(rows) >= 150
    conn = init_db(db_path)
    with conn:
        conn.executemany(UPSERT, rows)
    conn.close()


@pytest.fixture(scope="module")
def deterministic_databases(tmp_path_factory):
    root = tmp_path_factory.mktemp("clean-clone")
    snapshot = write_snapshot(root / "cards.json")
    cards_db = root / "cards.db"
    strategy_path = root / "strategy.db"
    _build_cards_db(snapshot, cards_db)

    from strategy.run import run_pipeline

    summary = run_pipeline(
        strategy_path,
        do_reset=True,
        source="json",
        scryfall_json=snapshot,
    )
    assert summary["cards"] >= 150
    assert summary["accepted_strategies"] > 0
    assert summary["card_weights"] > 0

    import db
    import strategy_db

    old_cards_path = db.DB_PATH
    old_strategy_path = strategy_db.STRATEGY_DB_PATH
    restore_live = db._conn is not None or strategy_db._conn is not None
    db.close()
    strategy_db.close()
    db.DB_PATH = cards_db
    strategy_db.STRATEGY_DB_PATH = strategy_path
    db.init()
    strategy_db.init()
    try:
        yield {"cards": cards_db, "strategy": strategy_path}
    finally:
        db.close()
        strategy_db.close()
        db.DB_PATH = old_cards_path
        strategy_db.STRATEGY_DB_PATH = old_strategy_path
        if restore_live and old_cards_path.exists():
            db.init()
            strategy_db.init()


def test_fixture_snapshot_is_deterministic(tmp_path):
    first = write_snapshot(tmp_path / "first.json")
    second = write_snapshot(tmp_path / "second.json")
    assert first.read_bytes() == second.read_bytes()
    assert len(fixture_cards()) == len({card["oracle_id"] for card in fixture_cards()})


def test_arena_alias_normalizes_without_live_data(deterministic_databases):
    from card_names import build_card_name_index, normalize_collection
    from db import get_db

    with get_db() as conn:
        cards = [dict(row) for row in conn.execute("SELECT * FROM cards")]
    owned, unmatched, copies = normalize_collection(
        [{"name": "A-Lantern Bearer", "count": 1}],
        build_card_name_index(cards),
    )
    assert "A-Lantern Bearer // A-Lanterns' Lift" in owned
    assert unmatched == []
    assert copies == 1


def test_collection_to_analysis_build_and_100_card_export(deterministic_databases):
    from routers.analyze_v2 import AnalyzeRequestV2, analyze_v2
    from routers.build import BuildRequest, WildcardBudget, build

    collection = [{"name": "Lorthos, the Tidemaker", "count": 1}]
    analysis = analyze_v2(AnalyzeRequestV2(
        collection=collection,
        strategy_filter="Control",
    ))
    recommendation = next(
        rec for rec in analysis.owned_recommendations
        if rec.name == "Lorthos, the Tidemaker"
    )
    assert recommendation.strategy_id == "big_mana_tap_control"

    variants = build(BuildRequest(
        collection=collection,
        commander=recommendation.name,
        profile=recommendation.strategy_id,
        wildcard_budget=WildcardBudget(),
    ))
    optimized = next(variant for variant in variants if variant.variant_key == "optimized")
    assert optimized.build_status in {"complete", "role_relaxed"}
    assert len(optimized.cards) == 99

    lines = optimized.arena_export.splitlines()
    assert lines[:2] == ["Commander", "1 Lorthos, the Tidemaker"]
    deck_index = lines.index("Deck")
    deck_count = sum(int(line.split(" ", 1)[0]) for line in lines[deck_index + 1:])
    assert deck_count == 99
    assert deck_count + 1 == 100
