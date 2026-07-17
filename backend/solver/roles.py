"""Infer card roles from Scryfall oracle text, type line, and keywords."""

import json
import re
from typing import Any

# ── Compiled patterns ──────────────────────────────────────────────────────────

_MANA_ADD = re.compile(r"\{t\}[^.]*?:.*?add \{", re.I | re.S)
_MANA_ADD2 = re.compile(r"add \{[wubrgc]\}\{[wubrgc]\}", re.I)  # produces 2+ mana
_LAND_FETCH = re.compile(r"search your library for (?:up to \w+ )?(?:a |an )?(?:basic )?land", re.I)
_LAND_PUT_BF = re.compile(r"put .{0,60}land.{0,30}onto the battlefield", re.I)
_DRAW = re.compile(r"\bdraws? (?:a card|\d+ cards?|that many cards)", re.I)
_TUTOR = re.compile(r"search your library for", re.I)
_COUNTER_SPELL = re.compile(r"counter target (?:spell|ability|activated|triggered)", re.I)
_DESTROY_CREATURE = re.compile(r"destroy target (?:creature|nonland permanent)", re.I)
_EXILE_CREATURE = re.compile(r"exile target (?:creature|nonland permanent)", re.I)
_DAMAGE_CREATURE = re.compile(r"deals? \{?[\dx+*/]+\}? damage to (?:target creature|any target|target player or planeswalker)", re.I)
_SWEEP_CREATURES = re.compile(r"(?:destroy|exile) all (?:creatures|nonland permanents|other creatures)", re.I)
_SWEEP_DAMAGE = re.compile(r"deals? \{?[\dx+*/]+\}? damage to (?:each creature|all creatures|each player and each creature)", re.I)
_BOUNCE = re.compile(r"return target (?:creature|permanent|nonland permanent).{0,30}to (?:its owner's hand|your hand)", re.I)
_ETB_TRIGGER = re.compile(r"when(?:ever)? (?:this creature |it )?enters(?: the battlefield)?", re.I)
_ETB_ANY = re.compile(r"when(?:ever)? (?:another |a )?creature (?:you control )?enters", re.I)
_ENGINE_UPKEEP = re.compile(r"at the beginning of (?:your|each) (?:upkeep|draw step)", re.I)
_ENGINE_COMBAT = re.compile(r"whenever .{0,40}(?:attacks|deals combat damage to a player)", re.I)
_TOPDECK = re.compile(r"(?:scry|surveil|look at the top|put .{0,30}on top of your library)", re.I)
_GY_HATE = re.compile(r"exile (?:all cards in|target card from|each card in) .{0,20}graveyard", re.I)
_ART_ANSWER = re.compile(r"(?:destroy|exile) target artifact", re.I)
_CANT_BE_BLOCKED = re.compile(r"can't be blocked", re.I)
_DUAL_TYPE = re.compile(r"basic land — \S+ \S+", re.I)
_FIX_ADD = re.compile(r"add (?:one mana of any color|any combination)", re.I)
_HEX_INDESTR = re.compile(r"\b(?:hexproof|shroud|indestructible)\b", re.I)
_PROT_FROM = re.compile(r"protection from", re.I)
_NINJUTSU_KW = re.compile(r"\bninjutsu\b", re.I)

# Cheap unblockable or near-unblockable evasion (good ninjutsu enablers)
_EVASION_KWS = frozenset({"flying", "shadow", "horsemanship", "skulk"})
_HASTE_KWS = frozenset({"haste", "trample", "flying", "first strike", "double strike"})


