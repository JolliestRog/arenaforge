"""POST /analyze/v2 — Collection Analysis V2.

Replaces V1's top-300 pre-filter with:
  1. Hard-gate: strategy-DB pairs matching the requested strategy_filter.
  2. Fast-score ALL pairs in the filter (intrinsic_fit × 0.70 + collection_coverage × 0.30).
  3. CP-SAT wildcard-variant build for top-15 finalists (parallel, deterministic 1-worker).
  4. Return up to 10 results with fully separated score components.

Score components returned (never combined into an opaque score):
  build_readiness        — 0-100, weighted role-target satisfaction in the built 99-card deck
  wildcard_cost_by_rarity — common/uncommon/rare/mythic wildcards needed to complete the deck
  mana_readiness         — 0-100, fixing + ramp adequacy vs commander CI complexity
  strategy_role_coverage — per-role target/deck_count breakdown
  commander_owned        — bool
  confidence             — strategy DB confidence value 0-1
"""

from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import strategy_db
from db import get_db
from routers.analyze import (
    ColorStrength, KeyCard, OwnedCard,
    _build_ci_pools, _color_strength, _role_counts, _summary, _type_distribution,
)
from solver.model import build_variant, DeckCard
from solver.profiles import Profile, PROFILES, RoleTarget
from solver.roles import infer_roles

# Legacy commanders not in strategy DB — injected when owned regardless of filter.
# Maps commander name → (profile_id, macro_plan_for_filter_matching)
_LEGACY_COMMANDERS: dict[str, tuple[str, str]] = {
    "A-Satoru Umezawa":           ("satoru_toolbox", "tempo"),
    "Yuriko, the Tiger's Shadow": ("yuriko_tempo",   "tempo"),
    "Talion, the Kindly Lord":    ("talion_control",  "control"),
    "A-Yuffie Kisaragi":          ("yuffie_ninjutsu", "tempo"),
}

router = APIRouter(prefix="/analyze/v2", tags=["analyze-v2"])

# ── Constants ───────────────────────────────────────────────────────────────────

COVERAGE_CARD_LIMIT = 60
N_FINALISTS = 15
N_RESULTS = 10
BUILD_TIME_LIMIT_S = 4.0
MAX_WORKERS = 4

FILTER_TO_MACRO: dict[str, str | None] = {
    "All":      None,
    "Control":  "control",
    "Tempo":    "tempo",
    "Aggro":    "aggro",
    "Midrange": "midrange",
    "Ramp":     "ramp",
}

_STRATEGY_ROLE_MAP: dict[str, str] = {
    "draw":              "draw",
    "ramp":              "ramp",
    "counterspell":      "counterspell",
    "protection":        "protection",
    "finisher":          "finisher",
    "selection":         "selection",
    "recursion":         "recursion",
    "removal":           "creature_removal",
    "board_wipe":        "sweeper",
    "token_maker":       "etb_payoff",
    "artifact_payoff":   "engine",
    "enchantment_payoff":"engine",
    "tap_enabler":       "evasive_enabler",
    "attack_payoff":     "engine",
    "land_payoff":       "engine",
    "sacrifice_outlet":  "engine",
    "death_payoff":      "engine",
    "graveyard_filler":  "engine",
    "counters_enabler":  "engine",
    "counters_payoff":   "engine",
    "lifegain_enabler":  "engine",
    "lifegain_payoff":   "engine",
    "anthem":            "finisher",
    "untap_denial":      "interaction",
}

_LAND_TARGET_BY_MACRO: dict[str, int] = {
    "tempo": 34, "aggro": 34, "control": 38, "ramp": 38, "midrange": 36,
}

