"""Resolve Arena export names to canonical card database rows."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any


_PUNCTUATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201b": "'",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
})


def card_name_key(name: str) -> str:
    """Return a case-, spacing-, accent-, and punctuation-insensitive key."""
    collapsed = " ".join(name.translate(_PUNCTUATION).split()).casefold()
    decomposed = unicodedata.normalize("NFKD", collapsed)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def build_card_name_index(cards: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index canonical names plus Arena's front-face and rebalanced aliases."""
    card_list = list(cards)
    index: dict[str, dict[str, Any]] = {}

    # Canonical and individual face names always win over derived aliases.
    for card in card_list:
        canonical = card["name"]
        for name in (canonical, *canonical.split(" // ")):
            index.setdefault(card_name_key(name), card)

    # Arena collection data can expose the printed name while Historic Brawl
    # uses the rebalanced A- version. Map it only when no canonical card won.
    for card in card_list:
        for name in card["name"].split(" // "):
            if name.startswith("A-"):
                index.setdefault(card_name_key(name[2:]), card)

    return index


def normalize_collection(
    collection: Iterable[Any],
    card_name_index: Mapping[str, dict[str, Any]],
) -> tuple[set[str], list[str], int]:
    """Return canonical owned names, unmatched inputs, and matched copy count."""
    owned: set[str] = set()
    unmatched: set[str] = set()
    total_copies = 0

    for item in collection:
        if isinstance(item, Mapping):
            name = str(item.get("name", ""))
            count = int(item.get("count", 0))
        else:
            name = str(item.name)
            count = int(item.count)
        if count < 1:
            continue

        normalized = " ".join(name.split())
        card = card_name_index.get(card_name_key(normalized))
        if card is None:
            unmatched.add(normalized)
            continue
        owned.add(card["name"])
        total_copies += count

    return owned, sorted(unmatched, key=card_name_key), total_copies
