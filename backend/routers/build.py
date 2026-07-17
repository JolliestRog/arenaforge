import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import strategy_db
from db import get_db
from solver.model import (
    BuildResult, DeckCard, Variant, _score_card, arena_export,
    build_variant, estimate_functional_hand,
)
from solver.profiles import Profile, PROFILES, RoleTarget
from solver.roles import infer_roles

router = APIRouter(prefix="/build", tags=["build"])

# Map strategy DB role names → solver role names (subset that CP-SAT can enforce)
_STRATEGY_ROLE_MAP = {
    "draw": "draw",
    "ramp": "ramp",
    "counterspell": "counterspell",
    "protection": "protection",
    "finisher": "finisher",
    "selection": "selection",
    "recursion": "recursion",
    "removal": "creature_removal",
    "board_wipe": "sweeper",
}

_LAND_TARGET_BY_MACRO = {
    "tempo": 34, "aggro": 34, "control": 38, "ramp": 38, "midrange": 36,
}


def _profile_from_strategy(strategy_id: str, display_name: str, macro_plan: str) -> Profile:
    """Synthesize a Profile from strategy DB role targets."""
    role_target_rows = strategy_db.fetch_strategy_role_targets(strategy_id)
    role_targets: dict[str, RoleTarget] = {}
    role_weights: dict[str, float] = {}
    for row in role_target_rows:
        solver_role = _STRATEGY_ROLE_MAP.get(row["role"])
        if solver_role:
            role_targets[solver_role] = RoleTarget(
                min=row["min_count"], preferred=row["preferred_count"]
            )
            role_weights[solver_role] = row["weight"] * 10  # 0.0-0.9 → 0-9

    land_target = _LAND_TARGET_BY_MACRO.get(macro_plan, 36)

    # Always ensure draw and ramp have at least a soft floor
    if "draw" not in role_targets:
        role_targets["draw"] = RoleTarget(min=6, preferred=10)
        role_weights["draw"] = 5.0
    if "ramp" not in role_targets:
        role_targets["ramp"] = RoleTarget(min=5, preferred=8)
        role_weights["ramp"] = 5.0

    priority = sorted(role_weights, key=lambda r: -role_weights[r])[:3]
    return Profile(
        id=strategy_id,
        commander="",
        display_name=display_name,
        description="",
        land_target=land_target,
        role_targets=role_targets,
        role_weights=role_weights,
        synergy_tag="",
        priority_roles=priority,
        functional_hand_definition="viable mana + key role pieces",
    )

# ── Request models ─────────────────────────────────────────────────────────────

class OwnedCard(BaseModel):
    name: str
    count: int

class WildcardBudget(BaseModel):
    common: int = 9999
    uncommon: int = 9999
    rare: int = 9999
    mythic: int = 9999

class BuildRequest(BaseModel):
    collection: list[OwnedCard]
    commander: str
    profile: str
    wildcard_budget: WildcardBudget = WildcardBudget()

# ── Response models ────────────────────────────────────────────────────────────

class CardResponse(BaseModel):
    name: str
    cmc: float
    mana_cost: str | None
    color_identity: list[str]
    type_line: str
    rarity: str
    oracle_text: str
    keywords: list[str]
    power: str | None
    toughness: str | None
    is_land: bool
    is_creature: bool
    is_legendary: bool
    is_commander: bool

class DeckCardResponse(BaseModel):
    card: CardResponse
    roles: list[str]
    owned: bool
    wildcard_cost: str | None
    reason: str
    score: float

class ExcludedCard(BaseModel):
    name: str
    score: float
    reason: str

class DeckVariantResponse(BaseModel):
    variant_key: Literal["performance", "wildcard", "consistency"]
    label: str
    description: str
    strategy_name: str
    commander: CardResponse
    cards: list[DeckCardResponse]
    role_counts: dict[str, int]
    mana_curve: dict[str, int]
    wildcard_cost: dict[str, int]
    functional_hand_estimate: float
    weakest_cards: list[str]
    excluded_high_scorers: list[ExcludedCard]
    arena_export: str
    score: float
    infeasible: bool

# ── Helpers ───────────────────────────────────────────────────────────────────

def _card_response(card: dict) -> CardResponse:
    return CardResponse(
        name=card["name"],
        cmc=card["cmc"],
        mana_cost=card["mana_cost"],
        color_identity=json.loads(card["color_identity"]),
        type_line=card["type_line"],
        rarity=card["rarity"],
        oracle_text=card["oracle_text"],
        keywords=json.loads(card["keywords"]),
        power=card["power"],
        toughness=card["toughness"],
        is_land=bool(card["is_land"]),
        is_creature=bool(card["is_creature"]),
        is_legendary=bool(card["is_legendary"]),
        is_commander=bool(card["is_commander"]),
    )


