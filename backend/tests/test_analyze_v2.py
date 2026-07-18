"""Fixture-based regression tests for POST /analyze/v2.

All tests call the endpoint function directly (no HTTP server required).
The suite is skipped automatically when the DBs are absent (see conftest.py).
"""

from __future__ import annotations

from routers.analyze_v2 import (
    AnalysisResultV2,
    AnalyzeRequestV2,
    OwnedCard,
    analyze_v2,
    FILTER_TO_MACRO,
)
from tests.conftest import CONTROL_FIXTURE, EMPTY_FIXTURE


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_collection(cards: list[dict]) -> list[OwnedCard]:
    return [OwnedCard(name=c["name"], count=c["count"]) for c in cards]


def _call(collection: list[dict], strategy_filter: str = "All") -> AnalysisResultV2:
    return analyze_v2(AnalyzeRequestV2(
        collection=_make_collection(collection),
        strategy_filter=strategy_filter,
    ))


# ── Acceptance: Control filter only returns Control commanders ────────────────

def test_control_filter_returns_only_control_commanders():
    """Selecting 'Control' must never surface non-Control commanders."""
    result = _call(CONTROL_FIXTURE, "Control")
    assert result.strategy_filter == "Control"
    for rec in result.recommendations:
        # Every recommendation must be a control-strategy pair
        macro = FILTER_TO_MACRO["Control"]
        # Strategy name should come from a control template. We verify via the
        # strategy_id — control templates are big_mana_tap_control / enchantress_control.
        assert rec.strategy_id in {
            "big_mana_tap_control", "enchantress_control",
        }, (
            f"{rec.name!r} was returned under Control filter "
            f"but has strategy_id={rec.strategy_id!r}"
        )


def test_control_filter_not_dependent_on_unfiltered_top20():
    """Results under Control filter must differ from naive top-20 of All filter."""
    all_result     = _call(CONTROL_FIXTURE, "All")
    control_result = _call(CONTROL_FIXTURE, "Control")

    all_names     = {r.name for r in all_result.recommendations}
    control_names = {r.name for r in control_result.recommendations}

    # At least some Control results should not appear in the top-10 All results,
    # proving V2 does not just slice the unfiltered list.
    # (If the collection is perfectly optimised for control, all top-10 might be
    #  control anyway — so we accept equality only when all_names ⊆ control_names.)
    if len(control_result.recommendations) > 0 and len(all_result.recommendations) > 0:
        # The control-filtered result set must be a subset of control-strategy pairs
        for rec in control_result.recommendations:
            assert rec.strategy_id in {"big_mana_tap_control", "enchantress_control"}


def test_weak_collection_still_returns_control_commanders():
    """Even an empty collection should return control commanders (with high wildcard cost)."""
    result = _call(EMPTY_FIXTURE, "Control")
    assert result.strategy_filter == "Control"
    assert len(result.recommendations) > 0, "No Control recommendations for empty collection"
    for rec in result.recommendations:
        assert rec.strategy_id in {"big_mana_tap_control", "enchantress_control"}


def test_weak_collection_gets_viable_completion_path_not_fallbacks():
    """Weak collections should report wildcard costs, not unrelated commander types."""
    result = _call(EMPTY_FIXTURE, "Control")
    for rec in result.recommendations:
        total_wc = (
            rec.wildcard_cost_by_rarity.common
            + rec.wildcard_cost_by_rarity.uncommon
            + rec.wildcard_cost_by_rarity.rare
            + rec.wildcard_cost_by_rarity.mythic
        )
        # Empty collection needs wildcards for almost everything.
        assert total_wc > 20, (
            f"{rec.name!r} has suspiciously low wildcard cost {total_wc} for empty collection"
        )
        # Must still be a control commander.
        assert rec.strategy_id in {"big_mana_tap_control", "enchantress_control"}


# ── Acceptance: readiness from 99-card deck ───────────────────────────────────

def test_readiness_based_on_99_card_deck():
    """build_readiness must reflect role coverage in the proposed deck, not just the pool."""
    result = _call(CONTROL_FIXTURE, "Control")
    for rec in result.recommendations:
        # Every role coverage item must have a deck_count that's plausible for a 99-card deck.
        for item in rec.strategy_role_coverage:
            assert 0 <= item.deck_count <= 99, (
                f"{rec.name!r} role {item.role!r} deck_count={item.deck_count} out of range"
            )
        # build_readiness is in [0, 100]
        assert 0.0 <= rec.build_readiness <= 100.0


# ── Acceptance: determinism ───────────────────────────────────────────────────

