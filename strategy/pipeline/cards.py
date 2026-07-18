"""Card role classification + commander/strategy card weights."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

from ..rules.templates import ROLE_TARGETS, TEMPLATES, get_template

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role rule table.
# Each entry: (role, regex, base_weight, extra_condition)
# extra_condition receives the full card dict and returns bool.
# ---------------------------------------------------------------------------
def _land_only(card): return card["is_land"] == 1
def _creature_only(card): return card["is_creature"] == 1
def _noncreature(card): return card["is_creature"] == 0
def _low_cmc(card): return card["cmc"] <= 3
def _high_cmc(card): return card["cmc"] >= 7
def _any(card): return True


ROLE_RULES: List[Tuple[str, re.Pattern, float, Callable[[dict], bool]]] = [
    # ramp
    ("ramp", re.compile(r"add \{[wubrgc]\}(?:\{[wubrgc]\})?", re.I), 0.7, _any),
    ("ramp", re.compile(r"search your library for (?:a|up to \w+) (?:basic )?land", re.I), 0.85, _any),
    ("ramp", re.compile(r"put (?:a|up to \w+) land[^.]* onto the battlefield", re.I), 0.8, _any),
    ("ramp", re.compile(r"add (?:one|two|three|four) mana", re.I), 0.75, _any),
    ("ritual", re.compile(r"add \{[wubrgc]\}\{[wubrgc]\}\{[wubrgc]\}", re.I), 0.7, _noncreature),
    ("cost_reduction", re.compile(r"costs? \{\d+\} less", re.I), 0.75, _any),

    # draw / selection / tutors
    ("draw", re.compile(r"draw (?:two|three|four|five|x) cards?", re.I), 0.75, _any),
    ("draw", re.compile(r"whenever .*? draw a card", re.I), 0.55, _any),
    ("draw", re.compile(r"draw a card", re.I), 0.4, _any),
    ("selection", re.compile(r"scry \d+|surveil \d+|look at the top \w+ cards?", re.I), 0.7, _any),
    ("tutor", re.compile(r"search your library for a (?:card|creature|artifact|enchantment|instant|sorcery)", re.I), 0.8, _any),

    # removal / wipes / counters
    ("removal", re.compile(r"destroy target (?:creature|permanent|artifact|enchantment|planeswalker)", re.I), 0.8, _any),
    ("removal", re.compile(r"exile target (?:creature|permanent|artifact|enchantment|planeswalker)", re.I), 0.8, _any),
    ("removal", re.compile(r"target creature .* -\d+/-\d+", re.I), 0.65, _any),
    ("removal", re.compile(r"deals \d+ damage to (?:any target|target creature|target planeswalker)", re.I), 0.6, _any),
    ("board_wipe", re.compile(r"destroy all (?:creatures|nonland permanents)", re.I), 0.9, _any),
    ("board_wipe", re.compile(r"exile all creatures", re.I), 0.9, _any),
    ("counterspell", re.compile(r"counter target (?:spell|noncreature spell|instant or sorcery)", re.I), 0.85, _any),

    # protection / recursion
    ("protection", re.compile(r"hexproof|indestructible|protection from", re.I), 0.7, _any),
    ("protection", re.compile(r"phasing|phase out", re.I), 0.6, _any),
    ("recursion", re.compile(r"return target .* from your graveyard to (?:your hand|the battlefield)", re.I), 0.85, _any),
    ("recursion", re.compile(r"return .* creature card .* from your graveyard to the battlefield", re.I), 0.9, _any),

    # graveyard
    ("graveyard_filler", re.compile(r"mill (?:a|two|three|four|five|x) cards?", re.I), 0.7, _any),
    ("graveyard_filler", re.compile(r"discard .* card", re.I), 0.4, _any),

    # sacrifice engine
    ("sacrifice_outlet", re.compile(r"sacrifice (?:a|another) creature", re.I), 0.8, _any),
    ("token_maker", re.compile(r"create[s]? .*? token", re.I), 0.8, _any),
    ("death_payoff", re.compile(r"whenever (?:a|another) creature (?:you control )?dies", re.I), 0.9, _any),

    # anthems / go-wide payoffs
    ("anthem", re.compile(r"creatures you control get \+\d+/\+\d+", re.I), 0.85, _any),
    ("anthem", re.compile(r"other (?:\w+ )?creatures you control get \+\d+/\+\d+", re.I), 0.8, _any),

    # blink
    ("blink_enabler", re.compile(r"exile target (?:creature|permanent).*? return .* to the battlefield", re.I), 0.85, _any),
    ("blink_payoff", re.compile(r"when ~ enters", re.I), 0.4, _creature_only),

    # theme payoffs
    ("artifact_payoff", re.compile(r"whenever (?:an|another) artifact", re.I), 0.8, _any),
    ("artifact_payoff", re.compile(r"for each artifact you control", re.I), 0.7, _any),
    ("enchantment_payoff", re.compile(r"whenever (?:an|another) enchantment", re.I), 0.8, _any),
    ("enchantment_payoff", re.compile(r"for each enchantment you control", re.I), 0.7, _any),
    ("enchantment_payoff", re.compile(r"constellation", re.I), 0.8, _any),
    ("land_payoff", re.compile(r"whenever a land enters", re.I), 0.85, _any),
    ("land_payoff", re.compile(r"landfall", re.I), 0.75, _any),

    ("counters_enabler", re.compile(r"put a \+1/\+1 counter", re.I), 0.65, _any),
    ("counters_payoff", re.compile(r"whenever a \+1/\+1 counter", re.I), 0.85, _any),
    ("counters_payoff", re.compile(r"for each \+1/\+1 counter", re.I), 0.7, _any),

    ("attack_payoff", re.compile(r"whenever (?:~|a creature you control) attacks", re.I), 0.75, _any),
    ("evasion", re.compile(r"flying|menace|trample|unblockable|can'?t be blocked", re.I), 0.6, _creature_only),
    ("evasive_enabler", re.compile(r"flying|menace|shadow|skulk|unblockable|can'?t be blocked", re.I), 0.75, lambda c: _creature_only(c) and _low_cmc(c)),
    ("ninjutsu_payoff", re.compile(r"\bninjutsu\b|\bninja\b", re.I), 0.9, _any),
    ("topdeck_setup", re.compile(r"scry|surveil|look at the top|put .{0,30} on top of your library", re.I), 0.75, _any),
    ("high_mana_reveal", re.compile(r".", re.S), 0.7, _high_cmc),

    ("tap_enabler", re.compile(r"tap (?:up to \w+|target|any number of|all|X) [^.]*permanent", re.I), 0.85, _any),
    ("tap_enabler", re.compile(r"tap (?:up to \w+|target|any number of|all|X) [^.]*creature", re.I), 0.7, _any),
    ("untap_denial", re.compile(r"do(?:es)?n'?t untap", re.I), 0.9, _any),

    ("lifegain_enabler", re.compile(r"gain \d+ life|lifelink", re.I), 0.6, _any),
    ("lifegain_payoff", re.compile(r"whenever you gain life", re.I), 0.85, _any),

    ("finisher", re.compile(r"deals? \d+ damage to each opponent", re.I), 0.8, _any),
    ("finisher", re.compile(r"you win the game", re.I), 0.9, _any),
    ("finisher", re.compile(r"double strike", re.I), 0.55, _creature_only),
    ("finisher", re.compile(r"trample", re.I), 0.4, _creature_only),

    ("combo_piece", re.compile(r"infinite|untap all", re.I), 0.6, _any),
]


# ---------------------------------------------------------------------------
# Role classification.
# ---------------------------------------------------------------------------
def classify_card(card: dict) -> Dict[str, Dict]:
    text = (card["oracle_text"] or "").lower()
    result: Dict[str, List[dict]] = defaultdict(list)
    for role, pattern, weight, condition in ROLE_RULES:
        if not condition(card):
            continue
        if pattern.search(text):
            result[role].append({
                "role": role,
                "pattern": pattern.pattern,
                "weight": weight,
            })
    out: Dict[str, Dict] = {}
    for role, hits in result.items():
        # OR aggregation for multiple pattern hits per role.
        remaining = 1.0
        for h in hits:
            remaining *= (1.0 - h["weight"])
        w = 1.0 - remaining
        out[role] = {"weight": w, "evidence": hits}
    return out


def classify_all_cards(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT oracle_id, name, oracle_text, cmc, type_line, is_land, is_creature"
        " FROM cards WHERE arena_legal = 1"
    )
    rows = cur.fetchall()

    with conn:
        conn.execute("DELETE FROM card_role_weights")
        batch: List[tuple] = []
        for row in rows:
            card = dict(row)
            roles = classify_card(card)
            for role, data in roles.items():
                if data["weight"] <= 0:
                    continue
                batch.append((
                    row["oracle_id"], role, data["weight"],
                    json.dumps(data["evidence"]),
                ))
        conn.executemany(
            "INSERT INTO card_role_weights (oracle_id, role, weight, evidence)"
            " VALUES (?, ?, ?, ?)",
            batch,
        )
    log.info("classified %d cards -> %d role weight rows", len(rows), len(batch))
    return len(rows)


# ---------------------------------------------------------------------------
# Commander/strategy card weights.
# ---------------------------------------------------------------------------
_QUALITY_BY_RARITY = {
    # Rarity is a crafting cost, not evidence of card strength.
    "mythic": 0.5, "rare": 0.5, "uncommon": 0.5, "common": 0.5,
    "special": 0.5, "bonus": 0.5,
}


def _quality(card: dict) -> float:
    base = _QUALITY_BY_RARITY.get(card["rarity"], 0.4)
    # Slight nudge against high-CMC noncreature spells.
    if card["cmc"] and card["cmc"] >= 7 and not card["is_creature"]:
        base -= 0.1
    return max(0.05, min(1.0, base))


def _color_ok(card_colors: Sequence[str], commander_colors: Sequence[str]) -> bool:
    return set(card_colors).issubset(set(commander_colors))


def _interaction_score(card: dict, commander_tags: Dict[str, float], template) -> float:
    """How well the card matches the *specific commander*'s tags."""
    text = (card["oracle_text"] or "").lower()
    score = 0.0
    # Reward any role the strategy needs whose payoff terms echo the commander.
    for tag in template.required_tags:
        if tag in commander_tags and tag in text.replace("_", " "):
            score += 0.4
    for tag in template.optional_tags:
        if tag in commander_tags and tag in text.replace("_", " "):
            score += 0.15
    return min(1.0, score)


