"""Commander profiles — Python port of frontend/src/lib/profiles.ts."""

from dataclasses import dataclass, field


@dataclass
class RoleTarget:
    min: int
    preferred: int
    max: int = 999


@dataclass
class Profile:
    id: str
    commander: str
    display_name: str
    description: str
    land_target: int
    role_targets: dict[str, RoleTarget]
    role_weights: dict[str, float]
    synergy_tag: str
    priority_roles: list[str]
    functional_hand_definition: str
    high_mv_target: int = 0


PROFILES: dict[str, Profile] = {
    "satoru_toolbox": Profile(
        id="satoru_toolbox",
        commander="A-Satoru Umezawa",
        display_name="Satoru Toolbox Tempo",
        description="Ninjutsu enablers to deploy huge threats for free.",
        land_target=36,
        role_targets={
            "evasive_enabler": RoleTarget(min=11, preferred=14),
            "interaction":     RoleTarget(min=14, preferred=18),
            "counterspell":    RoleTarget(min=4,  preferred=6),
            "creature_removal":RoleTarget(min=5,  preferred=8),
            "draw":            RoleTarget(min=8,  preferred=12),
            "tutor":           RoleTarget(min=2,  preferred=4),
            "protection":      RoleTarget(min=3,  preferred=5),
            "etb_payoff":      RoleTarget(min=3,  preferred=6, max=8),
            "ramp":            RoleTarget(min=4,  preferred=6),
        },
        role_weights={
            "evasive_enabler": 9, "etb_payoff": 8, "tutor": 8,
            "protection": 7, "draw": 7, "selection": 6, "counterspell": 6,
            "creature_removal": 6, "interaction": 5, "ramp": 5,
            "engine": 7, "finisher": 6, "topdeck_setup": 5,
            "bridge": 4, "sweeper": 4, "ninjutsu_payoff": 8,
        },
        synergy_tag="satoru",
        priority_roles=["evasive_enabler", "etb_payoff", "protection", "interaction"],
        functional_hand_definition="viable mana + evasive enabler + interaction or payoff",
        high_mv_target=6,
    ),

    "yuriko_tempo": Profile(
        id="yuriko_tempo",
        commander="Yuriko, the Tiger's Shadow",
        display_name="Yuriko Combat Tempo",
        description="One-drops set up ninjutsu chains for Yuriko reveals.",
        land_target=34,
        role_targets={
            "evasive_enabler":  RoleTarget(min=13, preferred=16),
            "high_mana_reveal": RoleTarget(min=5,  preferred=8),
            "topdeck_setup":    RoleTarget(min=4,  preferred=7),
            "draw":             RoleTarget(min=6,  preferred=10),
            "interaction":      RoleTarget(min=10, preferred=14),
            "ramp":             RoleTarget(min=3,  preferred=5),
        },
        role_weights={
            "evasive_enabler": 10, "high_mana_reveal": 9, "topdeck_setup": 8,
            "ninjutsu_payoff": 8, "draw": 7, "selection": 6,
            "counterspell": 5, "creature_removal": 5, "interaction": 5,
            "ramp": 4, "finisher": 5, "engine": 6,
        },
        synergy_tag="yuriko",
        priority_roles=["evasive_enabler", "high_mana_reveal", "topdeck_setup"],
        functional_hand_definition="blue + black mana + evasive one-drop + Yuriko ninjutsu by turn 2-3",
        high_mv_target=10,
    ),

    "talion_control": Profile(
        id="talion_control",
        commander="Talion, the Kindly Lord",
        display_name="Talion Adaptive Control",
        description="Passive damage and card draw trigger off chosen number.",
        land_target=38,
        role_targets={
            "counterspell":     RoleTarget(min=7,  preferred=10),
            "creature_removal": RoleTarget(min=6,  preferred=9),
            "sweeper":          RoleTarget(min=2,  preferred=3),
            "draw":             RoleTarget(min=10, preferred=14),
            "tutor":            RoleTarget(min=2,  preferred=4),
            "ramp":             RoleTarget(min=5,  preferred=7),
        },
        role_weights={
            "draw": 9, "counterspell": 9, "creature_removal": 8,
            "sweeper": 7, "interaction": 7, "tutor": 7,
            "selection": 6, "ramp": 6, "engine": 7,
            "protection": 6, "bridge": 4,
        },
        synergy_tag="talion",
        priority_roles=["draw", "counterspell", "creature_removal", "sweeper"],
        functional_hand_definition="viable mana + early interaction or card advantage",
    ),

    "yuffie_ninjutsu": Profile(
        id="yuffie_ninjutsu",
        commander="Yuffie Kisaragi",
        display_name="Yuffie Ninjutsu Tempo",
        description="Hybrid Satoru/Yuriko style using Yuffie as the ninjutsu enabler commander.",
        land_target=35,
        role_targets={
            "evasive_enabler": RoleTarget(min=12, preferred=15),
            "ninjutsu_payoff": RoleTarget(min=4,  preferred=7),
            "interaction":     RoleTarget(min=12, preferred=16),
            "draw":            RoleTarget(min=7,  preferred=11),
            "ramp":            RoleTarget(min=4,  preferred=6),
        },
        role_weights={
            "evasive_enabler": 9, "ninjutsu_payoff": 9, "draw": 7,
            "selection": 6, "counterspell": 6, "creature_removal": 6,
            "interaction": 6, "ramp": 5, "engine": 7,
            "finisher": 5, "topdeck_setup": 5, "protection": 6,
        },
        synergy_tag="yuriko",
        priority_roles=["evasive_enabler", "ninjutsu_payoff", "interaction"],
        functional_hand_definition="blue + black mana + evasive enabler + ninjutsu payoff",
    ),

    # ── Generic archetypes (work for any commander / color identity) ───────────

    "tempo": Profile(
        id="tempo",
        commander="",
        display_name="Tempo / Aggro",
        description="Low-curve threats, evasion, and disruption. Good for aggressive commanders that want to attack early.",
        land_target=34,
        role_targets={
            "evasive_enabler": RoleTarget(min=8,  preferred=14),
            "interaction":     RoleTarget(min=10, preferred=15),
            "creature_removal":RoleTarget(min=5,  preferred=8),
            "draw":            RoleTarget(min=6,  preferred=10),
            "ramp":            RoleTarget(min=3,  preferred=5),
        },
        role_weights={
            "evasive_enabler": 8, "interaction": 7, "draw": 7,
            "creature_removal": 6, "counterspell": 5, "ramp": 4,
            "engine": 5, "finisher": 6, "bridge": 5, "protection": 5,
            "etb_payoff": 6, "ninjutsu_payoff": 5,
        },
        synergy_tag="",
        priority_roles=["evasive_enabler", "interaction", "creature_removal"],
        functional_hand_definition="viable mana + early threat + interaction",
    ),

    "control": Profile(
        id="control",
        commander="",
        display_name="Control",
        description="Heavy interaction, card draw, and late-game value. Good for commanders that reward answering threats.",
        land_target=38,
        role_targets={
            "counterspell":     RoleTarget(min=6,  preferred=10),
            "creature_removal": RoleTarget(min=6,  preferred=9),
            "sweeper":          RoleTarget(min=2,  preferred=4),
            "draw":             RoleTarget(min=10, preferred=15),
            "ramp":             RoleTarget(min=5,  preferred=8),
            "tutor":            RoleTarget(min=2,  preferred=4),
        },
        role_weights={
            "draw": 9, "counterspell": 9, "creature_removal": 8,
            "sweeper": 8, "tutor": 7, "ramp": 6, "engine": 8,
            "protection": 6, "selection": 5, "interaction": 6,
        },
        synergy_tag="",
        priority_roles=["draw", "counterspell", "creature_removal", "sweeper"],
        functional_hand_definition="viable mana + early interaction or card advantage",
    ),

    "midrange": Profile(
        id="midrange",
        commander="",
        display_name="Midrange",
        description="Balanced curve with ramp, interaction, and powerful threats. Good for value-oriented commanders.",
        land_target=36,
        role_targets={
            "ramp":             RoleTarget(min=6,  preferred=9),
            "draw":             RoleTarget(min=8,  preferred=12),
            "creature_removal": RoleTarget(min=5,  preferred=8),
            "interaction":      RoleTarget(min=10, preferred=14),
        },
        role_weights={
            "ramp": 8, "draw": 8, "creature_removal": 7, "interaction": 6,
            "engine": 8, "finisher": 6, "etb_payoff": 6, "tutor": 6,
            "sweeper": 5, "counterspell": 5, "selection": 5,
        },
        synergy_tag="",
        priority_roles=["ramp", "draw", "creature_removal", "engine"],
        functional_hand_definition="viable mana + ramp or draw + threat or interaction",
    ),

    "value": Profile(
        id="value",
        commander="",
        display_name="Combo / Value",
        description="Tutors, engines, and self-synergy. Good for commanders that assemble specific card combinations.",
        land_target=36,
        role_targets={
            "tutor":       RoleTarget(min=5,  preferred=9),
            "draw":        RoleTarget(min=10, preferred=15),
            "ramp":        RoleTarget(min=6,  preferred=9),
            "protection":  RoleTarget(min=3,  preferred=6),
            "interaction": RoleTarget(min=8,  preferred=12),
        },
        role_weights={
            "tutor": 10, "engine": 9, "draw": 9, "ramp": 7,
            "protection": 7, "interaction": 6, "etb_payoff": 7,
            "selection": 6, "counterspell": 5,
        },
        synergy_tag="",
        priority_roles=["tutor", "engine", "draw", "protection"],
        functional_hand_definition="viable mana + tutor or engine + protection",
    ),
}