_ROLE_DISPLAY: dict[str, str] = {
    "ramp":              "Ramp",
    "draw":              "Card Draw",
    "removal":           "Removal",
    "counterspell":      "Counterspells",
    "board_wipe":        "Board Wipes",
    "finisher":          "Finishers",
    "protection":        "Protection",
    "token_maker":       "Token Production",
    "sacrifice_outlet":  "Sacrifice Outlets",
    "death_payoff":      "Death Payoffs",
    "recursion":         "Recursion",
    "graveyard_filler":  "Graveyard Filling",
    "attack_payoff":     "Attack Payoffs",
    "enchantment_payoff":"Enchantment Payoffs",
    "artifact_payoff":   "Artifact Payoffs",
    "counters_enabler":  "Counter Enablers",
    "counters_payoff":   "Counter Payoffs",
    "lifegain_enabler":  "Lifegain Enablers",
    "lifegain_payoff":   "Lifegain Payoffs",
    "land_payoff":       "Land Payoffs",
    "tap_enabler":       "Tap Enablers",
    "untap_denial":      "Untap Denial",
    "anthem":            "Anthems",
    "selection":         "Card Selection",
}


# ── Request / Response Models ────────────────────────────────────────────────────

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


class AnalysisResultV2(BaseModel):
    total_unique: int
    total_copies: int
    color_strength: list[ColorStrength]
    type_distribution: dict[str, int]
    role_counts: dict[str, int]
    strongest_colors: list[str]
    summary: str
    strategy_filter: str
    recommendations: list[CommanderRecommendationV2]


# ── Scoring helpers ──────────────────────────────────────────────────────────────

def _profile_from_rows(
    strategy_id: str,
    display_name: str,
    macro_plan: str,
    role_target_rows: list[dict],
) -> Profile:
    role_targets: dict[str, RoleTarget] = {}
    role_weights: dict[str, float] = {}
    for row in role_target_rows:
        solver_role = _STRATEGY_ROLE_MAP.get(row["role"], row["role"])
        role_targets[solver_role] = RoleTarget(
            min=row["min_count"], preferred=row["preferred_count"]
        )
        role_weights[solver_role] = row["weight"] * 10

    land_target = _LAND_TARGET_BY_MACRO.get(macro_plan, 36)
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


def _mana_readiness(cards: list[DeckCard], color_identity: list[str]) -> float:
    n_colors = max(len(color_identity), 1)
    fixing_lands = sum(1 for dc in cards if dc.card["is_land"] and "fixing" in dc.roles)
    ramp_count   = sum(1 for dc in cards if not dc.card["is_land"] and "ramp" in dc.roles)
    land_count   = sum(1 for dc in cards if dc.card["is_land"])

    ramp_target = {1: 5, 2: 7, 3: 9, 4: 11, 5: 13}.get(n_colors, 7)
    ramp_score  = min(ramp_count / max(ramp_target, 1), 1.0)

    if n_colors == 1:
        return round(ramp_score * 100, 1)

    fixing_target = {2: 6, 3: 10, 4: 14, 5: 18}.get(n_colors, 10)
    fixing_score  = min(fixing_lands / max(fixing_target, 1), 1.0)
    land_quality  = fixing_lands / max(land_count, 1)

    return round((0.4 * fixing_score + 0.3 * land_quality + 0.3 * ramp_score) * 100, 1)


def _wildcard_cost(cards: list[DeckCard]) -> WildcardCostByRarity:
    cost = WildcardCostByRarity()
    for dc in cards:
        if dc.wildcard_cost == "common":    cost.common += 1
        elif dc.wildcard_cost == "uncommon":cost.uncommon += 1
        elif dc.wildcard_cost == "rare":    cost.rare += 1
        elif dc.wildcard_cost == "mythic":  cost.mythic += 1
    return cost


def _build_readiness(
    cards: list[DeckCard],
    role_target_rows: list[dict],
) -> tuple[float, list[RoleCoverageItem]]:
    deck_role_counts: dict[str, int] = defaultdict(int)
    for dc in cards:
        for role in dc.roles:
            deck_role_counts[role] += 1

    items: list[RoleCoverageItem] = []
    total_weight  = 0.0
    weighted_score = 0.0

    for row in role_target_rows:
        solver_role = _STRATEGY_ROLE_MAP.get(row["role"], row["role"])
        count     = deck_role_counts.get(solver_role, 0)
        preferred = row["preferred_count"]
        min_count = row["min_count"]
        weight    = row["weight"]

        meets_preferred = count >= preferred
        meets_minimum   = count >= min_count

        items.append(RoleCoverageItem(
            role=row["role"],
            target=preferred,
            deck_count=count,
            meets_minimum=meets_minimum,
            meets_preferred=meets_preferred,
        ))
        total_weight  += weight
        if meets_preferred:
            weighted_score += weight * 1.0
        elif meets_minimum:
            weighted_score += weight * 0.6

    readiness = (weighted_score / max(total_weight, 0.001)) * 100
    return round(readiness, 1), items