def build_commander_strategy_cards(conn: sqlite3.Connection, per_pair_cap: int = 250) -> int:
    """Precompute visible pairs plus one fallback pair per legal commander."""
    pairs = conn.execute(
        """
        WITH ranked AS (
            SELECT cs.commander_oracle_id AS cid,
                   cs.strategy_template_id AS tid,
                   c.color_identity AS colors,
                   cs.fit_score AS fit,
                   cs.status AS status,
                   ROW_NUMBER() OVER (
                       PARTITION BY cs.commander_oracle_id
                       ORDER BY cs.fit_score DESC, cs.strategy_template_id
                   ) AS commander_rank
            FROM commander_strategies cs
            JOIN cards c ON c.oracle_id = cs.commander_oracle_id
            WHERE c.is_commander = 1 AND c.arena_legal = 1
        )
        SELECT cid, tid, colors, fit
        FROM ranked
        WHERE status IN ('recommended', 'viable', 'experimental')
           OR commander_rank = 1
        """
    ).fetchall()

    if not pairs:
        return 0

    # Preload role weights once.
    role_index: Dict[str, Dict[str, float]] = defaultdict(dict)
    for row in conn.execute("SELECT role, oracle_id, weight FROM card_role_weights"):
        role_index[row["role"]][row["oracle_id"]] = float(row["weight"])

    # Preload card metadata once.
    card_meta: Dict[str, dict] = {}
    for row in conn.execute(
        "SELECT oracle_id, name, color_identity, cmc, oracle_text, type_line,"
        "       rarity, is_land, is_creature, arena_legal FROM cards"
    ):
        card_meta[row["oracle_id"]] = dict(row)

    # Preload strategy role targets.
    strat_roles: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for row in conn.execute(
        "SELECT strategy_template_id, role, weight FROM strategy_role_targets"
    ):
        strat_roles[row["strategy_template_id"]].append(
            (row["role"], float(row["weight"]))
        )

    with conn:
        conn.execute("DELETE FROM commander_strategy_cards")
        insert_batch: List[tuple] = []
        for pair in pairs:
            cid, tid, colors_json = pair["cid"], pair["tid"], pair["colors"]
            colors = json.loads(colors_json or "[]")
            template = get_template(tid)
            role_targets = strat_roles.get(tid, [])
            if not role_targets:
                continue

            # Commander tag weights (used for interaction score).
            tag_rows = conn.execute(
                "SELECT tag, weight FROM commander_tag_weights"
                " WHERE commander_oracle_id = ?",
                (cid,),
            ).fetchall()
            commander_tags = {r["tag"]: float(r["weight"]) for r in tag_rows}

            candidates: List[tuple] = []
            for oid, meta in card_meta.items():
                if meta["arena_legal"] != 1:
                    continue
                if meta["is_land"]:  # lands handled separately
                    continue
                card_colors = json.loads(meta["color_identity"] or "[]")
                if not _color_ok(card_colors, colors):
                    continue

                # Role match: max over role weights weighted by target importance.
                role_match = 0.0
                best_role = None
                for role, target_weight in role_targets:
                    rw = role_index.get(role, {}).get(oid, 0.0)
                    if rw <= 0:
                        continue
                    contribution = rw * target_weight
                    if contribution > role_match:
                        role_match = contribution
                        best_role = role
                if role_match <= 0:
                    continue

                interaction = _interaction_score(meta, commander_tags, template)
                quality = _quality(meta)

                card_weight = 0.45 * role_match + 0.35 * interaction + 0.20 * quality
                card_weight = max(0.0, min(1.0, card_weight))

                candidates.append((
                    cid, tid, oid, card_weight, role_match, interaction, quality,
                ))

            candidates.sort(key=lambda x: x[3], reverse=True)
            insert_batch.extend(candidates[:per_pair_cap])

        conn.executemany(
            "INSERT INTO commander_strategy_cards"
            " (commander_oracle_id, strategy_template_id, card_oracle_id,"
            "  card_weight, role_contribution, interaction_score, quality_score)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            insert_batch,
        )

    log.info("built %d card weights across %d pairs", len(insert_batch), len(pairs))
    return len(insert_batch)
