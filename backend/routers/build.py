import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import strategy_db
from card_names import build_card_name_index, normalize_collection
from db import get_db
from solver.model import (
    BuildResult, DeckCard, Variant, _score_card, arena_export,
    build_variant, estimate_functional_hand,
)
from solver.profiles import PROFILES
from solver.roles import infer_roles
from solver.strategy_profile import profile_from_strategy_rows
from wildcard_costs import (
    commander_wildcard_rarity,
    completion_wildcard_cost,
    reserve_commander_wildcard,
)

router = APIRouter(prefix="/build", tags=["build"])

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

class FeaturedCards(BaseModel):
    engines: list[str] = []
    finishers: list[str] = []
    setup: list[str] = []
    interaction: list[str] = []
    protection: list[str] = []
    ramp: list[str] = []

class DeckVariantResponse(BaseModel):
    variant_key: str
    label: str
    description: str
    strategy_name: str
    strategy_id: str
    macro_plan: str = ""
    commander: CardResponse
    commander_owned: bool
    commander_wildcard_cost: Literal["common", "uncommon", "rare", "mythic"] | None
    cards: list[DeckCardResponse]
    role_counts: dict[str, int]
    mana_curve: dict[str, int]
    wildcard_cost: dict[str, int]
    functional_hand_estimate: float
    weakest_cards: list[str]
    excluded_high_scorers: list[ExcludedCard]
    arena_export: str
    score: float
    build_status: Literal["complete", "role_relaxed", "unavailable"]
    unavailable_reason: Literal[
        "card_pool_or_budget", "solver_timeout", "solver_error"
    ] | None = None
    infeasible: bool
    featured_cards: FeaturedCards = FeaturedCards()

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


