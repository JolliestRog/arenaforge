"""Regression coverage for Arena name matching, Yuriko, and Free mana bases."""

from __future__ import annotations
import pytest

pytestmark = [pytest.mark.live_data, pytest.mark.usefixtures("live_databases")]


from card_names import build_card_name_index, normalize_collection
from db import get_db
from routers.analyze_v2 import AnalyzeRequestV2, analyze_v2
from solver.model import _wc_cost_for, build_variant
from solver.profiles import Profile


def test_arena_front_face_rebalanced_and_accent_aliases_resolve():
    with get_db() as conn:
        cards = [dict(row) for row in conn.execute("SELECT * FROM cards")]

    collection = [
        {"name": "A-Lantern Bearer", "count": 1},
        {"name": "Blackbloom Rogue", "count": 1},
        {"name": "Boggart Trawler", "count": 1},
        {"name": "Dokuchi Silencer", "count": 1},
        {"name": "Orcish Bowmasters", "count": 1},
        {"name": "The One Ring", "count": 1},
        {"name": "Lorien Revealed", "count": 1},
        {"name": "Troll of Khazad-dum", "count": 1},
        {"name": "Bespoke Bo", "count": 1},
        {"name": "Wash Away", "count": 1},
    ]
    owned, unmatched, total_copies = normalize_collection(
        collection, build_card_name_index(cards)
    )

    assert {
        "A-Lantern Bearer // A-Lanterns' Lift",
        "Blackbloom Rogue // Blackbloom Bog",
        "Boggart Trawler // Boggart Bog",
        "A-Dokuchi Silencer",
        "A-Orcish Bowmasters",
        "A-The One Ring",
        "Lórien Revealed",
        "Troll of Khazad-dûm",
        "Bespoke Bō",
    } <= owned
    assert unmatched == ["Wash Away"]
    assert total_copies == 9


def test_owned_yuriko_is_not_hidden_by_strategy_arena_metadata():
    result = analyze_v2(AnalyzeRequestV2(
        collection=[{"name": "Yuriko, the Tiger's Shadow", "count": 1}],
        strategy_filter="All",
    ))

    yuriko = next(
        rec for rec in result.owned_recommendations
        if rec.name == "Yuriko, the Tiger's Shadow"
    )
    assert yuriko.commander_owned
    assert yuriko.strategy_id == "ninja_evasion_tempo"
    assert "Yuriko, the Tiger's Shadow" not in result.unmatched_cards


def _solver_card(name: str, *, is_land: bool, type_line: str) -> dict:
    return {
        "name": name,
        "mana_cost": None,
        "cmc": 0,
        "color_identity": '["U", "B"]' if name != "Island" else '["U"]',
        "type_line": type_line,
        "rarity": "common",
        "oracle_text": "",
        "keywords": "[]",
        "power": None,
        "toughness": None,
        "is_land": is_land,
        "is_creature": False,
        "is_legendary": False,
        "is_commander": False,
    }


def test_zero_budget_uses_unlimited_basics_not_unowned_common_nonbasics():
    commander = _solver_card(
        "Test Commander", is_land=False, type_line="Legendary Creature"
    )
    commander["color_identity"] = '["U", "B"]'
    spells = [
        _solver_card(f"Owned Spell {index}", is_land=False, type_line="Sorcery")
        for index in range(63)
    ]
    basics = [
        _solver_card("Island", is_land=True, type_line="Basic Land — Island"),
        _solver_card("Swamp", is_land=True, type_line="Basic Land — Swamp"),
    ]
    nonbasics = [
        _solver_card(f"Free Dual {index}", is_land=True, type_line="Land")
        for index in range(40)
    ]
    profile = Profile(
        id="test",
        commander="Test Commander",
        display_name="Test",
        description="",
        land_target=36,
        role_targets={},
        role_weights={},
        synergy_tag="",
        priority_roles=[],
        functional_hand_definition="",
    )

    result = build_variant(
        commander=commander,
        candidates=[*spells, *basics, *nonbasics],
        owned_set={card["name"] for card in spells},
        profile=profile,
        wildcard_budget={"common": 0, "uncommon": 0, "rare": 0, "mythic": 0},
        variant="wildcard",
        time_limit_s=2,
    )

    assert len(result.cards) == 99
    assert all(card.owned and card.wildcard_cost is None for card in result.cards)
    assert not any(card.card["name"].startswith("Free Dual") for card in result.cards)
    basic_count = sum(
        card.card["name"] in {"Island", "Swamp"} for card in result.cards
    )
    assert profile.land_target - 1 <= basic_count <= profile.land_target + 2
    assert _wc_cost_for(nonbasics[0], owned=False) == "common"
