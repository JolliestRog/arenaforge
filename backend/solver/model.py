"""OR-Tools CP-SAT deck builder for Historic Brawl."""

import json
import math
from dataclasses import dataclass
from typing import Any, Literal

from ortools.sat.python import cp_model

from .profiles import Profile
from .roles import infer_roles, synergy_score

DECK_SIZE = 99  # commander is the 100th
SCORE_SCALE = 1000  # float scores → integers for CP-SAT
WC_VALUES = {"common": 1, "uncommon": 2, "rare": 8, "mythic": 16, "special": 8}

Variant = Literal["performance", "wildcard", "consistency", "quality"]


@dataclass
class DeckCard:
    card: dict
    roles: list[str]
    owned: bool
    wildcard_cost: str | None  # rarity or None (owned / basic land)
    reason: str
    score: float


@dataclass
class BuildResult:
    cards: list[DeckCard]
    commander: dict
    score: float
    infeasible: bool = False


def _wc_cost_for(card: dict, owned: bool) -> str | None:
    """Wildcard rarity needed to craft this card, or None."""
    if owned:
        return None
    if card["is_land"] and card["rarity"] == "common":
        return None  # basic lands are free
    return card["rarity"]


def _score_card(
    card: dict,
    roles: list[str],
    profile: Profile,
    owned: bool,
    variant: Variant,
    strategy_weight: float = 0.0,
) -> float:
    score = 0.0

    if strategy_weight > 0:
        # Strategy DB path: weight is the primary signal (scaled 0–280)
        score = strategy_weight * 400
    else:
        # Legacy path: role-weight scoring
        for role in roles:
            score += profile.role_weights.get(role, 0) * 10
        score += synergy_score(roles, profile.synergy_tag)
        if strategy_weight == 0 and not card["is_land"]:
            score *= 0.4  # slight penalty for cards the strategy DB doesn't know about

    # The quality variant is deliberately ownership-neutral so two commanders
    # are compared using their best decks, not the cards a user happens to own.
    if variant != "quality":
        if owned:
            score += 80 if variant == "wildcard" else 20
        else:
            wc = _wc_cost_for(card, owned=False)
            if wc:
                score -= WC_VALUES[wc] * (3 if variant == "wildcard" else 1)

    # Yuriko high-MV bonus (legacy only)
    if not strategy_weight and profile.synergy_tag == "yuriko" and card["cmc"] >= 7:
        score += 20

    # Consistency: penalize high-CMC, reward low-CMC
    if variant == "consistency" and not card["is_land"]:
        role_set = set(roles)
        if card["cmc"] >= 6 and not role_set & {"high_mana_reveal", "etb_payoff"}:
            score -= card["cmc"] * 5
        if card["cmc"] <= 2:
            score += 10

    return score


def _primary_reason(roles: list[str], profile: Profile) -> str:
    """Best human-readable reason for including a card."""
    if not roles:
        return "filler"
    best = max(
        (r for r in roles if r != "land"),
        key=lambda r: profile.role_weights.get(r, 0),
        default=roles[0],
    )
    return best.replace("_", " ")


# ── Hypergeometric helpers ─────────────────────────────────────────────────────

def _log_fact(n: int, _cache: list[float] = [0.0]) -> float:
    while len(_cache) <= n:
        _cache.append(_cache[-1] + math.log(len(_cache)))
    return _cache[n]


def _log_comb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return _log_fact(n) - _log_fact(k) - _log_fact(n - k)


def _hypergeom_pmf(n: int, N: int, K: int, k: int) -> float:
    if k > min(n, K) or k < max(0, n - (N - K)):
        return 0.0
    return math.exp(_log_comb(K, k) + _log_comb(N - K, n - k) - _log_comb(N, n))


def _hypergeom(n: int, N: int, K: int, lo: int, hi: int) -> float:
    return min(1.0, max(0.0, sum(_hypergeom_pmf(n, N, K, k) for k in range(lo, hi + 1))))


def _hypergeom_below(n: int, N: int, K: int, lo: int) -> float:
    return min(1.0, max(0.0, sum(_hypergeom_pmf(n, N, K, k) for k in range(0, lo))))


def estimate_functional_hand(cards: list[DeckCard], profile: Profile) -> float:
    land_count = sum(1 for c in cards if c.card["is_land"])
    p_lands = _hypergeom(7, DECK_SIZE, land_count, 2, 4)

    enabler_count = sum(1 for c in cards if "evasive_enabler" in c.roles)
    ninja_count = sum(1 for c in cards if "ninjutsu_payoff" in c.roles)
    interaction_count = sum(1 for c in cards if "interaction" in c.roles or "draw" in c.roles)

    if profile.synergy_tag in ("satoru", "ninjutsu"):
        p_enabler = 1 - _hypergeom_below(7, DECK_SIZE, enabler_count, 1)
        return round(p_lands * p_enabler * 0.85, 3)
    if profile.synergy_tag == "yuriko":
        p_enabler = 1 - _hypergeom_below(7, DECK_SIZE, enabler_count, 1)
        return round(p_lands * p_enabler * 0.88, 3)
    # talion: mana + interaction
    p_interaction = 1 - _hypergeom_below(7, DECK_SIZE, interaction_count, 1)
    return round(p_lands * p_interaction * 0.9, 3)


# ── CP-SAT solver ─────────────────────────────────────────────────────────────

