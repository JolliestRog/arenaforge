"""POST /analyze — collection profile and commander recommendations."""

import json
from collections import defaultdict
from itertools import combinations

from fastapi import APIRouter
from pydantic import BaseModel

from db import get_db
from solver.roles import infer_roles
from solver.profiles import PROFILES
import strategy_db

router = APIRouter(prefix="/analyze", tags=["analyze"])

COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
GENERIC_PROFILE_IDS = {"tempo", "control", "midrange", "value"}

# Top-N strategy cards used to measure collection coverage
COVERAGE_CARD_LIMIT = 60


# ── Request / response models ──────────────────────────────────────────────────

class OwnedCard(BaseModel):
    name: str
    count: int


class ColorStrength(BaseModel):
    color: str
    label: str
    owned: int
    rares: int
    mythics: int


class CommanderRecommendation(BaseModel):
    name: str
    color_identity: list[str]
    cmc: float
    rarity: str
    type_line: str
    owned: bool
    profile_id: str
    profile_name: str
    collection_fit: float
    owned_pct: float
    owned_pool: int
    total_pool: int
    role_coverage: dict[str, int]
    score_breakdown: dict[str, float]
    key_owned: list[str]
    key_missing: list[str]


class AnalysisResult(BaseModel):
    total_unique: int
    total_copies: int
    color_strength: list[ColorStrength]
    type_distribution: dict[str, int]
    role_counts: dict[str, int]
    strongest_colors: list[str]
    summary: str
    recommendations: list[CommanderRecommendation]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _color_strength(owned_cards: list[dict]) -> list[ColorStrength]:
    counts: dict[str, int] = defaultdict(int)
    rares: dict[str, int] = defaultdict(int)
    mythics: dict[str, int] = defaultdict(int)
    for c in owned_cards:
        ci = json.loads(c["color_identity"])
        for color in ci:
            counts[color] += 1
            if c["rarity"] == "rare":     rares[color] += 1
            elif c["rarity"] == "mythic": mythics[color] += 1
    return [
        ColorStrength(color=col, label=COLOR_NAMES[col],
                      owned=counts.get(col, 0),
                      rares=rares.get(col, 0),
                      mythics=mythics.get(col, 0))
        for col in "WUBRG"
    ]


def _type_distribution(owned_cards: list[dict]) -> dict[str, int]:
    dist: dict[str, int] = defaultdict(int)
    for c in owned_cards:
        tl = c["type_line"] or ""
        if "Land" in tl:              dist["Land"] += 1
        elif "Creature" in tl:        dist["Creature"] += 1
        elif "Instant" in tl:         dist["Instant"] += 1
        elif "Sorcery" in tl:         dist["Sorcery"] += 1
        elif "Enchantment" in tl:     dist["Enchantment"] += 1
        elif "Artifact" in tl:        dist["Artifact"] += 1
        elif "Planeswalker" in tl:    dist["Planeswalker"] += 1
        else:                          dist["Other"] += 1
    return dict(dist)