def _role_counts(cards: list[DeckCard]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for dc in cards:
        for role in dc.roles:
            counts[role] = counts.get(role, 0) + 1
    return counts


def _mana_curve(cards: list[DeckCard]) -> dict[str, int]:
    curve: dict[str, int] = {}
    for dc in cards:
        if dc.card["is_land"]:
            continue
        mv = min(int(dc.card["cmc"]), 7)
        key = str(mv)
        curve[key] = curve.get(key, 0) + 1
    return curve


def _wildcard_costs(cards: list[DeckCard]) -> dict[str, int]:
    costs = {"common": 0, "uncommon": 0, "rare": 0, "mythic": 0}
    for dc in cards:
        if dc.wildcard_cost:
            costs[dc.wildcard_cost] = costs.get(dc.wildcard_cost, 0) + 1
    return costs


def _weakest_cards(cards: list[DeckCard]) -> list[str]:
    non_lands = [dc for dc in cards if not dc.card["is_land"]]
    return [dc.card["name"] for dc in sorted(non_lands, key=lambda c: c.score)[:5]]


def _build_variant_response(
    result: BuildResult,
    variant_key: str,
    label: str,
    description: str,
    strategy_name: str,
    all_candidates: list[dict],
    owned_set: set[str],
    profile,
    strategy_weights: dict[str, float] | None = None,
) -> DeckVariantResponse:
    sw = strategy_weights or {}
    selected_names = {dc.card["name"] for dc in result.cards}
    # Top excluded candidates by score
    excluded = []
    for card in all_candidates:
        if card["name"] in selected_names or card["name"] == result.commander["name"]:
            continue
        roles = infer_roles(card)
        owned = card["name"] in owned_set
        score = _score_card(card, roles, profile, owned, variant_key, sw.get(card["name"], 0.0))
        excluded.append(ExcludedCard(name=card["name"], score=score, reason="not selected"))
    excluded.sort(key=lambda e: -e.score)

    return DeckVariantResponse(
        variant_key=variant_key,
        label=label,
        description=description,
        strategy_name=strategy_name,
        commander=_card_response(result.commander),
        cards=[
            DeckCardResponse(
                card=_card_response(dc.card),
                roles=dc.roles,
                owned=dc.owned,
                wildcard_cost=dc.wildcard_cost,
                reason=dc.reason,
                score=dc.score,
            )
            for dc in result.cards
        ],
        role_counts=_role_counts(result.cards),
        mana_curve=_mana_curve(result.cards),
        wildcard_cost=_wildcard_costs(result.cards),
        functional_hand_estimate=estimate_functional_hand(result.cards, profile),
        weakest_cards=_weakest_cards(result.cards),
        excluded_high_scorers=excluded[:5],
        arena_export=arena_export(result.commander, result.cards),
        score=result.score,
        infeasible=result.infeasible,
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

VARIANT_META = {
    "performance": ("Highest Performance", "Maximum power — wildcards used freely."),
    "wildcard":    ("Lowest Wildcard Cost", "Prefers cards you already own."),
    "consistency": ("Highest Consistency",  "Optimized for functional opening hands."),
}


@router.post("", response_model=list[DeckVariantResponse])
def build(req: BuildRequest):
    # Resolve profile — may be a legacy profile ID or a strategy template ID
    strategy_weights: dict[str, float] | None = None
    profile = PROFILES.get(req.profile)
    strategy_name: str = ""

    if profile is None:
        # Try loading from strategy DB
        with strategy_db.get_strategy_db() as s_conn:
            if s_conn is None:
                raise HTTPException(status_code=422, detail=f"Unknown profile: {req.profile}")
            row = s_conn.execute(
                "SELECT id, display_name, macro_plan FROM strategy_templates WHERE id = ?",
                (req.profile,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=422, detail=f"Unknown profile: {req.profile}")
        strategy_name = row["display_name"]
        profile = _profile_from_strategy(row["id"], row["display_name"], row["macro_plan"])
        strategy_weights = strategy_db.fetch_strategy_card_weights(req.commander, req.profile)
    else:
        strategy_name = profile.display_name

    # Fetch commander
    with get_db() as conn:
        commander_row = conn.execute(
            "SELECT * FROM cards WHERE name = ?", (req.commander,)
        ).fetchone()
    if commander_row is None:
        raise HTTPException(status_code=404, detail=f"Commander not found: {req.commander}")

    commander = dict(commander_row)
    ci = json.loads(commander["color_identity"])

    # Fetch candidate pool (color identity subset of commander's)
    with get_db() as conn:
        all_rows = conn.execute("SELECT * FROM cards ORDER BY name").fetchall()

    ci_set = set(ci)
    candidates = [
        dict(r) for r in all_rows
        if set(json.loads(r["color_identity"])).issubset(ci_set)
    ]

    owned_set = {oc.name for oc in req.collection if oc.count >= 1}
    wc = req.wildcard_budget.model_dump()

    variants = []
    for vk in ("performance", "wildcard", "consistency"):
        result = build_variant(
            commander=commander,
            candidates=candidates,
            owned_set=owned_set,
            profile=profile,
            wildcard_budget=wc,
            variant=vk,
            time_limit_s=5.0,
            strategy_weights=strategy_weights,
        )
        label, description = VARIANT_META[vk]
        variants.append(
            _build_variant_response(
                result, vk, label, description, strategy_name, candidates, owned_set, profile,
                strategy_weights=strategy_weights,
            )
        )

    return variants
