"""Deck strategy templates.

Each template composes a macro plan + theme + win condition and lists the tags
that must / should / must-not be present on the commander.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

TEMPLATE_VERSION = "2026.07.17.1"


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    display_name: str
    macro_plan: str
    theme: str
    win_condition: str
    required_tags: Tuple[str, ...]     # each must clear required_threshold
    optional_tags: Tuple[str, ...]     # contribute to alignment when present
    conflicting_tags: Tuple[str, ...]  # veto if strong enough
    needed_roles: Tuple[str, ...]
    min_arena_depth: int = 30
    required_threshold: float = 0.35
    description: str = ""


TEMPLATES: Tuple[Template, ...] = (
    Template(
        id="big_mana_tap_control",
        name="big_mana_tap_control",
        display_name="Big-Mana Tap Control",
        macro_plan="control",
        theme="tap_control",
        win_condition="combat",
        required_tags=("tap_control",),
        optional_tags=(
            "untap_denial", "macro_control", "big_mana", "macro_ramp",
            "macro_prison", "counters_control",
        ),
        conflicting_tags=("macro_aggro",),
        needed_roles=(
            "ramp", "removal", "board_wipe", "draw", "counterspell",
            "tap_enabler", "untap_denial", "finisher",
        ),
        description="Ramp into massive mana, tap defenders down, swing.",
    ),
    Template(
        id="aristocrats_sacrifice_midrange",
        name="aristocrats_sacrifice_midrange",
        display_name="Aristocrats Sacrifice Midrange",
        macro_plan="midrange",
        theme="sacrifice",
        win_condition="drain",
        required_tags=("aristocrats",),
        optional_tags=(
            "sacrifice", "death_trigger", "tokens", "graveyard",
            "wincon_drain", "lifegain",
        ),
        conflicting_tags=("tap_control",),
        needed_roles=(
            "sacrifice_outlet", "token_maker", "death_payoff",
            "recursion", "removal", "draw",
        ),
        description="Loop cheap creatures through sacrifice triggers.",
    ),
    Template(
        id="aura_voltron",
        name="aura_voltron",
        display_name="Aura Voltron",
        macro_plan="midrange",
        theme="auras",
        win_condition="commander_damage",
        required_tags=("aura_payoff",),
        optional_tags=(
            "auras", "enchantments", "voltron", "wincon_commander_damage",
            "macro_midrange",
        ),
        conflicting_tags=("aristocrats", "tokens"),
        needed_roles=(
            "protection", "draw", "removal", "ramp",
            "attack_payoff", "enchantment_payoff",
        ),
        description="Suit up the commander with Auras and swing.",
    ),
    Template(
        id="equipment_voltron",
        name="equipment_voltron",
        display_name="Equipment Voltron",
        macro_plan="midrange",
        theme="equipment",
        win_condition="commander_damage",
        required_tags=("equipment_payoff",),
        optional_tags=(
            "equipment", "voltron", "wincon_commander_damage",
            "artifacts", "macro_midrange",
        ),
        conflicting_tags=("aristocrats",),
        needed_roles=(
            "protection", "draw", "removal", "ramp",
            "attack_payoff", "artifact_payoff",
        ),
        description="Load the commander with Equipment for a knockout swing.",
    ),
    Template(
        id="spellslinger_tempo",
        name="spellslinger_tempo",
        display_name="Spellslinger Tempo",
        macro_plan="tempo",
        theme="spellslinger",
        win_condition="combat",
        required_tags=("spellslinger",),
        optional_tags=(
            "cast_trigger", "noncreature_matters", "macro_tempo",
            "counters_control", "macro_control",
        ),
        conflicting_tags=("aristocrats", "tap_control"),
        needed_roles=(
            "counterspell", "removal", "draw", "selection",
            "protection", "finisher",
        ),
        description="Chain instants and sorceries for tempo and card advantage.",
    ),
    Template(
        id="tokens_go_wide",
        name="tokens_go_wide",
        display_name="Tokens Go-Wide Aggro",
        macro_plan="aggro",
        theme="tokens",
        win_condition="combat",
        required_tags=("tokens",),
        optional_tags=(
            "token_maker", "macro_aggro", "typal", "wincon_combat",
        ),
        conflicting_tags=("tap_control", "macro_control"),
        needed_roles=(
            "token_maker", "anthem", "removal", "ramp", "protection",
        ),
        description="Flood the board with tokens and pump them.",
    ),
    Template(
        id="graveyard_reanimator",
        name="graveyard_reanimator",
        display_name="Graveyard Reanimator",
        macro_plan="midrange",
        theme="graveyard",
        win_condition="combat",
        required_tags=("graveyard",),
        optional_tags=(
            "graveyard_engine", "aristocrats", "macro_midrange", "wincon_drain",
        ),
        conflicting_tags=("tap_control",),
        needed_roles=(
            "graveyard_filler", "recursion", "removal", "draw", "finisher",
        ),
        description="Fill the graveyard and return threats to the battlefield.",
    ),
    Template(
        id="landfall_ramp",
        name="landfall_ramp",
        display_name="Landfall Ramp",
        macro_plan="ramp",
        theme="lands",
        win_condition="combat",
        required_tags=("lands",),
        optional_tags=(
            "landfall_trigger", "macro_ramp", "big_mana", "wincon_combat",
        ),
        conflicting_tags=("tap_control",),
        needed_roles=(
            "ramp", "land_payoff", "draw", "removal", "finisher",
        ),
        description="Play extra lands each turn to trigger landfall payoffs.",
    ),
    Template(
        id="counters_go_tall",
        name="counters_go_tall",
        display_name="Counters Go-Tall",
        macro_plan="midrange",
        theme="counters",
        win_condition="combat",
        required_tags=("counters",),
        optional_tags=(
            "counter_matters", "wincon_combat", "macro_midrange",
        ),
        conflicting_tags=("tap_control",),
        needed_roles=(
            "counters_enabler", "counters_payoff", "removal", "draw", "ramp",
        ),
        description="Pile +1/+1 counters on threats to close.",
    ),
    Template(
        id="artifact_synergy_midrange",
        name="artifact_synergy_midrange",
        display_name="Artifact Synergy Midrange",
        macro_plan="midrange",
        theme="artifacts",
        win_condition="combat",
        required_tags=("artifacts",),
        optional_tags=(
            "macro_midrange", "wincon_combat", "equipment",
        ),
        conflicting_tags=(),
        needed_roles=(
            "artifact_payoff", "ramp", "draw", "removal", "finisher",
        ),
        description="Chain artifacts for value and payoff triggers.",
    ),
    Template(
        id="enchantress_control",
        name="enchantress_control",
        display_name="Enchantress Control",
        macro_plan="control",
        theme="enchantments",
        win_condition="combat",
        required_tags=("enchantments",),
        optional_tags=(
            "macro_control", "auras", "wincon_combat", "macro_midrange",
        ),
        conflicting_tags=("tap_control", "aristocrats"),
        needed_roles=(
            "enchantment_payoff", "draw", "removal", "board_wipe", "ramp",
        ),
        description="Enchantments as a value engine, closing with big threats.",
    ),
    Template(
        id="lifegain_midrange",
        name="lifegain_midrange",
        display_name="Lifegain Midrange",
        macro_plan="midrange",
        theme="lifegain",
        win_condition="drain",
        required_tags=("lifegain",),
        optional_tags=(
            "wincon_drain", "macro_midrange", "aristocrats",
        ),
        conflicting_tags=("tap_control",),
        needed_roles=(
            "lifegain_enabler", "lifegain_payoff", "removal", "draw", "ramp",
        ),
        description="Snowball lifegain triggers into a drain kill.",
    ),
    Template(
        id="typal_midrange",
        name="typal_midrange",
        display_name="Typal Midrange",
        macro_plan="midrange",
        theme="typal",
        win_condition="combat",
        required_tags=("typal",),
        optional_tags=(
            "tribal_generic", "macro_midrange", "wincon_combat",
        ),
        conflicting_tags=("tap_control",),
        needed_roles=(
            "anthem", "ramp", "removal", "draw", "finisher",
        ),
        description="Creature-type synergy stacked with lord effects.",
    ),
)


# Roles each template targets; used for card ranking and future deckbuilding.
ROLE_TARGETS: dict[str, Tuple[Tuple[str, int, int, float], ...]] = {
    "big_mana_tap_control":            (
        ("ramp",             12, 16, 0.9),
        ("removal",           6,  9, 0.7),
        ("board_wipe",        3,  5, 0.7),
        ("draw",              7, 10, 0.7),
        ("counterspell",      4,  7, 0.6),
        ("tap_enabler",       4,  8, 0.9),
        ("untap_denial",      2,  5, 0.9),
        ("finisher",          2,  4, 0.6),
    ),
    "aristocrats_sacrifice_midrange":  (
        ("sacrifice_outlet",  5,  8, 0.9),
        ("token_maker",       8, 12, 0.8),
        ("death_payoff",      6, 10, 0.9),
        ("recursion",         4,  6, 0.7),
        ("removal",           6,  9, 0.7),
        ("draw",              6,  9, 0.6),
    ),
    "aura_voltron":                    (
        ("protection",        6,  9, 0.9),
        ("draw",              6,  9, 0.6),
        ("removal",           5,  8, 0.6),
        ("ramp",              8, 12, 0.7),
        ("attack_payoff",     6,  9, 0.7),
        ("enchantment_payoff", 6,  9, 0.7),
    ),
    "equipment_voltron":               (
        ("protection",        6,  9, 0.9),
        ("draw",              6,  9, 0.6),
        ("removal",           5,  8, 0.6),
        ("ramp",              8, 12, 0.7),
        ("attack_payoff",     6,  9, 0.7),
        ("artifact_payoff",   6,  9, 0.7),
    ),
    "spellslinger_tempo":              (
        ("counterspell",      6,  9, 0.9),
        ("removal",           6,  9, 0.7),
        ("draw",              7, 10, 0.7),
        ("selection",         5,  8, 0.6),
        ("protection",        3,  5, 0.5),
        ("finisher",          2,  4, 0.6),
    ),
    "tokens_go_wide":                  (
        ("token_maker",       9, 13, 0.9),
        ("anthem",            5,  8, 0.9),
        ("removal",           5,  8, 0.6),
        ("ramp",              6,  9, 0.5),
        ("protection",        3,  5, 0.5),
    ),
    "graveyard_reanimator":            (
        ("graveyard_filler",  6, 10, 0.9),
        ("recursion",         6,  9, 0.9),
        ("removal",           5,  8, 0.6),
        ("draw",              6,  9, 0.6),
        ("finisher",          3,  5, 0.7),
    ),
    "landfall_ramp":                   (
        ("ramp",             13, 18, 0.9),
        ("land_payoff",       6,  9, 0.9),
        ("draw",              6,  9, 0.6),
        ("removal",           5,  8, 0.5),
        ("finisher",          3,  5, 0.6),
    ),
    "counters_go_tall":                (
        ("counters_enabler",  6,  9, 0.8),
        ("counters_payoff",   6,  9, 0.9),
        ("removal",           5,  8, 0.6),
        ("draw",              6,  9, 0.6),
        ("ramp",              7, 10, 0.6),
    ),
    "artifact_synergy_midrange":       (
        ("artifact_payoff",   7, 10, 0.9),
        ("ramp",              7, 10, 0.7),
        ("draw",              6,  9, 0.6),
        ("removal",           5,  8, 0.6),
        ("finisher",          3,  5, 0.6),
    ),
    "enchantress_control":             (
        ("enchantment_payoff", 6, 10, 0.9),
        ("draw",              7, 10, 0.7),
        ("removal",           6,  9, 0.7),
        ("board_wipe",        3,  5, 0.7),
        ("ramp",              6,  9, 0.6),
    ),
    "lifegain_midrange":               (
        ("lifegain_enabler",  6,  9, 0.8),
        ("lifegain_payoff",   6,  9, 0.9),
        ("removal",           5,  8, 0.6),
        ("draw",              6,  9, 0.6),
        ("ramp",              7, 10, 0.6),
    ),
    "typal_midrange":                  (
        ("anthem",            4,  7, 0.9),
        ("ramp",              7, 10, 0.6),
        ("removal",           5,  8, 0.6),
        ("draw",              6,  9, 0.6),
        ("finisher",          3,  5, 0.7),
    ),
}


def get_template(template_id: str) -> Template:
    for t in TEMPLATES:
        if t.id == template_id:
            return t
    raise KeyError(template_id)


__all__ = ["TEMPLATE_VERSION", "Template", "TEMPLATES", "ROLE_TARGETS", "get_template"]
