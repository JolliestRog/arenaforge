"""Regression coverage for deck variant availability and status semantics."""

from __future__ import annotations

from routers.build import BuildRequest, WildcardBudget, build
from solver.model import BuildResult


def test_role_relaxed_result_is_usable():
    result = BuildResult(
        cards=[],
        commander={"name": "Test Commander"},
        score=0,
        status="role_relaxed",
    )
    assert not result.infeasible


def test_spider_woman_unlimited_build_does_not_crash_and_has_usable_optimized_deck():
    variants = build(BuildRequest(
        collection=[],
        commander="Spider-Woman, Secret Agent",
        profile="big_mana_tap_control",
        wildcard_budget=WildcardBudget(),
    ))

    assert len(variants) == 4
    by_key = {variant.variant_key: variant for variant in variants}
    assert by_key["free"].build_status == "unavailable"
    assert by_key["free"].cards == []

    optimized = by_key["optimized"]
    assert optimized.build_status in {"complete", "role_relaxed"}
    assert not optimized.infeasible
    assert len(optimized.cards) == 99
