"""Load Arena-legal Historic Brawl cards into the strategy database.

Preferred source: the sibling ``backend/data/oracle_cards.json`` Scryfall bulk
snapshot.  It gives us ``oracle_id`` and the per-face detail we need.  Fallback:
the pre-built ``backend/data/cards.db`` (which lacks ``oracle_id`` but is fine
for testing when the JSON is unavailable).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------
def _stable_oracle_id(name: str) -> str:
    """Fabricate a deterministic ID when the Scryfall UUID is unavailable."""
    return "af-" + hashlib.md5(name.encode("utf-8")).hexdigest()


def _is_commander_eligible(type_line: str, oracle_text: str) -> bool:
    is_legendary = "Legendary" in type_line
    is_creature = "Creature" in type_line
    is_planeswalker = "Planeswalker" in type_line
    can_be_commander = "can be your commander" in (oracle_text or "").lower()
    return is_legendary and (is_creature or is_planeswalker or can_be_commander)


def _combine_faces(card: dict) -> str:
    faces = card.get("card_faces") or []
    if not faces:
        return card.get("oracle_text", "") or ""
    parts = []
    for face in faces:
        text = face.get("oracle_text") or ""
        if text:
            parts.append(text)
    return "\n\n".join(parts) if parts else (card.get("oracle_text", "") or "")


def _combine_type_line(card: dict) -> str:
    if card.get("type_line"):
        return card["type_line"]
    faces = card.get("card_faces") or []
    return " // ".join(f.get("type_line", "") for f in faces if f.get("type_line"))


def _face_summary(card: dict) -> list[dict]:
    faces = card.get("card_faces") or []
    if not faces:
        return [{
            "name":        card.get("name", ""),
            "type_line":   card.get("type_line", ""),
            "oracle_text": card.get("oracle_text", ""),
            "mana_cost":   card.get("mana_cost", ""),
            "power":       card.get("power"),
            "toughness":   card.get("toughness"),
        }]
    return [{
        "name":        f.get("name", ""),
        "type_line":   f.get("type_line", ""),
        "oracle_text": f.get("oracle_text", ""),
        "mana_cost":   f.get("mana_cost", ""),
        "power":       f.get("power"),
        "toughness":   f.get("toughness"),
    } for f in faces]


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
@dataclass
class CardRow:
    oracle_id: str
    name: str
    color_identity: list[str]
    cmc: float
    type_line: str
    oracle_text: str
    faces: list[dict]
    keywords: list[str]
    power: str | None
    toughness: str | None
    rarity: str
    is_land: int
    is_creature: int
    is_legendary: int
    is_commander: int
    arena_legal: int = 1


# ---------------------------------------------------------------------------
# Sources.
# ---------------------------------------------------------------------------
def iter_from_scryfall_json(path: Path) -> Iterator[CardRow]:
    with open(path, "rb") as f:
        data = json.load(f)
    for card in data:
        layout = card.get("layout", "")
        if layout in ("token", "art_series", "double_faced_token", "emblem", "vanguard"):
            continue
        legalities = card.get("legalities", {}) or {}
        if legalities.get("brawl") != "legal":
            continue
        # Only Arena-available printings; Scryfall marks games via ``games``.
        games = card.get("games", []) or []
        arena_legal = 1 if "arena" in games else 0
        # Historic Brawl cards not on Arena still slip in via unlocks; keep them
        # but mark arena_legal so the pipeline can filter downstream.
        type_line = _combine_type_line(card)
        oracle_text = _combine_faces(card)
        yield CardRow(
            oracle_id      = card.get("oracle_id") or _stable_oracle_id(card["name"]),
            name           = card["name"],
            color_identity = list(card.get("color_identity", [])),
            cmc            = float(card.get("cmc", 0)),
            type_line      = type_line,
            oracle_text    = oracle_text,
            faces          = _face_summary(card),
            keywords       = list(card.get("keywords", [])),
            power          = card.get("power"),
            toughness      = card.get("toughness"),
            rarity         = card.get("rarity", "common"),
            is_land        = int("Land" in type_line),
            is_creature    = int("Creature" in type_line),
            is_legendary   = int("Legendary" in type_line),
            is_commander   = int(_is_commander_eligible(type_line, oracle_text)),
            arena_legal    = arena_legal,
        )


def iter_from_cards_db(path: Path) -> Iterator[CardRow]:
    """Fallback: read the backend's cards.db (no oracle_id available)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM cards").fetchall()
    finally:
        conn.close()
    for r in rows:
        oracle_text = r["oracle_text"] or ""
        type_line = r["type_line"] or ""
        yield CardRow(
            oracle_id      = _stable_oracle_id(r["name"]),
            name           = r["name"],
            color_identity = json.loads(r["color_identity"] or "[]"),
            cmc            = float(r["cmc"] or 0),
            type_line      = type_line,
            oracle_text    = oracle_text,
            faces          = [{
                "name":        r["name"],
                "type_line":   type_line,
                "oracle_text": oracle_text,
                "mana_cost":   r["mana_cost"] or "",
                "power":       r["power"],
                "toughness":   r["toughness"],
            }],
            keywords       = json.loads(r["keywords"] or "[]"),
            power          = r["power"],
            toughness      = r["toughness"],
            rarity         = r["rarity"] or "common",
            is_land        = int(r["is_land"] or 0),
            is_creature    = int(r["is_creature"] or 0),
            is_legendary   = int(r["is_legendary"] or 0),
            is_commander   = int(r["is_commander"] or 0),
            arena_legal    = 1,
        )


