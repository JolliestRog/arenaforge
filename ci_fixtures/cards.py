"""Generate a compact Scryfall-shaped card snapshot for CI.

The runtime databases are intentionally ignored.  Tests build both SQLite
databases from this deterministic snapshot so a clean checkout exercises the
real ingestion, strategy, analysis, and solver code without network access.
"""

from __future__ import annotations

import json
from pathlib import Path


def _card(
    name: str,
    *,
    colors: tuple[str, ...] = (),
    type_line: str = "Artifact",
    oracle_text: str = "",
    mana_cost: str = "{2}",
    cmc: float = 2,
    rarity: str = "common",
    keywords: tuple[str, ...] = (),
    power: str | None = None,
    toughness: str | None = None,
    produced_mana: tuple[str, ...] = (),
    card_faces: list[dict] | None = None,
) -> dict:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    result = {
        "id": f"fixture-print-{slug}",
        "oracle_id": f"fixture-oracle-{slug}",
        "name": name,
        "layout": "transform" if card_faces else "normal",
        "games": ["arena"],
        "legalities": {"brawl": "legal"},
        "color_identity": list(colors),
        "colors": list(colors),
        "mana_cost": mana_cost,
        "cmc": cmc,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "rarity": rarity,
        "keywords": list(keywords),
        "power": power,
        "toughness": toughness,
        "produced_mana": list(produced_mana),
    }
    if card_faces:
        result["card_faces"] = card_faces
    return result


def _commanders() -> list[dict]:
    return [
        _card(
            "Lorthos, the Tidemaker",
            colors=("U",),
            type_line="Legendary Creature — Octopus",
            oracle_text=(
                "Whenever Lorthos attacks, you may pay {8}. If you do, tap up "
                "to eight target permanents. Those permanents don't untap "
                "during their controllers' next untap steps."
            ),
            mana_cost="{5}{U}{U}{U}",
            cmc=8,
            rarity="rare",
            power="8",
            toughness="8",
        ),
        _card(
            "A-Satoru Umezawa",
            colors=("U", "B"),
            type_line="Legendary Creature — Human Ninja",
            oracle_text=(
                "Whenever you activate a ninjutsu ability, look at the top "
                "three cards of your library, then put one of them into your "
                "hand. Each creature card in your hand has ninjutsu {2}{U}{B}."
            ),
            mana_cost="{1}{U}{B}",
            cmc=3,
            rarity="rare",
            power="2",
            toughness="4",
        ),
        _card(
            "Light-Paws, Emperor's Voice",
            colors=("W",),
            type_line="Legendary Creature — Fox Advisor",
            oracle_text=(
                "Whenever an Aura enters the battlefield under your control, "
                "search your library for an Aura card."
            ),
            mana_cost="{1}{W}",
            cmc=2,
            rarity="rare",
            power="2",
            toughness="2",
        ),
        _card(
            "Fixture Death Celebrant",
            colors=("W", "B"),
            type_line="Legendary Creature — Human Cleric",
            oracle_text=(
                "Whenever another creature you control dies, each opponent "
                "loses 1 life and you gain 1 life."
            ),
            mana_cost="{1}{W}{B}",
            cmc=3,
            rarity="rare",
            power="2",
            toughness="3",
        ),
        _card(
            "Fixture Spell Captain",
            colors=("U", "R"),
            type_line="Legendary Creature — Bird Wizard",
            oracle_text=(
                "Flying. Whenever you cast an instant or sorcery spell, draw "
                "a card, then discard a card."
            ),
            mana_cost="{U}{R}",
            cmc=2,
            rarity="rare",
            keywords=("Flying",),
            power="1",
            toughness="3",
        ),
    ]


