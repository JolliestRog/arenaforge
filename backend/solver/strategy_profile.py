"""Shared strategy-DB to solver profile adapter.

Analysis and deck building must use the same role vocabulary and land targets;
otherwise a recommendation can score well and then build a materially different
deck after the user selects it.
"""

from __future__ import annotations

from .profiles import Profile, RoleTarget


STRATEGY_ROLE_MAP: dict[str, str] = {
    "draw": "draw",
    "ramp": "ramp",
    "counterspell": "counterspell",
    "protection": "protection",
    "finisher": "finisher",
    "selection": "selection",
    "recursion": "recursion",
    "removal": "creature_removal",
    "board_wipe": "sweeper",
    "token_maker": "etb_payoff",
    "artifact_payoff": "engine",
    "enchantment_payoff": "engine",
    "tap_enabler": "interaction",
    "attack_payoff": "engine",
    "land_payoff": "engine",
    "sacrifice_outlet": "engine",
    "death_payoff": "engine",
    "graveyard_filler": "engine",
    "counters_enabler": "engine",
    "counters_payoff": "engine",
    "lifegain_enabler": "engine",
    "lifegain_payoff": "engine",
    "anthem": "finisher",
    "untap_denial": "interaction",
    "blink_enabler": "etb_payoff",
    "blink_payoff": "engine",
    "evasive_enabler": "evasive_enabler",
    "topdeck_setup": "topdeck_setup",
    "ninjutsu_payoff": "ninjutsu_payoff",
}

LAND_TARGET_BY_MACRO: dict[str, int] = {
    "tempo": 34,
    "aggro": 34,
    "control": 38,
    "ramp": 38,
    "midrange": 36,
    "combo": 35,
}


def profile_from_strategy_rows(
    strategy_id: str,
    display_name: str,
    macro_plan: str,
    role_target_rows: list[dict],
) -> Profile:
    role_targets: dict[str, RoleTarget] = {}
    role_weights: dict[str, float] = {}
    for row in role_target_rows:
        solver_role = STRATEGY_ROLE_MAP.get(row["role"], row["role"])
        target = RoleTarget(min=row["min_count"], preferred=row["preferred_count"])
        existing = role_targets.get(solver_role)
        if existing:
            target = RoleTarget(
                min=max(existing.min, target.min),
                preferred=max(existing.preferred, target.preferred),
            )
        role_targets[solver_role] = target
        role_weights[solver_role] = max(
            role_weights.get(solver_role, 0.0), row["weight"] * 10
        )

    if "draw" not in role_targets:
        role_targets["draw"] = RoleTarget(min=6, preferred=10)
        role_weights["draw"] = 5.0
    if "ramp" not in role_targets:
        role_targets["ramp"] = RoleTarget(min=5, preferred=8)
        role_weights["ramp"] = 5.0

    priority = sorted(role_weights, key=lambda role: -role_weights[role])[:3]
    return Profile(
        id=strategy_id,
        commander="",
        display_name=display_name,
        description="",
        land_target=LAND_TARGET_BY_MACRO.get(macro_plan, 36),
        role_targets=role_targets,
        role_weights=role_weights,
        synergy_tag="ninjutsu" if strategy_id == "ninja_evasion_tempo" else "",
        priority_roles=priority,
        functional_hand_definition="viable mana + key role pieces",
    )