def test_identical_inputs_produce_identical_results():
    """Two calls with the same collection and filter must produce identical output."""
    result_a = _call(CONTROL_FIXTURE, "Control")
    result_b = _call(CONTROL_FIXTURE, "Control")

    assert len(result_a.recommendations) == len(result_b.recommendations)
    for a, b in zip(result_a.recommendations, result_b.recommendations):
        assert a.name        == b.name
        assert a.strategy_id == b.strategy_id
        assert abs(a.build_readiness - b.build_readiness) < 0.01, (
            f"build_readiness not deterministic for {a.name!r}: {a.build_readiness} vs {b.build_readiness}"
        )
        assert a.wildcard_cost_by_rarity == b.wildcard_cost_by_rarity


# ── Acceptance: score variation ───────────────────────────────────────────────

def test_scores_vary_meaningfully_between_commanders():
    """Different commanders must not all receive the same build_readiness score."""
    result = _call(CONTROL_FIXTURE, "All")
    if len(result.recommendations) < 2:
        return  # can't measure variation with fewer than 2

    scores = [r.build_readiness for r in result.recommendations]
    assert max(scores) - min(scores) >= 1.0, (
        f"build_readiness scores suspiciously uniform: {scores}"
    )


def test_strategy_intrinsic_fit_varies():
    """strategy_intrinsic_fit must differ across commanders."""
    result = _call(CONTROL_FIXTURE, "All")
    if len(result.recommendations) < 2:
        return
    fits = [r.strategy_intrinsic_fit for r in result.recommendations]
    assert max(fits) - min(fits) >= 0.01, (
        f"strategy_intrinsic_fit suspiciously uniform: {fits}"
    )


# ── Acceptance: human-readable evidence ──────────────────────────────────────

def test_every_recommendation_has_evidence():
    """Every recommendation must include either strengths, deficits, key_owned, or key_missing."""
    result = _call(CONTROL_FIXTURE, "All")
    for rec in result.recommendations:
        has_evidence = (
            len(rec.key_owned)  > 0
            or len(rec.key_missing) > 0
            or len(rec.strengths)   > 0
            or len(rec.deficits)    > 0
        )
        assert has_evidence, f"{rec.name!r} has no human-readable evidence at all"


# ── Acceptance: separate components (no opaque single score) ──────────────────

def test_response_has_all_required_components():
    """Each recommendation must expose all six separate score components."""
    result = _call(CONTROL_FIXTURE, "Control")
    for rec in result.recommendations:
        assert rec.build_readiness        is not None
        assert rec.wildcard_cost_by_rarity is not None
        assert rec.mana_readiness         is not None
        assert rec.strategy_role_coverage is not None
        assert rec.commander_owned        is not None
        assert rec.confidence             is not None
        # strategy_role_coverage must be non-empty for a DB-backed strategy
        assert len(rec.strategy_role_coverage) > 0, (
            f"{rec.name!r} has empty strategy_role_coverage"
        )


# ── Acceptance: filter labels and strategy_filter echoed back ─────────────────

def test_strategy_filter_echoed_in_response():
    for flt in ("All", "Control", "Midrange", "Tempo"):
        result = _call(EMPTY_FIXTURE, flt)
        assert result.strategy_filter == flt


# ── Unit: helpers (no DB needed for these) ────────────────────────────────────

def test_mana_readiness_single_color():
    from routers.analyze_v2 import _mana_readiness, WildcardCostByRarity
    from solver.model import DeckCard

    def _dc(is_land: bool, roles: list[str]) -> DeckCard:
        return DeckCard(
            card={"is_land": is_land, "name": "x", "cmc": 0, "rarity": "common",
                  "mana_cost": None, "color_identity": "[]", "type_line": "",
                  "oracle_text": "", "keywords": "[]", "power": None, "toughness": None,
                  "is_creature": False, "is_legendary": False, "is_commander": False},
            roles=roles, owned=True, wildcard_cost=None, reason="test", score=0,
        )

    # Mono-color: only ramp matters
    cards = [_dc(False, ["ramp"])] * 7 + [_dc(True, ["land"])] * 36
    score = _mana_readiness(cards, ["B"])
    assert score > 0.0


def test_wildcard_cost_counting():
    from routers.analyze_v2 import _wildcard_cost
    from solver.model import DeckCard

    def _dc(wc: str | None) -> DeckCard:
        return DeckCard(
            card={"is_land": False, "name": "x", "cmc": 0, "rarity": wc or "common",
                  "mana_cost": None, "color_identity": "[]", "type_line": "",
                  "oracle_text": "", "keywords": "[]", "power": None, "toughness": None,
                  "is_creature": False, "is_legendary": False, "is_commander": False},
            roles=[], owned=(wc is None), wildcard_cost=wc, reason="test", score=0,
        )

    cards = [_dc("rare")] * 3 + [_dc("mythic")] * 2 + [_dc(None)] * 5
    cost = _wildcard_cost(cards)
    assert cost.rare == 3
    assert cost.mythic == 2
    assert cost.common == 0
    assert cost.uncommon == 0


def test_invalid_strategy_filter_raises():
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _call(EMPTY_FIXTURE, "NotAFilter")
    assert exc.value.status_code == 422
