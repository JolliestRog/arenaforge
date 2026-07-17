"""Versioned oracle-text signal rule registry.

Rules are deterministic regex-based classifiers.  Each rule fires per clause
and contributes to one or more tags.  The registry version is stored in the DB
build metadata; re-running with an unchanged version + rules + card data must
produce identical weights.

Design notes
------------
* Rules operate on lower-cased oracle text.  Card *self-name* mentions are
  replaced with the sentinel ``~`` so wording like "Whenever Lorthos attacks"
  matches the same rule as "Whenever CARDNAME attacks".
* Contributions are *pre*-clamp.  The classifier aggregates and clamps to
  [0, 1] with an inclusive-OR curve (see ``classify.aggregate_tag_weight``).
* Every fired rule records evidence (source clause, signal id, contribution)
  so a human reviewer can trace any weight.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

SIGNAL_RULE_VERSION = "2026.07.17.1"


# ---------------------------------------------------------------------------
# Tag catalog (also inserted into strategy_tags at migration time).
# ---------------------------------------------------------------------------
TAG_CATALOG: List[Tuple[str, str, str]] = [
    # macro plans
    ("macro_aggro", "macro", "Wants to close on combat quickly."),
    ("macro_tempo", "macro", "Efficient threats + interaction."),
    ("macro_midrange", "macro", "Value creatures, incremental advantage."),
    ("macro_control", "macro", "Interact-heavy, wins late."),
    ("macro_ramp", "macro", "Cheats out expensive threats through mana."),
    ("macro_combo", "macro", "Assembles a specific interaction to win."),
    ("macro_prison", "macro", "Locks the opponent out of resources/attacks."),

    # themes / engines
    ("tokens", "theme", "Creates or cares about creature tokens."),
    ("sacrifice", "theme", "Sacrifices permanents as a resource."),
    ("aristocrats", "theme", "Death triggers as primary engine."),
    ("graveyard", "theme", "Fills or exploits the graveyard."),
    ("artifacts", "theme", "Artifact-matters synergies."),
    ("enchantments", "theme", "Enchantment-matters synergies."),
    ("auras", "theme", "Auras attached to creatures."),
    ("spellslinger", "theme", "Instant/sorcery-matters."),
    ("counters", "theme", "+1/+1 or other counters payoff."),
    ("lands", "theme", "Extra lands, landfall, land-matters."),
    ("lifegain", "theme", "Lifegain triggers/payoffs."),
    ("typal", "theme", "Creature-type tribal payoffs."),
    ("blink", "theme", "Repeatedly exile-and-return permanents."),
    ("equipment", "theme", "Equipment-matters / Voltron equip."),
    ("voltron", "theme", "Wins by attacking with one enhanced creature."),
    ("tap_control", "theme", "Taps opposing permanents."),
    ("untap_denial", "theme", "Prevents opposing untap."),
    ("big_mana", "theme", "Generates or spends large amounts of mana."),
    ("counters_control", "theme", "Uses counterspells as core interaction."),
    ("tribal_generic", "theme", "Any typal/tribal marker present."),

    # signals (raw classifier outputs, kept for evidence)
    ("attack_trigger", "signal", "Whenever ~ attacks trigger."),
    ("etb_trigger", "signal", "Whenever ~ enters trigger."),
    ("cast_trigger", "signal", "Whenever you cast trigger."),
    ("death_trigger", "signal", "Whenever a creature dies trigger."),
    ("landfall_trigger", "signal", "Whenever a land enters trigger."),
    ("token_maker", "signal", "Creates creature tokens."),
    ("tap_effect", "signal", "Taps target permanents."),
    ("untap_denial_effect", "signal", "Prevents untap."),
    ("counter_matters", "signal", "+1/+1 counter payoff."),
    ("aura_payoff", "signal", "Aura attached to CARDNAME payoff."),
    ("equipment_payoff", "signal", "Equipment attached to CARDNAME payoff."),
    ("graveyard_engine", "signal", "Return from graveyard / mill."),
    ("draw_engine", "signal", "Repeatable card draw."),
    ("lifegain_signal", "signal", "Lifegain triggers or payoffs."),
    ("noncreature_matters", "signal", "Noncreature-spell payoff."),

    # win conditions
    ("wincon_combat", "wincon", "Wins via creature combat."),
    ("wincon_commander_damage", "wincon", "Wins via commander damage."),
    ("wincon_drain", "wincon", "Wins by draining life."),
    ("wincon_combo", "wincon", "Wins with a combo kill."),
    ("wincon_mill", "wincon", "Wins by decking opponents."),
    ("wincon_alternate", "wincon", "Alternate win condition text."),
]


# ---------------------------------------------------------------------------
# Rule data structure.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    """A single deterministic rule."""

    signal: str
    pattern: re.Pattern
    contributions: Tuple[Tuple[str, float], ...]  # (tag, weight) pairs
    description: str = ""


def _r(pattern: str, flags: int = re.IGNORECASE) -> re.Pattern:
    return re.compile(pattern, flags)


# Ordering matters only for evidence readability, not for weights.
RULES: Tuple[Rule, ...] = (
    # --- attack triggers ---------------------------------------------------
    Rule(
        "attack_trigger",
        _r(r"whenever (?:~|this creature|it) attacks"),
        (
            ("attack_trigger", 0.9),
            ("macro_aggro", 0.35),
            ("macro_tempo", 0.20),
            ("wincon_combat", 0.35),
        ),
    ),
    Rule(
        "attack_trigger_generic",
        _r(r"whenever (?:a|another) creature you control attacks"),
        (
            ("attack_trigger", 0.5),
            ("macro_aggro", 0.30),
            ("wincon_combat", 0.30),
        ),
    ),

    # --- ETB / cast triggers ----------------------------------------------
    Rule(
        "etb_trigger_self",
        _r(r"when ~ enters"),
        (("etb_trigger", 0.6),),
    ),
    Rule(
        "cast_trigger_spells",
        _r(r"whenever you cast (?:an? )?(?:instant|sorcery|noncreature)"),
        (
            ("cast_trigger", 0.9),
            ("spellslinger", 0.65),
            ("macro_tempo", 0.30),
            ("macro_control", 0.15),
            ("noncreature_matters", 0.60),
        ),
    ),
    Rule(
        "storm_ability",
        _r(r"\bstorm\b"),
        (
            ("spellslinger", 0.45),
            ("macro_combo", 0.30),
        ),
    ),
    Rule(
        "prowess",
        _r(r"\bprowess\b"),
        (
            ("spellslinger", 0.30),
            ("macro_tempo", 0.20),
        ),
    ),

    # --- death triggers / sacrifice ---------------------------------------
    Rule(
        "death_trigger_other",
        _r(r"whenever another creature (?:you control )?dies"),
        (
            ("death_trigger", 0.9),
            ("aristocrats", 0.70),
            ("sacrifice", 0.55),
            ("macro_midrange", 0.20),
            ("wincon_drain", 0.25),
        ),
    ),
    Rule(
        "death_trigger_creature",
        _r(r"whenever a creature dies"),
        (
            ("death_trigger", 0.7),
            ("aristocrats", 0.55),
            ("sacrifice", 0.40),
        ),
    ),
    Rule(
        "sacrifice_cost",
        _r(r"sacrifice (?:a|another) creature[:,]"),
        (
            ("sacrifice", 0.55),
            ("aristocrats", 0.30),
        ),
    ),
    Rule(
        "creates_tokens",
        _r(r"create[s]? (?:an? |[a-z]+ |x |\d+ )?[^.]*?token"),
        (
            ("token_maker", 0.75),
            ("tokens", 0.65),
        ),
    ),

    # --- graveyard / recursion --------------------------------------------
    Rule(
        "return_from_graveyard",
        _r(r"return .*? from your graveyard to (?:your hand|the battlefield)"),
        (
            ("graveyard_engine", 0.75),
            ("graveyard", 0.60),
        ),
    ),
    Rule(
        "mill_self",
        _r(r"mill (?:a card|two cards|\w+ cards|x cards)"),
        (
            ("graveyard_engine", 0.45),
            ("graveyard", 0.35),
        ),
    ),
    Rule(
        "flashback",
        _r(r"\bflashback\b"),
        (("graveyard", 0.40), ("spellslinger", 0.20)),
    ),
    Rule(
        "escape",
        _r(r"\bescape\b"),
        (("graveyard", 0.40),),
    ),

    # --- landfall / lands -------------------------------------------------
    Rule(
        "landfall",
        _r(r"whenever a land (?:enters|you control enters)"),
        (
            ("landfall_trigger", 0.8),
            ("lands", 0.70),
            ("macro_ramp", 0.40),
        ),
    ),
    Rule(
        "additional_land",
        _r(r"you may play an additional land"),
        (
            ("lands", 0.55),
            ("macro_ramp", 0.35),
        ),
    ),

    # --- ramp / big mana --------------------------------------------------
    Rule(
        "mana_from_creature",
        _r(r"add (?:one|two|three|four|five|six|seven|eight|x|\d+)?\s*\{[wubrgc]}"),
        (("macro_ramp", 0.25), ("big_mana", 0.25)),
    ),
    Rule(
        "search_for_lands",
        _r(r"search your library for (?:a|up to \w+) (?:basic )?land"),
        (("macro_ramp", 0.45), ("lands", 0.35)),
    ),
    Rule(
        "cost_reduction",
        _r(r"costs? \{\d+\} less"),
        (("macro_tempo", 0.25),),
    ),

    # --- artifacts / enchantments ----------------------------------------
    Rule(
        "artifact_matters",
        _r(r"whenever (?:an|another) artifact"),
        (("artifacts", 0.70), ("macro_midrange", 0.15)),
    ),
    Rule(
        "affinity_artifact",
        _r(r"affinity for artifacts|metalcraft|improvise"),
        (("artifacts", 0.55),),
    ),
    Rule(
        "enchantment_matters",
        _r(r"whenever (?:an|another) enchantment"),
        (("enchantments", 0.70),),
    ),
    Rule(
        "constellation",
        _r(r"constellation"),
        (("enchantments", 0.65),),
    ),

    # --- auras / equipment / voltron -------------------------------------
    Rule(
        "aura_attached_payoff",
        _r(r"(?:aura|enchanted creature) (?:attached to ~|you control)"),
        (
            ("aura_payoff", 0.75),
            ("auras", 0.65),
            ("enchantments", 0.30),
            ("voltron", 0.35),
            ("macro_midrange", 0.15),
        ),
    ),
    Rule(
        "aura_attached_generic",
        _r(r"for each aura (?:and equipment )?attached to ~"),
        (
            ("aura_payoff", 0.75),
            ("auras", 0.60),
            ("voltron", 0.45),
        ),
    ),
    Rule(
        "aura_matters_light",
        _r(r"whenever an aura (?:you control )?enters"),
        (
            ("aura_payoff", 0.65),
            ("auras", 0.75),
            ("enchantments", 0.35),
        ),
    ),
    Rule(
        "equipment_attached_payoff",
        _r(r"equipped creature|for each equipment attached"),
        (
            ("equipment_payoff", 0.7),
            ("equipment", 0.60),
            ("voltron", 0.40),
            ("wincon_commander_damage", 0.20),
        ),
    ),
    Rule(
        "equip_ability",
        _r(r"\bequip \{"),
        (("equipment", 0.40),),
    ),

    # --- counters ---------------------------------------------------------
    Rule(
        "plus_one_counter",
        _r(r"\+1/\+1 counter"),
        (
            ("counter_matters", 0.55),
            ("counters", 0.55),
        ),
    ),
    Rule(
        "proliferate",
        _r(r"\bproliferate\b"),
        (("counters", 0.55),),
    ),

    # --- tap / untap manipulation ----------------------------------------
    Rule(
        "tap_target_permanents",
        _r(r"tap (?:up to \w+|target|any number of|all|X) [^.]*permanent"),
        (
            ("tap_effect", 0.85),
            ("tap_control", 0.85),
            ("macro_prison", 0.55),
            ("macro_control", 0.35),
        ),
    ),
    Rule(
        "tap_target_creature",
        _r(r"tap (?:up to \w+|target|any number of|all|X) [^.]*creature"),
        (
            ("tap_effect", 0.65),
            ("tap_control", 0.55),
            ("macro_control", 0.20),
        ),
    ),
    Rule(
        "no_untap",
        _r(r"(?:do(?:es)?n'?t untap|does not untap)"),
        (
            ("untap_denial_effect", 0.9),
            ("untap_denial", 0.85),
            ("tap_control", 0.55),
            ("macro_prison", 0.60),
            ("macro_control", 0.25),
        ),
    ),

    # --- pay a lot of mana ------------------------------------------------
    Rule(
        "high_mv_activation",
        _r(r"pay \{[6-9]\}|pay \{1[0-9]\}"),
        (("big_mana", 0.55), ("macro_ramp", 0.25)),
    ),

    # --- lifegain ---------------------------------------------------------
    Rule(
        "lifegain",
        _r(r"you gain \d+ life|gains? \d+ life|lifelink"),
        (("lifegain_signal", 0.45), ("lifegain", 0.45)),
    ),
    Rule(
        "lifegain_payoff",
        _r(r"whenever you gain life"),
        (("lifegain", 0.75), ("wincon_drain", 0.15)),
    ),

    # --- counterspell / control -----------------------------------------
    Rule(
        "counter_target_spell",
        _r(r"counter target (?:spell|noncreature spell|instant or sorcery)"),
        (
            ("counters_control", 0.75),
            ("macro_control", 0.40),
        ),
    ),

    # --- draw engines -----------------------------------------------------
    Rule(
        "recurring_draw",
        _r(r"draw a card"),
        (("draw_engine", 0.20),),
    ),
    Rule(
        "draw_trigger",
        _r(r"whenever .* draw (?:a|two|three|x) cards?"),
        (("draw_engine", 0.55), ("macro_control", 0.15)),
    ),

    # --- typal / tribal ---------------------------------------------------
    Rule(
        "type_lord",
        _r(r"other \w+ creatures? you control get \+"),
        (("typal", 0.65), ("tribal_generic", 0.65)),
    ),
    Rule(
        "typal_matters",
        _r(r"whenever another \w+ (?:you control )?enters"),
        (("typal", 0.55), ("tribal_generic", 0.55)),
    ),

    # --- blink ------------------------------------------------------------
    Rule(
        "blink_effect",
        _r(r"exile .* return .* to the battlefield"),
        (("blink", 0.60),),
    ),

    # --- win conditions ---------------------------------------------------
    Rule(
        "combat_damage_wincon",
        _r(r"deals combat damage to a player"),
        (("wincon_combat", 0.30),),
    ),
    Rule(
        "commander_damage_hint",
        _r(r"double strike|trample|menace|flying"),
        (("wincon_combat", 0.10),),
    ),
    Rule(
        "drain_wincon",
        _r(r"each opponent loses \d+ life"),
        (("wincon_drain", 0.65),),
    ),
    Rule(
        "mill_wincon",
        _r(r"target (?:opponent|player) mills"),
        (("wincon_mill", 0.55),),
    ),
    Rule(
        "alt_win",
        _r(r"you (?:win|lose) the game"),
        (("wincon_alternate", 0.75), ("macro_combo", 0.25)),
    ),
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalize_text(name: str, oracle_text: str) -> str:
    """Replace card name references with ``~`` and lowercase."""
    text = oracle_text or ""
    # Full name.
    text = re.sub(re.escape(name), "~", text, flags=re.IGNORECASE)
    # First word of the name is often used as short reference (e.g. Lorthos).
    first = name.split(",")[0].split(" ")[0]
    if first and len(first) > 2:
        text = re.sub(rf"\b{re.escape(first)}\b", "~", text, flags=re.IGNORECASE)
    return text.lower()


def split_clauses(text: str) -> List[str]:
    parts = [p.strip() for p in _CLAUSE_SPLIT.split(text) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


@dataclass
class SignalHit:
    signal: str
    clause: str
    tag: str
    contribution: float


def scan(name: str, oracle_text: str) -> List[SignalHit]:
    """Return every rule hit against ``oracle_text``."""
    hits: List[SignalHit] = []
    norm = normalize_text(name, oracle_text)
    clauses = split_clauses(norm)
    for clause in clauses:
        for rule in RULES:
            if rule.pattern.search(clause):
                for tag, contribution in rule.contributions:
                    hits.append(
                        SignalHit(
                            signal=rule.signal,
                            clause=clause,
                            tag=tag,
                            contribution=float(contribution),
                        )
                    )
    return hits


__all__ = [
    "RULES",
    "SIGNAL_RULE_VERSION",
    "TAG_CATALOG",
    "SignalHit",
    "normalize_text",
    "scan",
    "split_clauses",
]
