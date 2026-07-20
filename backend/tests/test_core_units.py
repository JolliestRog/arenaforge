"""Fast backend unit regressions required in every clean checkout."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from routers.analyze_v2 import _AnalysisGate, _completion_cost
from solver.model import BuildResult, _score_card
from solver.profiles import Profile, RoleTarget


def test_role_relaxed_result_remains_usable():
    result = BuildResult(
        cards=[],
        commander={"name": "Fixture Commander"},
        score=0,
        status="role_relaxed",
    )
    assert not result.infeasible


def test_unowned_commander_is_included_in_completion_cost():
    cost, points = _completion_cost([], {"rarity": "rare"}, commander_owned=False)
    assert cost.rare == 1
    assert points == 8


def test_quality_scoring_is_ownership_neutral():
    card = {"name": "Fixture Card", "is_land": False, "rarity": "mythic", "cmc": 2}
    profile = Profile(
        id="fixture",
        commander="",
        display_name="",
        description="",
        land_target=36,
        role_targets={"draw": RoleTarget(1, 1)},
        role_weights={"draw": 5},
        synergy_tag="",
        priority_roles=["draw"],
        functional_hand_definition="",
    )
    owned = _score_card(card, ["draw"], profile, True, "quality", 0.5)
    unowned = _score_card(card, ["draw"], profile, False, "quality", 0.5)
    assert owned == unowned


def test_analysis_gate_rejects_excess_waiters_and_recovers():
    gate = _AnalysisGate(max_active=1, max_waiting=0)
    gate.acquire(timeout_s=0.01)
    try:
        with pytest.raises(HTTPException) as exc:
            gate.acquire(timeout_s=0.01)
        assert exc.value.status_code == 503
        assert gate.snapshot()["active"] == 1
    finally:
        gate.release()
    assert gate.snapshot()["active"] == 0
