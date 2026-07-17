"""Parse Scryfall oracle_cards JSON and load Historic Brawl-legal cards into SQLite."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterator

from .schema import init_db


def _is_commander_eligible(card: dict) -> bool:
    type_line = card.get("type_line", "")
    oracle = card.get("oracle_text", "")
    is_legendary = "Legendary" in type_line
    is_creature = "Creature" in type_line
    is_planeswalker = "Planeswalker" in type_line
    can_be_commander = "can be your commander" in oracle.lower()
    return is_legendary and (is_creature or is_planeswalker or can_be_commander)


def _iter_hb_cards(cards_path: Path) -> Iterator[dict]:
    """Yield Historic Brawl-legal cards from the Scryfall JSON file."""
    with open(cards_path, "rb") as f:
        data = json.load(f)

    for card in data:
        # Skip tokens, art cards, etc.
        if card.get("layout") in ("token", "art_series", "double_faced_token", "emblem"):
            continue
        legalities = card.get("legalities", {})
        if legalities.get("brawl") != "legal":
            continue
        # For split/adventure cards Scryfall gives us the combined face in oracle
        yield card


def _card_to_row(card: dict) -> dict:
    type_line = card.get("type_line", "")
    return {
        "name": card["name"],
        "mana_cost": card.get("mana_cost") or None,
        "cmc": float(card.get("cmc", 0)),
        "color_identity": json.dumps(card.get("color_identity", [])),
        "type_line": type_line,
        "rarity": card.get("rarity", "common"),
        "oracle_text": card.get("oracle_text", ""),
        "keywords": json.dumps(card.get("keywords", [])),
        "power": card.get("power"),
        "toughness": card.get("toughness"),
        "is_land": int("Land" in type_line),
        "is_creature": int("Creature" in type_line),
        "is_legendary": int("Legendary" in type_line),
        "is_commander": int(_is_commander_eligible(card)),
    }


UPSERT = """
INSERT INTO cards (
    name, mana_cost, cmc, color_identity, type_line,
    rarity, oracle_text, keywords, power, toughness,
    is_land, is_creature, is_legendary, is_commander
) VALUES (
    :name, :mana_cost, :cmc, :color_identity, :type_line,
    :rarity, :oracle_text, :keywords, :power, :toughness,
    :is_land, :is_creature, :is_legendary, :is_commander
)
ON CONFLICT(name) DO UPDATE SET
    mana_cost      = excluded.mana_cost,
    cmc            = excluded.cmc,
    color_identity = excluded.color_identity,
    type_line      = excluded.type_line,
    rarity         = excluded.rarity,
    oracle_text    = excluded.oracle_text,
    keywords       = excluded.keywords,
    power          = excluded.power,
    toughness      = excluded.toughness,
    is_land        = excluded.is_land,
    is_creature    = excluded.is_creature,
    is_legendary   = excluded.is_legendary,
    is_commander   = excluded.is_commander
"""


def ingest(cards_path: Path) -> int:
    conn = init_db()
    rows = [_card_to_row(c) for c in _iter_hb_cards(cards_path)]
    t0 = time.time()
    with conn:
        conn.executemany(UPSERT, rows)
    elapsed = time.time() - t0
    count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    print(f"[ingest] {len(rows)} cards upserted in {elapsed:.2f}s — {count} total in DB")
    return len(rows)