def _profile_role_target_rows(profile: Profile) -> list[dict]:
    """Convert a hardcoded Profile's role_targets to the same format as strategy DB rows."""
    rows = []
    for role, rt in profile.role_targets.items():
        rows.append({
            "role": role,
            "min_count": rt.min,
            "preferred_count": rt.preferred,
            "weight": profile.role_weights.get(role, 5.0) / 10.0,
        })
    return rows


def _build_legacy_rec(
    cmdr_name: str,
    profile_id: str,
    owned_set: set[str],
    cards_by_name: dict[str, dict],
    ci_pools: dict,
    roles_cache: dict[str, list[str]],
) -> CommanderRecommendationV2 | None:
    """Build a single recommendation for a hardcoded-profile legacy commander."""
    profile = PROFILES.get(profile_id)
    if profile is None:
        return None
    cmdr_card = cards_by_name.get(cmdr_name)
    if cmdr_card is None:
        return None

    cmdr_ci = sorted(json.loads(cmdr_card["color_identity"]))
    ci_key = frozenset(cmdr_ci)
    pool = [c for c in ci_pools.get(ci_key, []) if c["name"] != cmdr_name]
    if len(pool) < 50:
        return None

    role_target_rows = _profile_role_target_rows(profile)

    result = build_variant(
        commander=cmdr_card,
        candidates=pool,
        owned_set=owned_set,
        profile=profile,
        wildcard_budget=None,
        variant="wildcard",
        time_limit_s=BUILD_TIME_LIMIT_S,
        strategy_weights=None,
    )
    if not result.cards:
        return None

    # Compute key_owned / key_missing from pool (top 30 by score, non-land)
    scored = [
        (c, sum(roles_cache.get(c["name"], []).__contains__(r) * profile.role_weights.get(r, 1.0)
                for r in profile.priority_roles))
        for c in pool if not c["is_land"]
    ]
    scored.sort(key=lambda x: -x[1])
    top30 = scored[:30]
    key_owned   = [c["name"] for c, _ in top30 if c["name"] in owned_set][:5]
    key_missing = [KeyCard(name=c["name"], rarity=c["rarity"])
                   for c, _ in top30 if c["name"] not in owned_set][:5]

    build_ready, role_coverage = _build_readiness(result.cards, role_target_rows)
    wc_cost    = _wildcard_cost(result.cards)
    mana_ready = _mana_readiness(result.cards, cmdr_ci)
    strengths, deficits = _strengths_deficits(role_coverage)

    return CommanderRecommendationV2(
        name=cmdr_name,
        color_identity=cmdr_ci,
        cmc=cmdr_card["cmc"],
        rarity=cmdr_card["rarity"],
        type_line=cmdr_card["type_line"],
        owned=cmdr_name in owned_set,
        strategy_id=profile_id,
        strategy_name=profile.display_name,
        strategy_intrinsic_fit=1.0,
        strategy_collection_coverage=len(key_owned) / max(len(top30), 1),
        build_readiness=build_ready,
        wildcard_cost_by_rarity=wc_cost,
        mana_readiness=mana_ready,
        strategy_role_coverage=role_coverage,
        commander_owned=cmdr_name in owned_set,
        confidence=1.0,
        key_owned=key_owned,
        key_missing=key_missing,
        strengths=strengths[:4],
        deficits=deficits[:4],
    )