def _featured_cards_for(cards: list[DeckCard]) -> FeaturedCards:
    def top(role_any: list[str], n: int = 4) -> list[str]:
        role_set = set(role_any)
        hits = [dc for dc in cards if not dc.card["is_land"] and set(dc.roles) & role_set]
        hits.sort(key=lambda dc: -dc.score)
        seen: set[str] = set()
        result = []
        for dc in hits:
            if dc.card["name"] not in seen:
                seen.add(dc.card["name"])
                result.append(dc.card["name"])
            if len(result) >= n:
                break
        return result

    return FeaturedCards(
        engines=top(["engine"]),
        finishers=top(["finisher"]),
        setup=top(["selection", "topdeck_setup"]),
        interaction=top(["counterspell", "creature_removal", "sweeper"]),
        protection=top(["protection"]),
        ramp=top(["ramp"]),
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


def _wildcard_costs(
    cards: list[DeckCard],
    commander: dict,
    commander_owned: bool,
) -> dict[str, int]:
    return completion_wildcard_cost(cards, commander, commander_owned)


def _weakest_cards(cards: list[DeckCard]) -> list[str]:
    non_lands = [dc for dc in cards if not dc.card["is_land"]]
    return [dc.card["name"] for dc in sorted(non_lands, key=lambda c: c.score)[:5]]


def _build_variant_response(
    result: BuildResult,
    variant_key: str,
    label: str,
    description: str,
    strategy_name: str,
    strategy_id: str,
    all_candidates: list[dict],
    owned_set: set[str],
    profile,
    commander_owned: bool,
    solver_variant: str = "performance",
    strategy_weights: dict[str, float] | None = None,
    macro_plan: str = "",
) -> DeckVariantResponse:
    sw = strategy_weights or {}
    selected_names = {dc.card["name"] for dc in result.cards}
    excluded = []
    for card in all_candidates:
        if card["name"] in selected_names or card["name"] == result.commander["name"]:
            continue
        roles = infer_roles(card)
        owned = card["name"] in owned_set
        score = _score_card(card, roles, profile, owned, solver_variant, sw.get(card["name"], 0.0))
        excluded.append(ExcludedCard(name=card["name"], score=score, reason="not selected"))
    excluded.sort(key=lambda e: -e.score)

    return DeckVariantResponse(
        variant_key=variant_key,
        label=label,
        description=description,
        strategy_name=strategy_name,
        strategy_id=strategy_id,
        macro_plan=macro_plan,
        commander=_card_response(result.commander),
        commander_owned=commander_owned,
        commander_wildcard_cost=commander_wildcard_rarity(
            result.commander, commander_owned
        ),
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
        wildcard_cost=_wildcard_costs(
            result.cards, result.commander, commander_owned
        ),
        functional_hand_estimate=estimate_functional_hand(result.cards, profile),
        weakest_cards=_weakest_cards(result.cards),
        excluded_high_scorers=excluded[:5],
        arena_export=arena_export(result.commander, result.cards),
        score=result.score,
        build_status=result.status,
        unavailable_reason=result.unavailable_reason,
        infeasible=result.infeasible,
        featured_cards=_featured_cards_for(result.cards),
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

# Each entry: (variant_key, label, description, budget_preset_or_None, solver_variant)
# budget_preset=None → use the user's wildcard_budget (the "optimized" tier)
# solver_variant maps to CP-SAT scoring mode ("wildcard" prefers owned, "performance" ignores ownership)
VARIANT_PRESETS = [
    ("free",        "Free",          "Built entirely from your collection — zero wildcards needed.",
     {"common": 0, "uncommon": 0, "rare": 0, "mythic": 0},  "wildcard"),
    ("cheap",       "Budget",        "Low-cost upgrades — up to 2 rares, no mythics.",
     {"common": 8,  "uncommon": 5,  "rare": 2, "mythic": 0}, "wildcard"),
    ("competitive", "Competitive",   "Meaningful upgrades — up to 6 rares and 2 mythics.",
     {"common": 20, "uncommon": 12, "rare": 6, "mythic": 2}, "performance"),
    ("optimized",   "Optimized",     "Best possible build within your wildcard budget.",
     None, "performance"),
]


@router.post("", response_model=list[DeckVariantResponse])
def build(req: BuildRequest):
    # Resolve profile — may be a legacy profile ID or a strategy template ID
    strategy_weights: dict[str, float] | None = None
    profile = PROFILES.get(req.profile)
    strategy_name: str = ""
    macro_plan: str = ""

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
        macro_plan = row["macro_plan"] or ""
        profile = profile_from_strategy_rows(
            row["id"],
            row["display_name"],
            row["macro_plan"],
            strategy_db.fetch_strategy_role_targets(row["id"]),
        )
        strategy_weights = strategy_db.fetch_strategy_card_weights(req.commander, req.profile)
    else:
        strategy_name = profile.display_name
        macro_plan = getattr(profile, "macro_plan", "")

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
    all_cards = [dict(row) for row in all_rows]

    ci_set = set(ci)
    candidates = [
        card for card in all_cards
        if set(json.loads(card["color_identity"])).issubset(ci_set)
    ]

    owned_set, _, _ = normalize_collection(
        req.collection, build_card_name_index(all_cards)
    )
    commander_owned = commander["name"] in owned_set
    wc = req.wildcard_budget.model_dump()

    variants = []
    for vk, label, description, budget_preset, solver_vk in VARIANT_PRESETS:
        requested_budget = budget_preset if budget_preset is not None else wc
        build_budget = reserve_commander_wildcard(
            requested_budget, commander, commander_owned
        )
        if build_budget is None:
            result = BuildResult(
                cards=[], commander=commander, score=0,
                status="unavailable", unavailable_reason="card_pool_or_budget",
            )
        else:
            result = build_variant(
                commander=commander,
                candidates=candidates,
                owned_set=owned_set,
                profile=profile,
                wildcard_budget=build_budget,
                variant=solver_vk,
                time_limit_s=5.0,
                strategy_weights=strategy_weights,
            )

        variants.append(
            _build_variant_response(
                result, vk, label, description, strategy_name, req.profile,
                candidates, owned_set, profile,
                commander_owned=commander_owned,
                solver_variant=solver_vk,
                strategy_weights=strategy_weights,
                macro_plan=macro_plan,
            )
        )

    return variants