# ---------------------------------------------------------------------------
# Insertion.
# ---------------------------------------------------------------------------
UPSERT = """
INSERT INTO cards (
    oracle_id, name, color_identity, cmc, type_line, oracle_text,
    faces, keywords, power, toughness, rarity, is_land, is_creature,
    is_legendary, is_commander, arena_legal
) VALUES (
    :oracle_id, :name, :color_identity, :cmc, :type_line, :oracle_text,
    :faces, :keywords, :power, :toughness, :rarity, :is_land, :is_creature,
    :is_legendary, :is_commander, :arena_legal
)
ON CONFLICT(oracle_id) DO UPDATE SET
    name           = excluded.name,
    color_identity = excluded.color_identity,
    cmc            = excluded.cmc,
    type_line      = excluded.type_line,
    oracle_text    = excluded.oracle_text,
    faces          = excluded.faces,
    keywords       = excluded.keywords,
    power          = excluded.power,
    toughness      = excluded.toughness,
    rarity         = excluded.rarity,
    is_land        = excluded.is_land,
    is_creature    = excluded.is_creature,
    is_legendary   = excluded.is_legendary,
    is_commander   = excluded.is_commander,
    arena_legal    = excluded.arena_legal
"""


def upsert_cards(conn: sqlite3.Connection, cards: Iterable[CardRow]) -> int:
    rows = [{
        "oracle_id":      c.oracle_id,
        "name":           c.name,
        "color_identity": json.dumps(sorted(c.color_identity)),
        "cmc":            c.cmc,
        "type_line":      c.type_line,
        "oracle_text":    c.oracle_text,
        "faces":          json.dumps(c.faces),
        "keywords":       json.dumps(sorted(c.keywords)),
        "power":          c.power,
        "toughness":      c.toughness,
        "rarity":         c.rarity,
        "is_land":        c.is_land,
        "is_creature":    c.is_creature,
        "is_legendary":   c.is_legendary,
        "is_commander":   c.is_commander,
        "arena_legal":    c.arena_legal,
    } for c in cards]
    with conn:
        conn.executemany(UPSERT, rows)
    return len(rows)


def load_cards(
    conn: sqlite3.Connection,
    scryfall_json: Path | None,
    cards_db: Path | None,
) -> tuple[int, str]:
    """Prefer Scryfall JSON; fall back to cards.db.

    Returns (row_count, source_label).
    """
    if scryfall_json and scryfall_json.exists():
        rows = list(iter_from_scryfall_json(scryfall_json))
        upsert_cards(conn, rows)
        return len(rows), f"scryfall_json:{scryfall_json.name}"
    if cards_db and cards_db.exists():
        rows = list(iter_from_cards_db(cards_db))
        upsert_cards(conn, rows)
        return len(rows), f"cards_db:{cards_db.name}"
    raise FileNotFoundError("No Scryfall JSON or cards.db source available.")