def infer_roles(card: Any) -> list[str]:
    """Return a list of role strings for a card dict/Row from the DB."""
    oracle: str = (card["oracle_text"] or "").lower()
    type_line: str = (card["type_line"] or "").lower()
    try:
        kws = {k.lower() for k in json.loads(card["keywords"] or "[]")}
    except Exception:
        kws = set()
    cmc: float = card["cmc"] or 0
    is_land: bool = bool(card["is_land"])
    is_creature: bool = bool(card["is_creature"])

    roles: set[str] = set()

    # ── Land roles ────────────────────────────────────────────────────────────
    if is_land:
        roles.add("land")
        # Fixing: produces multiple colors, has fetch ability, or is a dual
        if _FIX_ADD.search(oracle):
            roles.add("fixing")
        if _LAND_FETCH.search(oracle):
            roles.add("fixing")
        if _DUAL_TYPE.search(type_line):
            roles.add("fixing")
        if oracle.count("add {") >= 2 or "add {w}" in oracle or "add {r}" in oracle or "add {g}" in oracle:
            # Non-basics that can produce multiple colors
            if "basic" not in type_line:
                roles.add("fixing")
    else:
        # ── Ramp ──────────────────────────────────────────────────────────────
        if _MANA_ADD.search(oracle) or _MANA_ADD2.search(oracle):
            roles.add("ramp")
        if _LAND_FETCH.search(oracle) and (_LAND_PUT_BF.search(oracle) or "onto the battlefield" in oracle):
            roles.add("ramp")

    # ── Draw ──────────────────────────────────────────────────────────────────
    if _DRAW.search(oracle):
        roles.add("draw")

    # ── Selection / topdeck setup ─────────────────────────────────────────────
    if _TOPDECK.search(oracle):
        roles.add("selection")
        roles.add("topdeck_setup")

    # ── Tutor ─────────────────────────────────────────────────────────────────
    if _TUTOR.search(oracle) and not is_land:
        roles.add("tutor")

    # ── Protection ────────────────────────────────────────────────────────────
    if _HEX_INDESTR.search(oracle) or _PROT_FROM.search(oracle):
        roles.add("protection")

    # ── Counterspell ─────────────────────────────────────────────────────────
    if _COUNTER_SPELL.search(oracle):
        roles.add("counterspell")
        roles.add("interaction")

    # ── Creature removal ─────────────────────────────────────────────────────
    if _DESTROY_CREATURE.search(oracle) or _EXILE_CREATURE.search(oracle) or _DAMAGE_CREATURE.search(oracle):
        roles.add("creature_removal")
        roles.add("interaction")

    # ── Sweeper ───────────────────────────────────────────────────────────────
    if _SWEEP_CREATURES.search(oracle) or _SWEEP_DAMAGE.search(oracle):
        roles.add("sweeper")
        roles.add("interaction")

    # ── Bounce / general interaction ─────────────────────────────────────────
    if _BOUNCE.search(oracle):
        roles.add("interaction")

    # ── Evasive enabler (cheap creatures that can attack unblocked for ninjutsu) ─
    if is_creature and cmc <= 3 and (kws & _EVASION_KWS or _CANT_BE_BLOCKED.search(oracle)):
        roles.add("evasive_enabler")

    # ── Ninjutsu payoff ───────────────────────────────────────────────────────
    if _NINJUTSU_KW.search(oracle) or "ninja" in type_line:
        roles.add("ninjutsu_payoff")

    # ── ETB payoff ────────────────────────────────────────────────────────────
    if _ETB_TRIGGER.search(oracle) or _ETB_ANY.search(oracle):
        roles.add("etb_payoff")

    # ── Engine ────────────────────────────────────────────────────────────────
    if _ENGINE_UPKEEP.search(oracle) or (_ENGINE_COMBAT.search(oracle) and "draw" in oracle):
        roles.add("engine")

    # ── Finisher ──────────────────────────────────────────────────────────────
    if is_creature and cmc >= 5 and (kws & _HASTE_KWS):
        roles.add("finisher")

    # ── High mana reveal (Yuriko) ─────────────────────────────────────────────
    if cmc >= 7:
        roles.add("high_mana_reveal")

    # ── Graveyard hate ───────────────────────────────────────────────────────
    if _GY_HATE.search(oracle):
        roles.add("graveyard_hate")

    # ── Artifact answer ───────────────────────────────────────────────────────
    if _ART_ANSWER.search(oracle):
        roles.add("artifact_answer")
        roles.add("interaction")

    # ── Bridge (low-cost utility creatures) ───────────────────────────────────
    if is_creature and cmc <= 2 and roles & {"interaction", "draw", "ramp", "selection"}:
        roles.add("bridge")

    return sorted(roles)


def synergy_score(roles: list[str], synergy_tag: str) -> float:
    """Return bonus for how well a card's roles match the commander's synergy theme."""
    role_set = set(roles)
    if synergy_tag == "satoru":
        return 25 if role_set & {"etb_payoff", "ninjutsu_payoff", "evasive_enabler"} else 0
    if synergy_tag == "yuriko":
        return 25 if role_set & {"high_mana_reveal", "topdeck_setup", "ninjutsu_payoff"} else 0
    if synergy_tag == "talion":
        return 15 if role_set & {"draw", "counterspell", "creature_removal"} else 0
    if synergy_tag == "ninjutsu":
        return 25 if role_set & {"ninjutsu_payoff", "evasive_enabler"} else 0
    return 0