def _basics() -> list[dict]:
    specs = (
        ("Plains", "W"),
        ("Island", "U"),
        ("Swamp", "B"),
        ("Mountain", "R"),
        ("Forest", "G"),
    )
    cards = [
        _card(
            name,
            colors=(color,),
            type_line=f"Basic Land — {name}",
            oracle_text=f"{{T}}: Add {{{color}}}.",
            mana_cost="",
            cmc=0,
            produced_mana=(color,),
        )
        for name, color in specs
    ]
    cards.append(
        _card(
            "Wastes",
            type_line="Basic Land",
            oracle_text="{T}: Add {C}.",
            mana_cost="",
            cmc=0,
            produced_mana=("C",),
        )
    )
    return cards


def _role_cards() -> list[dict]:
    specs = (
        ("Ramp", "Artifact", "{T}: Add {C}.", (), 2),
        ("Draw", "Sorcery", "Draw two cards.", (), 3),
        ("Removal", "Instant", "Destroy target creature.", (), 2),
        ("Counter", "Instant", "Counter target spell.", (), 2),
        ("Wipe", "Sorcery", "Destroy all creatures.", (), 5),
        ("Protection", "Instant", "Target creature gains indestructible until end of turn.", (), 1),
        ("Recursion", "Sorcery", "Return target creature card from your graveyard to the battlefield.", (), 5),
        ("Sacrifice", "Artifact Creature — Construct", "Sacrifice another creature: Draw a card.", (), 2),
        ("Token", "Sorcery", "Create two 1/1 colorless Servo artifact creature tokens.", (), 3),
        ("Death", "Artifact Creature — Cleric", "Whenever another creature you control dies, draw a card.", (), 3),
        ("Blink", "Instant", "Exile target creature, then return it to the battlefield.", (), 2),
        ("Artifact", "Artifact Creature — Artificer", "Whenever another artifact enters, draw a card.", (), 3),
        ("Enchantment", "Enchantment Creature", "Whenever another enchantment enters, draw a card.", (), 3),
        ("Aura", "Enchantment — Aura", "Enchant creature. Enchanted creature gets +2/+2 and has flying.", (), 2),
        ("Countermaker", "Artifact Creature — Golem", "Put a +1/+1 counter on target creature.", (), 2),
        ("Evasive", "Artifact Creature — Thopter", "Flying", ("Flying",), 1),
        ("Ninja", "Artifact Creature — Ninja", "Ninjutsu {2}. When this creature enters, draw a card.", (), 3),
        ("Topdeck", "Instant", "Scry 2, then draw a card.", (), 1),
        ("Tap", "Artifact", "Tap target permanent. It doesn't untap during its controller's next untap step.", (), 3),
        ("Finisher", "Artifact Creature — Giant", "Flying, trample", ("Flying", "Trample"), 8),
    )
    cards: list[dict] = []
    for index in range(160):
        label, type_line, text, keywords, cmc = specs[index % len(specs)]
        creature = "Creature" in type_line
        cards.append(
            _card(
                f"Fixture {label} {index + 1:03d}",
                type_line=type_line,
                oracle_text=text,
                cmc=cmc,
                rarity=("common", "uncommon", "rare")[index % 3],
                keywords=keywords,
                power="2" if creature else None,
                toughness="2" if creature else None,
            )
        )
    return cards


def fixture_cards() -> list[dict]:
    cards = [*_commanders(), *_basics(), *_role_cards()]
    cards.append(
        _card(
            "A-Lantern Bearer // A-Lanterns' Lift",
            colors=("U",),
            type_line="Creature — Spirit // Enchantment — Aura",
            oracle_text="Flying // Enchant creature",
            mana_cost="{U}",
            cmc=1,
            card_faces=[
                {
                    "name": "A-Lantern Bearer",
                    "type_line": "Creature — Spirit",
                    "oracle_text": "Flying",
                    "mana_cost": "{U}",
                    "power": "1",
                    "toughness": "1",
                },
                {
                    "name": "A-Lanterns' Lift",
                    "type_line": "Enchantment — Aura",
                    "oracle_text": "Enchant creature",
                    "mana_cost": "{2}{U}",
                    "power": None,
                    "toughness": None,
                },
            ],
        )
    )
    return cards


def write_snapshot(path: Path) -> Path:
    path.write_text(json.dumps(fixture_cards(), indent=2, sort_keys=True) + "\n")
    return path