def _strengths_deficits(
    role_coverage: list[RoleCoverageItem],
) -> tuple[list[str], list[str]]:
    strengths, deficits = [], []
    for item in role_coverage:
        label = _ROLE_DISPLAY.get(item.role, item.role.replace("_", " ").title())
        if item.meets_preferred:
            strengths.append(f"Strong {label} ({item.deck_count}/{item.target})")
        elif not item.meets_minimum:
            deficits.append(f"Needs {label} ({item.deck_count}/{item.target})")
    return strengths, deficits


# ── Endpoint ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=AnalysisResultV2)
def analyze_v2(req: AnalyzeRequestV2):
    strategy_filter = req.strategy_filter
    if strategy_filter not in FILTER_TO_MACRO:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown strategy_filter: {strategy_filter!r}. "
                   f"Valid values: {sorted(FILTER_TO_MACRO)}",
        )
    target_macro = FILTER_TO_MACRO[strategy_filter]

    owned_set    = {c.name for c in req.collection if c.count >= 1}
    total_unique = len(owned_set)
    total_copies = sum(c.count for c in req.collection)

    # Load cards once — all computations share this snapshot.
    with get_db() as conn:
        all_rows = conn.execute("SELECT * FROM cards ORDER BY name").fetchall()
    all_cards:    list[dict] = [dict(r) for r in all_rows]
    cards_by_name: dict[str, dict] = {c["name"]: c for c in all_cards}
    roles_cache:  dict[str, list[str]] = {c["name"]: infer_roles(c) for c in all_cards}

    owned_cards   = [c for c in all_cards if c["name"] in owned_set]
    color_strength = _color_strength(owned_cards)
    strongest = sorted(
        "WUBRG",
        key=lambda col: next(
            cs.owned + cs.rares * 2 + cs.mythics * 3
            for cs in color_strength if cs.color == col
        ),
        reverse=True,
    )
    type_dist      = _type_distribution(owned_cards)
    role_counts_all = _role_counts(owned_cards, roles_cache)
    summary        = _summary(color_strength, role_counts_all, list(strongest))
    ci_pools       = _build_ci_pools(all_cards)

    # ── Phase 1: fetch ALL strategy DB pairs in the requested filter ─────────────
    with strategy_db.get_strategy_db() as s_conn:
        if s_conn is None:
            raise HTTPException(status_code=503, detail="Strategy DB unavailable")

        macro_clause = " AND st.macro_plan = ?" if target_macro else ""
        macro_params = [target_macro] if target_macro else []

        pair_rows = s_conn.execute(
            f"""
            SELECT c.name           AS commander_name,
                   c.cmc            AS commander_cmc,
                   c.rarity         AS commander_rarity,
                   c.type_line      AS commander_type,
                   c.color_identity AS commander_ci,
                   c.oracle_id      AS commander_oracle_id,
                   cs.strategy_template_id,
                   cs.fit_score,
                   cs.confidence,
                   st.display_name  AS strategy_name,
                   st.macro_plan
            FROM commander_strategies cs
            JOIN cards c              ON c.oracle_id  = cs.commander_oracle_id
            JOIN strategy_templates st ON st.id        = cs.strategy_template_id
            WHERE cs.status IN ('recommended', 'viable', 'experimental')
              AND c.is_commander = 1
              AND c.arena_legal  = 1
              {macro_clause}
            ORDER BY cs.fit_score DESC
            """,
            macro_params,
        ).fetchall()

        pairs = [dict(r) for r in pair_rows]
        if not pairs:
            return AnalysisResultV2(
                total_unique=total_unique,
                total_copies=total_copies,
                color_strength=color_strength,
                type_distribution=type_dist,
                role_counts=role_counts_all,
                strongest_colors=list(strongest[:3]),
                summary=summary,
                strategy_filter=strategy_filter,
                recommendations=[],
            )

        # ── Batch-fetch top-COVERAGE_CARD_LIMIT cards per pair ────────────────
        # Single SQL call using ROW_NUMBER() window function (SQLite ≥ 3.25).
        top_card_rows = s_conn.execute(
            f"""
            SELECT commander_oracle_id, strategy_template_id, card_name, card_rarity
            FROM (
                SELECT csc.commander_oracle_id,
                       csc.strategy_template_id,
                       cc.name  AS card_name,
                       cc.rarity AS card_rarity,
                       ROW_NUMBER() OVER (
                           PARTITION BY csc.commander_oracle_id, csc.strategy_template_id
                           ORDER BY csc.card_weight DESC
                       ) AS rn
                FROM commander_strategy_cards csc
                JOIN cards cc ON cc.oracle_id = csc.card_oracle_id
                JOIN commander_strategies cs
                     ON cs.commander_oracle_id  = csc.commander_oracle_id
                    AND cs.strategy_template_id = csc.strategy_template_id
                JOIN strategy_templates st ON st.id = cs.strategy_template_id
                WHERE cs.status IN ('recommended', 'viable', 'experimental')
                  AND cc.is_land = 0
                  {macro_clause}
            )
            WHERE rn <= {COVERAGE_CARD_LIMIT}
            """,
            macro_params,
        ).fetchall()

        # Group into dict: (oid, sid) → [(card_name, card_rarity), ...]
        top_cards_by_pair: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
        for row in top_card_rows:
            key = (row["commander_oracle_id"], row["strategy_template_id"])
            top_cards_by_pair[key].append((row["card_name"], row["card_rarity"]))

        # ── Fast-score all pairs (no CP-SAT here) ─────────────────────────────
        scored_pairs: list[tuple[float, dict, list[str], list[KeyCard], float]] = []
        for pair in pairs:
            oid = pair["commander_oracle_id"]
            sid = pair["strategy_template_id"]
            top_cards = top_cards_by_pair.get((oid, sid), [])

            key_owned   = [n for n, _ in top_cards if n in owned_set]
            key_missing = [KeyCard(name=n, rarity=r) for n, r in top_cards if n not in owned_set]
            coverage    = len(key_owned) / max(len(top_cards), 1)
            fast_score  = 0.70 * pair["fit_score"] + 0.30 * coverage

            scored_pairs.append((fast_score, pair, key_owned, key_missing, coverage))

        # Sort descending by fast_score, take top-N finalists for CP-SAT phase
        scored_pairs.sort(key=lambda t: -t[0])
        finalists = scored_pairs[:N_FINALISTS]

        # ── Fetch role targets for finalist strategies ─────────────────────────
        finalist_sids = {pair["strategy_template_id"] for _, pair, _, _, _ in finalists}
        role_targets_by_sid: dict[str, list[dict]] = {}
        for sid in finalist_sids:
            rows = s_conn.execute(
                "SELECT role, min_count, preferred_count, weight "
                "FROM strategy_role_targets WHERE strategy_template_id = ?",
                (sid,),
            ).fetchall()
            role_targets_by_sid[sid] = [dict(r) for r in rows]

        # ── Fetch card weights for finalist pairs ──────────────────────────────
        finalist_keys = {
            (pair["commander_oracle_id"], pair["strategy_template_id"])
            for _, pair, _, _, _ in finalists
        }
        sw_cache: dict[tuple[str, str], dict[str, float]] = {}
        for oid, sid in finalist_keys:
            rows = s_conn.execute(
                """
                SELECT cc.name AS card_name, csc.card_weight
                FROM commander_strategy_cards csc
                JOIN cards cc ON cc.oracle_id = csc.card_oracle_id
                WHERE csc.commander_oracle_id  = ?
                  AND csc.strategy_template_id = ?
                  AND cc.is_land = 0
                ORDER BY csc.card_weight DESC
                """,
                (oid, sid),
            ).fetchall()
            sw_cache[(oid, sid)] = {r["card_name"]: r["card_weight"] for r in rows}

    # ── Phase 2: CP-SAT wildcard-variant build for each finalist ─────────────────
    # num_workers=1 for determinism; parallel via Python threads.

    def build_finalist(
        _fast_score: float,
        pair: dict,
        key_owned_list: list[str],
        key_missing_list: list[KeyCard],
        coverage: float,
    ) -> CommanderRecommendationV2 | None:
        cmdr_name = pair["commander_name"]
        cmdr_ci   = sorted(json.loads(pair["commander_ci"]))
        ci_key    = frozenset(cmdr_ci)

        pool = [c for c in ci_pools.get(ci_key, []) if c["name"] != cmdr_name]
        if len(pool) < 50:
            return None

        cmdr_card = cards_by_name.get(cmdr_name)
        if cmdr_card is None:
            return None

        sid              = pair["strategy_template_id"]
        role_target_rows = role_targets_by_sid.get(sid, [])
        oid              = pair["commander_oracle_id"]
        strategy_weights = sw_cache.get((oid, sid), {})

        profile = _profile_from_rows(
            sid, pair["strategy_name"], pair["macro_plan"], role_target_rows,
        )

        result = build_variant(
            commander=cmdr_card,
            candidates=pool,
            owned_set=owned_set,
            profile=profile,
            wildcard_budget=None,
            variant="wildcard",
            time_limit_s=BUILD_TIME_LIMIT_S,
            strategy_weights=strategy_weights,
        )

        if result.infeasible or not result.cards:
            return None

        build_ready, role_coverage = _build_readiness(result.cards, role_target_rows)
        wc_cost    = _wildcard_cost(result.cards)
        mana_ready = _mana_readiness(result.cards, cmdr_ci)
        strengths, deficits = _strengths_deficits(role_coverage)

        return CommanderRecommendationV2(
            name=cmdr_name,
            color_identity=cmdr_ci,
            cmc=pair["commander_cmc"],
            rarity=pair["commander_rarity"],
            type_line=pair["commander_type"],
            owned=cmdr_name in owned_set,
            strategy_id=sid,
            strategy_name=pair["strategy_name"],
            strategy_intrinsic_fit=round(pair["fit_score"], 3),
            strategy_collection_coverage=round(coverage, 3),
            build_readiness=build_ready,
            wildcard_cost_by_rarity=wc_cost,
            mana_readiness=mana_ready,
            strategy_role_coverage=role_coverage,
            commander_owned=cmdr_name in owned_set,
            confidence=round(pair.get("confidence", 0.5), 3),
            key_owned=key_owned_list[:5],
            key_missing=key_missing_list[:5],
            strengths=strengths[:4],
            deficits=deficits[:4],
        )

    results: list[CommanderRecommendationV2] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(build_finalist, fs, pair, ko, km, cov): idx
            for idx, (fs, pair, ko, km, cov) in enumerate(finalists)
        }
        for future in as_completed(futures):
            try:
                rec = future.result()
                if rec is not None:
                    results.append(rec)
            except Exception:
                pass

    # Sort: build_readiness descending, break ties with strategy_intrinsic_fit
    results.sort(key=lambda r: (-r.build_readiness, -r.strategy_intrinsic_fit))
    results = results[:N_RESULTS]

    # ── Inject legacy commanders if owned and not already present ─────────────
    # Satoru, Yuriko, Talion, Yuffie have hardcoded profiles outside the strategy DB.
    # They always appear in recommendations when the user owns them.
    already_in = {r.name for r in results}
    for legacy_name, (profile_id, macro) in _LEGACY_COMMANDERS.items():
        if legacy_name not in owned_set:
            continue
        if legacy_name in already_in:
            continue
        # Only inject when filter matches the commander's macro or filter is "All"
        if target_macro is not None and target_macro != macro:
            continue
        rec = _build_legacy_rec(
            legacy_name, profile_id, owned_set,
            cards_by_name, ci_pools, roles_cache,
        )
        if rec is not None:
            results.append(rec)
            already_in.add(legacy_name)

    # Re-sort after injection — owned commanders float higher
    results.sort(key=lambda r: (not r.commander_owned, -r.build_readiness, -r.strategy_intrinsic_fit))

    return AnalysisResultV2(
        total_unique=total_unique,
        total_copies=total_copies,
        color_strength=color_strength,
        type_distribution=type_dist,
        role_counts=role_counts_all,
        strongest_colors=list(strongest[:3]),
        summary=summary,
        strategy_filter=strategy_filter,
        recommendations=results,
    )
