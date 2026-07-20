"""Collection analysis with separate owned-best and unowned-nearest rankings."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import strategy_db
from card_names import build_card_name_index, normalize_collection
from db import get_db
from routers.analyze import (
    ColorStrength,
    KeyCard,
    OwnedCard,
    _build_ci_pools,
    _color_strength,
    _role_counts,
    _summary,
    _type_distribution,
)
from solver.model import DeckCard, WC_VALUES, build_variant
from solver.roles import infer_roles
from solver.strategy_profile import STRATEGY_ROLE_MAP, profile_from_strategy_rows
from wildcard_costs import (
    completion_wildcard_cost,
    deck_wildcard_cost,
    wildcard_points,
)

log = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/analyze/v2", tags=["analyze-v2"])

COVERAGE_CARD_LIMIT = 60
FINALISTS_PER_LANE = 12
OWNED_RESULTS_LIMIT = 12
UNOWNED_RESULTS_LIMIT = 6
BUILD_TIME_LIMIT_S = 3.0
MAX_WORKERS = 4
QUALITY_FLOOR = 55.0
RANKING_VERSION = "owned-best-unowned-nearest-v3-card-aliases"

MAX_ACTIVE_ANALYSES = 1
MAX_WAITING_ANALYSES = 4
QUEUE_TIMEOUT_S = 120.0

FILTER_TO_MACRO: dict[str, str | None] = {
    "All": None,
    "Control": "control",
    "Tempo": "tempo",
    "Aggro": "aggro",
    "Midrange": "midrange",
    "Ramp": "ramp",
}

_ROLE_DISPLAY: dict[str, str] = {
    "ramp": "Ramp",
    "draw": "Card Draw",
    "removal": "Removal",
    "counterspell": "Counterspells",
    "board_wipe": "Board Wipes",
    "finisher": "Finishers",
    "protection": "Protection",
    "token_maker": "Token Production",
    "sacrifice_outlet": "Sacrifice Outlets",
    "death_payoff": "Death Payoffs",
    "recursion": "Recursion",
    "graveyard_filler": "Graveyard Filling",
    "attack_payoff": "Attack Payoffs",
    "enchantment_payoff": "Enchantment Payoffs",
    "artifact_payoff": "Artifact Payoffs",
    "counters_enabler": "Counter Enablers",
    "counters_payoff": "Counter Payoffs",
    "lifegain_enabler": "Lifegain Enablers",
    "lifegain_payoff": "Lifegain Payoffs",
    "land_payoff": "Land Payoffs",
    "tap_enabler": "Tap Enablers",
    "untap_denial": "Untap Denial",
    "anthem": "Anthems",
    "selection": "Card Selection",
    "evasive_enabler": "Evasive Enablers",
    "ninjutsu_payoff": "Ninjutsu Payoffs",
    "topdeck_setup": "Topdeck Setup",
    "blink_enabler": "Blink Effects",
    "blink_payoff": "ETB Payoffs",
}

_STATUS_RANK = {"recommended": 3, "viable": 2, "experimental": 1, "rejected": 0}


class AnalyzeRequestV2(BaseModel):
    collection: list[OwnedCard]
    strategy_filter: str = "All"


class WildcardCostByRarity(BaseModel):
    common: int = 0
    uncommon: int = 0
    rare: int = 0
    mythic: int = 0


class RoleCoverageItem(BaseModel):
    role: str
    target: int
    deck_count: int
    meets_minimum: bool
    meets_preferred: bool


class CommanderRecommendationV2(BaseModel):
    name: str
    color_identity: list[str]
    cmc: float
    rarity: str
    type_line: str
    owned: bool
    strategy_id: str
    strategy_name: str
    strategy_intrinsic_fit: float
    strategy_collection_coverage: float
    build_readiness: float
    wildcard_cost_by_rarity: WildcardCostByRarity
    mana_readiness: float
    strategy_role_coverage: list[RoleCoverageItem]
    commander_owned: bool
    confidence: float
    key_owned: list[str]
    key_missing: list[KeyCard]
    strengths: list[str]
    deficits: list[str]
    deck_quality: float
    collection_readiness: float
    completion_cost_by_rarity: WildcardCostByRarity
    completion_cost_points: int
    commander_wildcard_required: bool
    provisional: bool
    ranking_reason: str


class CraftLeverageCard(BaseModel):
    name: str
    rarity: str
    deck_count: int


class CraftLeverage(BaseModel):
    lands_by_rarity: dict[str, list[CraftLeverageCard]]
    cards_by_rarity: dict[str, list[CraftLeverageCard]]
    total_decks_analyzed: int


class AnalysisResultV2(BaseModel):
    total_unique: int
    total_copies: int
    color_strength: list[ColorStrength]
    type_distribution: dict[str, int]
    role_counts: dict[str, int]
    strongest_colors: list[str]
    summary: str
    strategy_filter: str
    ranking_version: str
    unmatched_cards: list[str]
    analysis_warnings: list[str]
    craft_leverage: CraftLeverage | None = None
    owned_recommendations: list[CommanderRecommendationV2]
    unowned_recommendations: list[CommanderRecommendationV2]
    # Compatibility field for existing clients during the V2 transition.
    recommendations: list[CommanderRecommendationV2]


class _AnalysisGate:
    def __init__(self, max_active: int, max_waiting: int) -> None:
        self.max_active = max_active
        self.max_waiting = max_waiting
        self._active = 0
        self._waiting = 0
        self._condition = threading.Condition()

    def acquire(self, timeout_s: float) -> float:
        started = time.monotonic()
        with self._condition:
            if self._active >= self.max_active:
                if self._waiting >= self.max_waiting:
                    raise HTTPException(
                        status_code=503,
                        detail="Analysis queue is full. Please try again shortly.",
                        headers={"Retry-After": "30"},
                    )
                self._waiting += 1
                try:
                    deadline = started + timeout_s
                    while self._active >= self.max_active:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise HTTPException(
                                status_code=503,
                                detail="Analysis queue wait timed out. Please try again.",
                                headers={"Retry-After": "30"},
                            )
                        self._condition.wait(remaining)
                finally:
                    self._waiting -= 1
            self._active += 1
        return time.monotonic() - started

    def release(self) -> None:
        with self._condition:
            self._active = max(0, self._active - 1)
            self._condition.notify_all()

    def snapshot(self) -> dict[str, int | bool]:
        with self._condition:
            return {
                "active": self._active,
                "waiting": self._waiting,
                "max_active": self.max_active,
                "max_waiting": self.max_waiting,
                "accepting": self._waiting < self.max_waiting,
            }


_analysis_gate = _AnalysisGate(MAX_ACTIVE_ANALYSES, MAX_WAITING_ANALYSES)


def _analysis_slot():
    wait_s = _analysis_gate.acquire(QUEUE_TIMEOUT_S)
    acquired_at = time.monotonic()
    log.info("analysis_slot_acquired wait_s=%.3f", wait_s)
    try:
        yield
    finally:
        duration_s = time.monotonic() - acquired_at
        _analysis_gate.release()
        log.info("analysis_slot_released duration_s=%.3f wait_s=%.3f", duration_s, wait_s)


@router.get("/queue")
def queue_status():
    return _analysis_gate.snapshot()


@dataclass
class _BuiltCandidate:
    recommendation: CommanderRecommendationV2
    missing_cards: list[tuple[str, str, float] | tuple[str, str, float, bool]]


def _compute_craft_leverage(
    candidates: list[_BuiltCandidate],
    top_per_rarity: int = 2,
) -> CraftLeverage | None:
    eligible = [
        candidate for candidate in candidates
        if candidate.recommendation.commander_owned
        and not candidate.recommendation.provisional
    ]
    if not eligible:
        return None

    deck_counts: Counter[str] = Counter()
    aggregate_scores: Counter[str] = Counter()
    card_details: dict[str, tuple[str, bool]] = {}
    valid_rarities = {"common", "uncommon", "rare", "mythic"}
    for candidate in eligible:
        seen: set[str] = set()
        for missing_card in candidate.missing_cards:
            name, rarity, score = missing_card[:3]
            is_land = bool(missing_card[3]) if len(missing_card) == 4 else False
            if rarity not in valid_rarities or name in seen:
                continue
            seen.add(name)
            deck_counts[name] += 1
            aggregate_scores[name] += score
            card_details[name] = (rarity, is_land)

    def ranked_group(want_land: bool) -> dict[str, list[CraftLeverageCard]]:
        grouped: dict[str, list[CraftLeverageCard]] = {}
        for rarity in ("mythic", "rare", "uncommon", "common"):
            names = [
                name for name, (card_rarity, is_land) in card_details.items()
                if card_rarity == rarity and is_land == want_land
            ]
            names.sort(
                key=lambda name: (
                    -deck_counts[name], -aggregate_scores[name], name.casefold()
                )
            )
            if names:
                grouped[rarity] = [
                    CraftLeverageCard(
                        name=name,
                        rarity=rarity,
                        deck_count=deck_counts[name],
                    )
                    for name in names[:top_per_rarity]
                ]
        return grouped

    lands_by_rarity = ranked_group(True)
    cards_by_rarity = ranked_group(False)
    if not lands_by_rarity and not cards_by_rarity:
        return None
    return CraftLeverage(
        lands_by_rarity=lands_by_rarity,
        cards_by_rarity=cards_by_rarity,
        total_decks_analyzed=len(eligible),
    )


def _mana_readiness(cards: list[DeckCard], color_identity: list[str]) -> float:
    n_colors = max(len(color_identity), 1)
    fixing_lands = sum(1 for dc in cards if dc.card["is_land"] and "fixing" in dc.roles)
    ramp_count = sum(1 for dc in cards if not dc.card["is_land"] and "ramp" in dc.roles)
    land_count = sum(1 for dc in cards if dc.card["is_land"])
    ramp_target = {1: 5, 2: 7, 3: 9, 4: 11, 5: 13}.get(n_colors, 7)
    ramp_score = min(ramp_count / max(ramp_target, 1), 1.0)
    if n_colors == 1:
        return round(ramp_score * 100, 1)
    fixing_target = {2: 6, 3: 10, 4: 14, 5: 18}.get(n_colors, 10)
    fixing_score = min(fixing_lands / max(fixing_target, 1), 1.0)
    land_quality = fixing_lands / max(land_count, 1)
    return round((0.4 * fixing_score + 0.3 * land_quality + 0.3 * ramp_score) * 100, 1)


def _wildcard_cost(cards: list[DeckCard]) -> WildcardCostByRarity:
    return WildcardCostByRarity(**deck_wildcard_cost(cards))


def _completion_cost(
    cards: list[DeckCard],
    commander: dict,
    commander_owned: bool,
) -> tuple[WildcardCostByRarity, int]:
    raw_costs = completion_wildcard_cost(cards, commander, commander_owned)
    return WildcardCostByRarity(**raw_costs), wildcard_points(raw_costs)


def _build_readiness(
    cards: list[DeckCard],
    role_target_rows: list[dict],
) -> tuple[float, list[RoleCoverageItem]]:
    counts: dict[str, int] = defaultdict(int)
    for dc in cards:
        for role in dc.roles:
            counts[role] += 1

    items: list[RoleCoverageItem] = []
    weighted_score = 0.0
    total_weight = 0.0
    for row in role_target_rows:
        solver_role = STRATEGY_ROLE_MAP.get(row["role"], row["role"])
        count = counts.get(solver_role, 0)
        preferred = row["preferred_count"]
        minimum = row["min_count"]
        weight = row["weight"]
        meets_preferred = count >= preferred
        meets_minimum = count >= minimum
        items.append(RoleCoverageItem(
            role=row["role"],
            target=preferred,
            deck_count=count,
            meets_minimum=meets_minimum,
            meets_preferred=meets_preferred,
        ))
        total_weight += weight
        if meets_preferred:
            weighted_score += weight
        elif meets_minimum:
            weighted_score += weight * 0.6
    return round(100 * weighted_score / max(total_weight, 0.001), 1), items


def _strengths_deficits(items: list[RoleCoverageItem]) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    deficits: list[str] = []
    for item in items:
        label = _ROLE_DISPLAY.get(item.role, item.role.replace("_", " ").title())
        if item.meets_preferred:
            strengths.append(f"Strong {label} ({item.deck_count}/{item.target})")
        elif not item.meets_minimum:
            deficits.append(f"Needs {label} ({item.deck_count}/{item.target})")
    return strengths, deficits


def _weighted_collection_readiness(
    cards: list[DeckCard],
    strategy_weights: dict[str, float],
) -> float:
    owned_weight = 0.0
    total_weight = 0.0
    for dc in cards:
        if dc.card["is_land"]:
            continue
        weight = max(strategy_weights.get(dc.card["name"], 0.0), 0.20)
        total_weight += weight
        if dc.owned:
            owned_weight += weight
    return round(100 * owned_weight / max(total_weight, 0.001), 1)


def _deck_quality(
    cards: list[DeckCard],
    strategy_weights: dict[str, float],
    role_readiness: float,
    mana_readiness: float,
    confidence: float,
) -> float:
    nonlands = [dc for dc in cards if not dc.card["is_land"]]
    if nonlands:
        card_signal = sum(
            max(strategy_weights.get(dc.card["name"], 0.0), 0.20)
            for dc in nonlands
        ) / len(nonlands)
    else:
        card_signal = 0.0
    quality = (
        0.50 * card_signal * 100
        + 0.25 * role_readiness
        + 0.15 * mana_readiness
        + 0.10 * min(max(confidence, 0.0), 1.0) * 100
    )
    return round(min(max(quality, 0.0), 100.0), 1)


def _normalize_collection(
    collection: list[OwnedCard],
    card_name_index: dict[str, dict],
) -> tuple[set[str], list[str], int]:
    return normalize_collection(collection, card_name_index)


@router.post(
    "",
    response_model=AnalysisResultV2,
    dependencies=[Depends(_analysis_slot)],
)
def analyze_v2(req: AnalyzeRequestV2):
    analysis_started = time.monotonic()
    if req.strategy_filter not in FILTER_TO_MACRO:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown strategy_filter: {req.strategy_filter!r}. "
            f"Valid values: {sorted(FILTER_TO_MACRO)}",
        )
    target_macro = FILTER_TO_MACRO[req.strategy_filter]

    with get_db() as conn:
        all_rows = conn.execute("SELECT * FROM cards ORDER BY name").fetchall()
    all_cards = [dict(row) for row in all_rows]
    cards_by_name = {card["name"]: card for card in all_cards}
    card_name_index = build_card_name_index(all_cards)
    owned_set, unmatched_cards, total_copies = _normalize_collection(
        req.collection, card_name_index
    )
    roles_cache = {card["name"]: infer_roles(card) for card in all_cards}
    owned_cards = [card for card in all_cards if card["name"] in owned_set]
    color_strength = _color_strength(owned_cards)
    strongest = sorted(
        "WUBRG",
        key=lambda color: next(
            cs.owned + cs.rares * 2 + cs.mythics * 3
            for cs in color_strength if cs.color == color
        ),
        reverse=True,
    )
    type_dist = _type_distribution(owned_cards)
    role_counts_all = _role_counts(owned_cards, roles_cache)
    summary = _summary(color_strength, role_counts_all, list(strongest))
    ci_pools = _build_ci_pools(all_cards)
    warnings: list[str] = []

    with strategy_db.get_strategy_db() as s_conn:
        if s_conn is None:
            raise HTTPException(status_code=503, detail="Strategy DB unavailable")
        macro_clause = " AND st.macro_plan = ?" if target_macro else ""
        params = [target_macro] if target_macro else []
        pair_rows = s_conn.execute(
            f"""
            SELECT c.name AS commander_name,
                   c.cmc AS commander_cmc,
                   c.rarity AS commander_rarity,
                   c.type_line AS commander_type,
                   c.color_identity AS commander_ci,
                   c.oracle_id AS commander_oracle_id,
                   cs.strategy_template_id,
                   cs.fit_score,
                   cs.confidence,
                   cs.status,
                   c.arena_legal,
                   st.display_name AS strategy_name,
                   st.macro_plan
            FROM commander_strategies cs
            JOIN cards c ON c.oracle_id = cs.commander_oracle_id
            JOIN strategy_templates st ON st.id = cs.strategy_template_id
            WHERE c.is_commander = 1 {macro_clause}
            ORDER BY c.name, cs.fit_score DESC, cs.strategy_template_id
            """,
            params,
        ).fetchall()
        # oracle_cards contains one representative printing per oracle ID. An
        # Arena commander such as Yuriko may therefore be marked non-Arena when
        # that representative is a paper printing. An imported owned name is
        # direct evidence that Arena supports it, while unowned suggestions
        # still respect the database flag.
        pairs = [
            dict(row) for row in pair_rows
            if row["arena_legal"] or row["commander_name"] in owned_set
        ]

        top_rows = s_conn.execute(
            f"""
            SELECT commander_oracle_id, strategy_template_id,
                   card_name, card_rarity, card_weight
            FROM (
                SELECT csc.commander_oracle_id,
                       csc.strategy_template_id,
                       cc.name AS card_name,
                       cc.rarity AS card_rarity,
                       csc.card_weight,
                       ROW_NUMBER() OVER (
                           PARTITION BY csc.commander_oracle_id, csc.strategy_template_id
                           ORDER BY csc.card_weight DESC, cc.name
                       ) AS rn
                FROM commander_strategy_cards csc
                JOIN cards cc ON cc.oracle_id = csc.card_oracle_id
                JOIN strategy_templates st ON st.id = csc.strategy_template_id
                WHERE cc.is_land = 0 {macro_clause}
            )
            WHERE rn <= {COVERAGE_CARD_LIMIT}
            """,
            params,
        ).fetchall()
        top_by_pair: dict[tuple[str, str], list[tuple[str, str, float]]] = defaultdict(list)
        for row in top_rows:
            top_by_pair[(row["commander_oracle_id"], row["strategy_template_id"])].append(
                (row["card_name"], row["card_rarity"], float(row["card_weight"]))
            )

        scored: list[dict] = []
        for pair in pairs:
            commander_owned = pair["commander_name"] in owned_set
            if not commander_owned and pair["status"] == "rejected":
                continue
            top_cards = top_by_pair.get(
                (pair["commander_oracle_id"], pair["strategy_template_id"]), []
            )
            total_weight = sum(weight for _, _, weight in top_cards)
            owned_weight = sum(
                weight for name, _, weight in top_cards if name in owned_set
            )
            coverage = owned_weight / max(total_weight, 0.001)
            estimated_cost = sum(
                WC_VALUES.get(rarity, 8)
                for name, rarity, _ in top_cards if name not in owned_set
            )
            if not commander_owned:
                estimated_cost += WC_VALUES.get(pair["commander_rarity"], 8)
            pair["top_cards"] = top_cards
            pair["coverage"] = coverage
            pair["estimated_cost"] = estimated_cost
            pair["fast_quality"] = (
                0.65 * pair["fit_score"]
                + 0.20 * pair["confidence"]
                + 0.15 * coverage
            )
            scored.append(pair)

        # One strategy per commander before expensive solver work.
        best_by_commander: dict[str, dict] = {}
        for pair in scored:
            current = best_by_commander.get(pair["commander_name"])
            key = (
                _STATUS_RANK[pair["status"]],
                pair["fast_quality"],
                pair["coverage"],
                -pair["estimated_cost"],
                pair["strategy_template_id"],
            )
            if current is None:
                best_by_commander[pair["commander_name"]] = pair
                continue
            current_key = (
                _STATUS_RANK[current["status"]],
                current["fast_quality"],
                current["coverage"],
                -current["estimated_cost"],
                current["strategy_template_id"],
            )
            if key > current_key:
                best_by_commander[pair["commander_name"]] = pair

        owned_candidates = [
            pair for pair in best_by_commander.values()
            if pair["commander_name"] in owned_set
        ]
        unowned_candidates = [
            pair for pair in best_by_commander.values()
            if pair["commander_name"] not in owned_set
        ]
        owned_candidates.sort(
            key=lambda pair: (
                -_STATUS_RANK[pair["status"]],
                -pair["fast_quality"],
                pair["estimated_cost"],
                pair["commander_name"],
            )
        )
        unowned_candidates.sort(
            key=lambda pair: (
                pair["estimated_cost"],
                -pair["fast_quality"],
                pair["commander_name"],
            )
        )
        finalists = (
            owned_candidates[:FINALISTS_PER_LANE]
            + unowned_candidates[:FINALISTS_PER_LANE]
        )

        role_targets_by_sid: dict[str, list[dict]] = {}
        sw_cache: dict[tuple[str, str], dict[str, float]] = {}
        for pair in finalists:
            sid = pair["strategy_template_id"]
            if sid not in role_targets_by_sid:
                role_targets_by_sid[sid] = [
                    dict(row) for row in s_conn.execute(
                        "SELECT role, min_count, preferred_count, weight "
                        "FROM strategy_role_targets WHERE strategy_template_id = ?",
                        (sid,),
                    ).fetchall()
                ]
            key = (pair["commander_oracle_id"], sid)
            if key not in sw_cache:
                sw_cache[key] = {
                    row["card_name"]: float(row["card_weight"])
                    for row in s_conn.execute(
                        """
                        SELECT cc.name AS card_name, csc.card_weight
                        FROM commander_strategy_cards csc
                        JOIN cards cc ON cc.oracle_id = csc.card_oracle_id
                        WHERE csc.commander_oracle_id = ?
                          AND csc.strategy_template_id = ?
                          AND cc.is_land = 0
                        ORDER BY csc.card_weight DESC, cc.name
                        """,
                        key,
                    ).fetchall()
                }

    def build_candidate(pair: dict) -> _BuiltCandidate | None:
        commander_name = pair["commander_name"]
        commander = cards_by_name.get(commander_name)
        if commander is None:
            return None
        colors = sorted(json.loads(pair["commander_ci"]))
        pool = [
            card for card in ci_pools.get(frozenset(colors), [])
            if card["name"] != commander_name
        ]
        if len(pool) < 50:
            return None
        sid = pair["strategy_template_id"]
        role_rows = role_targets_by_sid.get(sid, [])
        weights = sw_cache.get((pair["commander_oracle_id"], sid), {})
        profile = profile_from_strategy_rows(
            sid, pair["strategy_name"], pair["macro_plan"], role_rows
        )
        result = build_variant(
            commander=commander,
            candidates=pool,
            owned_set=owned_set,
            profile=profile,
            wildcard_budget=None,
            variant="quality",
            time_limit_s=BUILD_TIME_LIMIT_S,
            strategy_weights=weights,
        )
        if result.infeasible or not result.cards:
            return None

        role_readiness, role_coverage = _build_readiness(result.cards, role_rows)
        mana_readiness = _mana_readiness(result.cards, colors)
        collection_readiness = _weighted_collection_readiness(result.cards, weights)
        quality = _deck_quality(
            result.cards, weights, role_readiness, mana_readiness, pair["confidence"]
        )
        commander_owned = commander_name in owned_set
        deck_cost = _wildcard_cost(result.cards)
        completion_cost, completion_points = _completion_cost(
            result.cards, commander, commander_owned
        )
        strengths, deficits = _strengths_deficits(role_coverage)
        top_cards = pair["top_cards"]
        key_owned = [name for name, _, _ in top_cards if name in owned_set][:5]
        key_missing = [
            KeyCard(name=name, rarity=rarity)
            for name, rarity, _ in top_cards if name not in owned_set
        ][:5]
        provisional = pair["status"] == "rejected" or quality < QUALITY_FLOOR
        if commander_owned:
            reason = (
                f"{quality:.0f}% deck quality; {collection_readiness:.0f}% "
                f"of the optimized nonland core already owned"
            )
        else:
            reason = (
                f"{completion_points} wildcard points to complete a "
                f"{quality:.0f}% quality deck"
            )
        recommendation = CommanderRecommendationV2(
            name=commander_name,
            color_identity=colors,
            cmc=pair["commander_cmc"],
            rarity=pair["commander_rarity"],
            type_line=pair["commander_type"],
            owned=commander_owned,
            strategy_id=sid,
            strategy_name=pair["strategy_name"],
            strategy_intrinsic_fit=round(pair["fit_score"], 3),
            strategy_collection_coverage=round(pair["coverage"], 3),
            build_readiness=role_readiness,
            wildcard_cost_by_rarity=deck_cost,
            mana_readiness=mana_readiness,
            strategy_role_coverage=role_coverage,
            commander_owned=commander_owned,
            confidence=round(pair["confidence"], 3),
            key_owned=key_owned,
            key_missing=key_missing,
            strengths=strengths[:4],
            deficits=deficits[:4],
            deck_quality=quality,
            collection_readiness=collection_readiness,
            completion_cost_by_rarity=completion_cost,
            completion_cost_points=completion_points,
            commander_wildcard_required=not commander_owned,
            provisional=provisional,
            ranking_reason=reason,
        )
        missing_cards = [
            (dc.card["name"], dc.card["rarity"], dc.score, bool(dc.card["is_land"]))
            for dc in result.cards
            if not dc.owned
            and dc.wildcard_cost in {"common", "uncommon", "rare", "mythic"}
        ]
        return _BuiltCandidate(
            recommendation=recommendation,
            missing_cards=missing_cards,
        )

    built: list[_BuiltCandidate] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(build_candidate, pair): pair for pair in finalists}
        for future in as_completed(futures):
            pair = futures[future]
            try:
                candidate = future.result()
            except Exception as exc:
                message = (
                    f"Could not evaluate {pair['commander_name']} / "
                    f"{pair['strategy_template_id']}: {exc}"
                )
                log.exception(message)
                warnings.append(message)
                continue
            if candidate is not None:
                built.append(candidate)

    craft_leverage = _compute_craft_leverage(built)
    recommendations = [candidate.recommendation for candidate in built]
    owned_results = [rec for rec in recommendations if rec.commander_owned]
    unowned_results = [rec for rec in recommendations if not rec.commander_owned]
    owned_results.sort(
        key=lambda rec: (
            rec.provisional,
            -(0.60 * rec.deck_quality + 0.40 * rec.collection_readiness),
            rec.completion_cost_points,
            -rec.deck_quality,
            -rec.collection_readiness,
            rec.name,
        )
    )
    qualified = [rec for rec in unowned_results if not rec.provisional]
    provisional = [rec for rec in unowned_results if rec.provisional]
    qualified.sort(
        key=lambda rec: (
            rec.completion_cost_points,
            -rec.deck_quality,
            -rec.collection_readiness,
            rec.name,
        )
    )
    provisional.sort(
        key=lambda rec: (
            -rec.deck_quality,
            rec.completion_cost_points,
            -rec.collection_readiness,
            rec.name,
        )
    )
    owned_results = owned_results[:OWNED_RESULTS_LIMIT]
    unowned_results = (qualified + provisional)[:UNOWNED_RESULTS_LIMIT]
    combined = owned_results + unowned_results
    log.info(
        "analysis_complete filter=%s owned=%d unowned=%d warnings=%d duration_s=%.3f",
        req.strategy_filter,
        len(owned_results),
        len(unowned_results),
        len(warnings),
        time.monotonic() - analysis_started,
    )

    return AnalysisResultV2(
        total_unique=len(owned_set),
        total_copies=total_copies,
        color_strength=color_strength,
        type_distribution=type_dist,
        role_counts=role_counts_all,
        strongest_colors=list(strongest[:3]),
        summary=summary,
        strategy_filter=req.strategy_filter,
        ranking_version=RANKING_VERSION,
        unmatched_cards=unmatched_cards,
        analysis_warnings=warnings,
        craft_leverage=craft_leverage,
        owned_recommendations=owned_results,
        unowned_recommendations=unowned_results,
        recommendations=combined,
    )