def _role_counts(cards: list[dict], roles_cache: dict[str, list[str]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for c in cards:
        for role in roles_cache[c["name"]]:
            counts[role] += 1
    return dict(counts)


def _summary(color_strength: list[ColorStrength], role_counts: dict[str, int], strongest: list[str]) -> str:
    color_labels = [COLOR_NAMES[c] for c in strongest[:2]]
    color_str = " and ".join(color_labels) if color_labels else "multiple colors"

    assets = []
    if role_counts.get("draw", 0) >= 25:             assets.append("card draw")
    if role_counts.get("interaction", 0) >= 20:      assets.append("interaction")
    if role_counts.get("ramp", 0) >= 12:             assets.append("ramp")
    if role_counts.get("creature_removal", 0) >= 15: assets.append("removal")
    if role_counts.get("tutor", 0) >= 10:            assets.append("tutors")
    if role_counts.get("evasive_enabler", 0) >= 10:  assets.append("evasive creatures")

    asset_str = f", with strong {', '.join(assets[:3])}" if assets else ""

    draw = role_counts.get("draw", 0)
    interaction = role_counts.get("interaction", 0) + role_counts.get("creature_removal", 0)
    evasive = role_counts.get("evasive_enabler", 0)

    if evasive >= 10 and interaction >= 20:   archetype = "tempo and control"
    elif interaction >= 25 and draw >= 25:    archetype = "control"
    elif role_counts.get("ramp", 0) >= 12:   archetype = "midrange and ramp"
    else:                                      archetype = "value and interaction"

    return (
        f"Your collection is strongest in {color_str}{asset_str}. "
        f"You are best set up for {archetype} strategies."
    )


def _build_ci_pools(all_cards: list[dict]) -> dict[frozenset, list[dict]]:
    pools: dict[frozenset, list[dict]] = {}
    for r in range(6):
        for combo in combinations("WUBRG", r):
            key = frozenset(combo)
            pools[key] = [
                c for c in all_cards
                if frozenset(json.loads(c["color_identity"])).issubset(key)
            ]
    return pools


# ── Strategy DB scoring ────────────────────────────────────────────────────────

def _fetch_strategy_scores(
    candidate_names: list[str],
    owned_set: set[str],
    s_conn,
) -> dict[str, dict]:
    """
    For each candidate commander, fetch their best recommended/viable strategy
    and measure what fraction of the top COVERAGE_CARD_LIMIT strategy cards
    the user owns.

    Returns {commander_name: {strategy_id, strategy_name, intrinsic_fit,
                               collection_coverage, key_owned, key_missing}}
    """
    if not candidate_names:
        return {}

    placeholders = ",".join("?" * len(candidate_names))
    rows = s_conn.execute(
        f"""
        SELECT c.name       AS commander_name,
               cs.commander_oracle_id,
               cs.strategy_template_id,
               cs.fit_score,
               cs.status,
               st.display_name AS strategy_name
        FROM commander_strategies cs
        JOIN cards c  ON c.oracle_id  = cs.commander_oracle_id
        JOIN strategy_templates st ON st.id = cs.strategy_template_id
        WHERE c.name IN ({placeholders})
          AND cs.status IN ('recommended', 'viable', 'experimental')
        ORDER BY c.name, cs.fit_score DESC
        """,
        candidate_names,
    ).fetchall()

    # Take only the best strategy per commander
    best: dict[str, dict] = {}
    for row in rows:
        name = row["commander_name"]
        if name not in best:
            best[name] = dict(row)

    result: dict[str, dict] = {}
    for cmdr_name, strat in best.items():
        card_rows = s_conn.execute(
            """
            SELECT cc.name AS card_name, sc.card_weight
            FROM commander_strategy_cards sc
            JOIN cards cc ON cc.oracle_id = sc.card_oracle_id
            WHERE sc.commander_oracle_id = ?
              AND sc.strategy_template_id = ?
              AND cc.is_land = 0
            ORDER BY sc.card_weight DESC
            LIMIT ?
            """,
            (strat["commander_oracle_id"], strat["strategy_template_id"], COVERAGE_CARD_LIMIT),
        ).fetchall()

        top_cards = [r["card_name"] for r in card_rows]
        key_owned   = [n for n in top_cards if n in owned_set]
        key_missing = [n for n in top_cards if n not in owned_set]
        coverage = len(key_owned) / max(len(top_cards), 1)

        result[cmdr_name] = {
            "strategy_id":          strat["strategy_template_id"],
            "strategy_name":        strat["strategy_name"],
            "intrinsic_fit":        strat["fit_score"],
            "collection_coverage":  coverage,
            "key_owned":            key_owned[:5],
            "key_missing":          key_missing[:5],
        }

    return result


# ── Commander scoring ──────────────────────────────────────────────────────────

def _score_commander(
    cmdr: dict,
    ci_pools: dict[frozenset, list[dict]],
    owned_set: set[str],
    roles_cache: dict[str, list[str]],
    strategy_data: dict | None,
) -> CommanderRecommendation | None:
    ci_key = frozenset(json.loads(cmdr["color_identity"]))
    pool = [c for c in ci_pools[ci_key] if c["name"] != cmdr["name"]]
    if len(pool) < 50:
        return None

    owned_pool = [c for c in pool if c["name"] in owned_set]
    owned_pct  = 100 * len(owned_pool) / len(pool)

    owned_role_counts: dict[str, int] = defaultdict(int)
    for c in owned_pool:
        for role in roles_cache[c["name"]]:
            owned_role_counts[role] += 1

    # Always compute legacy score as a floor
    specific = [p for p in PROFILES.values()
                if p.commander == cmdr["name"] and p.id not in GENERIC_PROFILE_IDS]
    profile = specific[0] if specific else PROFILES["midrange"]

    role_score = 0.0
    coverage_score = 0.0
    for role, target in profile.role_targets.items():
        count = owned_role_counts.get(role, 0)
        sat = min(count / max(target.preferred, 1), 1.5)
        role_score += sat * profile.role_weights.get(role, 1)
        if count >= target.preferred: coverage_score += 2
        elif count >= target.min:     coverage_score += 1

    breadth_score = owned_pct * 0.3
    high_rarity = sum(1 for c in owned_pool if c["rarity"] in ("rare", "mythic") and not c["is_land"])
    rarity_score = min(high_rarity * 0.5, 15.0)
    legacy_score = min(role_score * 8 + coverage_score * 4 + breadth_score + rarity_score, 60.0)

    if strategy_data:
        # Strategy-DB path: 70% oracle-text alignment, 30% collection coverage.
        # Take max(strategy_score, legacy_score) so the DB never hurts a commander's ranking.
        intrinsic  = strategy_data["intrinsic_fit"]
        coverage   = strategy_data["collection_coverage"]
        strat_score = min((0.70 * intrinsic + 0.30 * coverage) * 100, 100.0)
        total = max(strat_score, legacy_score)

        return CommanderRecommendation(
            name=cmdr["name"],
            color_identity=sorted(json.loads(cmdr["color_identity"])),
            cmc=cmdr["cmc"],
            rarity=cmdr["rarity"],
            type_line=cmdr["type_line"],
            owned=cmdr["name"] in owned_set,
            profile_id=strategy_data["strategy_id"],
            profile_name=strategy_data["strategy_name"],
            collection_fit=round(total, 1),
            owned_pct=round(owned_pct, 1),
            owned_pool=len(owned_pool),
            total_pool=len(pool),
            role_coverage=dict(owned_role_counts),
            score_breakdown={
                "strategy_alignment":  round(intrinsic * 70, 1),
                "collection_coverage": round(coverage * 30, 1),
                "rare_mythic_support": round(rarity_score, 1),
            },
            key_owned=strategy_data["key_owned"],
            key_missing=strategy_data["key_missing"],
        )

    # Legacy-only path: no strategy DB data for this commander
    def card_weight(c: dict) -> float:
        return sum(profile.role_weights.get(r, 0) for r in roles_cache[c["name"]])

    key_owned = [c["name"] for c in
                 sorted([c for c in owned_pool if not c["is_land"] and card_weight(c) > 0],
                        key=card_weight, reverse=True)[:5]]
    key_missing = [c["name"] for c in
                   sorted([c for c in pool if c["name"] not in owned_set and not c["is_land"] and card_weight(c) > 0],
                          key=card_weight, reverse=True)[:5]]

    return CommanderRecommendation(
        name=cmdr["name"],
        color_identity=sorted(json.loads(cmdr["color_identity"])),
        cmc=cmdr["cmc"],
        rarity=cmdr["rarity"],
        type_line=cmdr["type_line"],
        owned=cmdr["name"] in owned_set,
        profile_id=profile.id,
        profile_name=profile.display_name,
        collection_fit=round(legacy_score, 1),
        owned_pct=round(owned_pct, 1),
        owned_pool=len(owned_pool),
        total_pool=len(pool),
        role_coverage=dict(owned_role_counts),
        score_breakdown={
            "role_coverage":       round(role_score * 8, 1),
            "target_completion":   round(coverage_score * 4, 1),
            "collection_breadth":  round(breadth_score, 1),
            "rare_mythic_support": round(rarity_score, 1),
        },
        key_owned=key_owned,
        key_missing=key_missing,
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("", response_model=AnalysisResult)
def analyze(collection: list[OwnedCard]):
    owned_set    = {c.name for c in collection if c.count >= 1}
    total_unique = len(owned_set)
    total_copies = sum(c.count for c in collection)

    with get_db() as conn:
        all_rows = conn.execute("SELECT * FROM cards ORDER BY name").fetchall()
    all_cards = [dict(r) for r in all_rows]

    roles_cache: dict[str, list[str]] = {c["name"]: infer_roles(c) for c in all_cards}

    owned_cards = [c for c in all_cards if c["name"] in owned_set]
    color_strength = _color_strength(owned_cards)
    strongest = sorted(
        "WUBRG",
        key=lambda col: next(cs.owned + cs.rares * 2 + cs.mythics * 3
                             for cs in color_strength if cs.color == col),
        reverse=True,
    )

    type_dist       = _type_distribution(owned_cards)
    role_counts_all = _role_counts(owned_cards, roles_cache)
    summary         = _summary(color_strength, role_counts_all, strongest)

    ci_pools = _build_ci_pools(all_cards)

    commanders = [c for c in all_cards if c["is_commander"]]
    candidates = []
    for cmdr in commanders:
        ci_key = frozenset(json.loads(cmdr["color_identity"]))
        pool   = ci_pools.get(ci_key, [])
        owned_count = sum(1 for c in pool if c["name"] in owned_set and c["name"] != cmdr["name"])
        candidates.append((owned_count, cmdr))

    candidates.sort(key=lambda x: (-(1 if x[1]["name"] in owned_set else 0), -x[0]))
    top_candidates = candidates[:300]

    # Batch-fetch strategy scores for all candidates
    candidate_names = [cmdr["name"] for _, cmdr in top_candidates]
    with strategy_db.get_strategy_db() as s_conn:
        strategy_scores = _fetch_strategy_scores(candidate_names, owned_set, s_conn) if s_conn else {}

    recs = []
    for _, cmdr in top_candidates:
        rec = _score_commander(
            cmdr, ci_pools, owned_set, roles_cache,
            strategy_scores.get(cmdr["name"]),
        )
        if rec:
            recs.append(rec)

    # Sort by fit score only; split into two pools of up to 10 each
    recs.sort(key=lambda r: -(r.collection_fit + r.owned_pct * 0.01))
    owned_recs   = [r for r in recs if r.owned][:10]
    unowned_recs = [r for r in recs if not r.owned][:10]

    return AnalysisResult(
        total_unique=total_unique,
        total_copies=total_copies,
        color_strength=color_strength,
        type_distribution=type_dist,
        role_counts=role_counts_all,
        strongest_colors=list(strongest[:3]),
        summary=summary,
        recommendations=owned_recs + unowned_recs,
    )
