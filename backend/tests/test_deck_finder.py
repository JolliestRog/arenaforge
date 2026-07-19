"""Needle-in-a-random-collection regressions for recommendation ranking."""

from __future__ import annotations
import pytest

pytestmark = [pytest.mark.live_data, pytest.mark.usefixtures("live_databases")]


import random

import strategy_db
from db import get_db
from routers.analyze_v2 import AnalyzeRequestV2, OwnedCard, analyze_v2

TARGET = "A-Satoru Umezawa"
STRATEGY = "ninja_evasion_tempo"


def _benchmark_collection(
    *,
    commander_owned: bool,
    noise_count: int = 0,
) -> list[OwnedCard]:
    with strategy_db.get_strategy_db() as conn:
        rows = conn.execute(
            """
            SELECT cc.name
            FROM commander_strategy_cards csc
            JOIN cards commander
              ON commander.oracle_id = csc.commander_oracle_id
            JOIN cards cc ON cc.oracle_id = csc.card_oracle_id
            WHERE commander.name = ?
              AND csc.strategy_template_id = ?
              AND cc.is_land = 0
            ORDER BY csc.card_weight DESC, cc.name
            LIMIT 90
            """,
            (TARGET, STRATEGY),
        ).fetchall()

    names = {row["name"] for row in rows}
    names.discard(TARGET)
    if commander_owned:
        names.add(TARGET)

    if noise_count:
        with get_db() as conn:
            noise_pool = [
                row["name"] for row in conn.execute(
                    "SELECT name FROM cards "
                    "WHERE is_commander = 0 AND is_land = 0 ORDER BY name"
                ).fetchall()
                if row["name"] not in names
            ]
        names.update(random.Random(42).sample(noise_pool, noise_count))
    return [OwnedCard(name=name, count=1) for name in sorted(names)]


def _rank(recommendations, commander: str) -> int | None:
    for index, recommendation in enumerate(recommendations, 1):
        if recommendation.name == commander:
            return index
    return None


def test_owned_satoru_survives_100_card_random_noise():
    result = analyze_v2(AnalyzeRequestV2(
        collection=_benchmark_collection(commander_owned=True, noise_count=100),
    ))
    rank = _rank(result.owned_recommendations, TARGET)
    assert rank is not None and rank <= 3
    recommendation = result.owned_recommendations[rank - 1]
    assert recommendation.strategy_id == STRATEGY
    assert recommendation.collection_readiness >= 50


def test_removing_commander_moves_same_deck_to_nearest_unowned_lane():
    result = analyze_v2(AnalyzeRequestV2(
        collection=_benchmark_collection(commander_owned=False),
    ))
    rank = _rank(result.unowned_recommendations, TARGET)
    assert rank is not None and rank <= 3
    recommendation = result.unowned_recommendations[rank - 1]
    assert recommendation.strategy_id == STRATEGY
    assert recommendation.commander_wildcard_required
    assert recommendation.completion_cost_by_rarity.rare >= 1