def build_variant(
    commander: dict,
    candidates: list[dict],
    owned_set: set[str],
    profile: Profile,
    wildcard_budget: dict[str, int] | None,  # None = infinite
    variant: Variant,
    time_limit_s: float = 5.0,
    strategy_weights: dict[str, float] | None = None,
) -> BuildResult:
    sw = strategy_weights or {}
    # Attach roles and scores to each candidate
    annotated: list[tuple[dict, list[str], bool, float]] = []
    for card in candidates:
        if card["name"] == commander["name"]:
            continue
        roles = infer_roles(card)
        owned = card["name"] in owned_set
        score = _score_card(card, roles, profile, owned, variant, sw.get(card["name"], 0.0))
        annotated.append((card, roles, owned, score))

    # Cap the pool size so CP-SAT remains tractable for large color identities.
    # Lands are kept in full; non-lands are trimmed to the top-scored candidates.
    MAX_NONLANDS = 800
    land_ann = [t for t in annotated if t[0]["is_land"]]
    nonland_ann = sorted(
        [t for t in annotated if not t[0]["is_land"]],
        key=lambda t: -t[3],
    )[:MAX_NONLANDS]
    annotated = land_ann + nonland_ann

    n = len(annotated)
    if n < DECK_SIZE:
        return BuildResult(cards=[], commander=commander, score=0, infeasible=True)

    model = cp_model.CpModel()
    x = [model.new_bool_var(f"c{i}") for i in range(n)]

    # Hard: exactly 99 cards
    model.add(sum(x) == DECK_SIZE)

    # Hard: land count in [target-4, target+2]
    land_vars = [x[i] for i, (c, _, _, _) in enumerate(annotated) if c["is_land"]]
    target = profile.land_target
    model.add(sum(land_vars) >= target - 1)
    model.add(sum(land_vars) <= target + 2)

    # Hard: role minimums (only if enough candidates exist)
    for role, rt in profile.role_targets.items():
        role_vars = [x[i] for i, (_, roles, _, _) in enumerate(annotated) if role in roles]
        if len(role_vars) >= rt.min:
            model.add(sum(role_vars) >= rt.min)

    # Hard: wildcard budget per rarity (all variants)
    if wildcard_budget:
        for rarity, budget in wildcard_budget.items():
            if budget >= 9999:
                continue
            unowned_rarity = [
                x[i] for i, (c, _, owned, _) in enumerate(annotated)
                if not owned and c["rarity"] == rarity
                and not (c["is_land"] and c["rarity"] == "common")
            ]
            if unowned_rarity:
                model.add(sum(unowned_rarity) <= budget)

    # Objective: maximize total score (scaled to int)
    int_scores = [max(0, int(score * SCORE_SCALE)) for (_, _, _, score) in annotated]
    model.maximize(sum(int_scores[i] * x[i] for i in range(n)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Retry without role minimums but keep the budget hard constraint
        model2 = cp_model.CpModel()
        x2 = [model2.new_bool_var(f"c{i}") for i in range(n)]
        model2.add(sum(x2) == DECK_SIZE)
        land_vars2 = [x2[i] for i, (c, _, _, _) in enumerate(annotated) if c["is_land"]]
        model2.add(sum(land_vars2) >= target - 1)
        model2.add(sum(land_vars2) <= target + 2)
        if wildcard_budget:
            for rarity, budget in wildcard_budget.items():
                if budget >= 9999:
                    continue
                unowned_rarity2 = [
                    x2[i] for i, (c, _, owned, _) in enumerate(annotated)
                    if not owned and c["rarity"] == rarity
                    and not (c["is_land"] and c["rarity"] == "common")
                ]
                if unowned_rarity2:
                    model2.add(sum(unowned_rarity2) <= budget)
        model2.maximize(sum(int_scores[i] * x2[i] for i in range(n)))
        status = solver.solve(model2)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Budget is genuinely too tight — signal infeasible to caller
            return BuildResult(cards=[], commander=commander, score=0, infeasible=True)
        x = x2
        infeasible_flag = True  # succeeded with relaxed role constraints
    else:
        infeasible_flag = False

    selected: list[DeckCard] = []
    total_score = 0.0
    for i, (card, roles, owned, score) in enumerate(annotated):  # type: ignore[assignment]
        if solver.value(x[i]):
            wc = None if owned else _wc_cost_for(card, owned=False)
            reason = _primary_reason(roles, profile)
            selected.append(DeckCard(card=card, roles=roles, owned=owned,
                                     wildcard_cost=wc, reason=reason, score=score))
            total_score += score

    # Pad with basics if short on lands (Arena allows unlimited basics)
    land_count = sum(1 for dc in selected if dc.card["is_land"])
    basic_by_color = {
        "W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest",
    }
    commander_colors = json.loads(commander.get("color_identity") or "[]")
    allowed_basics = [basic_by_color[c] for c in commander_colors if c in basic_by_color]
    if not allowed_basics:
        allowed_basics = ["Wastes"]
    basics = {c["name"]: c for c in candidates if c["name"] in allowed_basics}
    available_basics = [name for name in allowed_basics if name in basics]
    pad_index = 0
    while land_count < target and len(selected) < DECK_SIZE:
        if not available_basics:
            break
        basic_name = available_basics[pad_index % len(available_basics)]
        pad_index += 1
        basic = basics[basic_name]
        selected.append(DeckCard(card=basic, roles=["land"], owned=True,
                                 wildcard_cost=None, reason="basic land pad", score=0))
        land_count += 1

    return BuildResult(cards=selected, commander=commander, score=total_score,
                       infeasible=infeasible_flag)


def arena_export(commander: dict, cards: list[DeckCard]) -> str:
    counts: dict[str, int] = {}
    for dc in cards:
        counts[dc.card["name"]] = counts.get(dc.card["name"], 0) + 1
    lines = ["Commander", f"1 {commander['name']}", "", "Deck"]
    for name, count in counts.items():
        lines.append(f"{count} {name}")
    return "\n".join(lines)
