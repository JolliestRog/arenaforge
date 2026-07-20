"""Shared wildcard accounting for analysis and deck builds."""

from __future__ import annotations

from collections.abc import Mapping

from solver.model import DeckCard, WC_VALUES

WILDCARD_RARITIES = ("common", "uncommon", "rare", "mythic")


def deck_wildcard_cost(cards: list[DeckCard]) -> dict[str, int]:
    """Count wildcards needed for the 99 cards in a solved deck."""
    costs = {rarity: 0 for rarity in WILDCARD_RARITIES}
    for deck_card in cards:
        rarity = deck_card.wildcard_cost
        if rarity in costs:
            costs[rarity] += 1
    return costs


def commander_wildcard_rarity(
    commander: Mapping[str, object],
    commander_owned: bool,
) -> str | None:
    """Return the wildcard consumed by a commander, if it is craftable."""
    rarity = commander.get("rarity")
    if commander_owned or rarity not in WILDCARD_RARITIES:
        return None
    return str(rarity)


def completion_wildcard_cost(
    cards: list[DeckCard],
    commander: Mapping[str, object],
    commander_owned: bool,
) -> dict[str, int]:
    """Count deck and commander wildcards using one canonical rule."""
    costs = deck_wildcard_cost(cards)
    rarity = commander_wildcard_rarity(commander, commander_owned)
    if rarity is not None:
        costs[rarity] += 1
    return costs


def wildcard_points(costs: Mapping[str, int]) -> int:
    """Return the weighted wildcard value used by recommendation ranking."""
    return sum(
        costs.get(rarity, 0) * WC_VALUES[rarity]
        for rarity in WILDCARD_RARITIES
    )


def reserve_commander_wildcard(
    budget: Mapping[str, int],
    commander: Mapping[str, object],
    commander_owned: bool,
) -> dict[str, int] | None:
    """Reserve commander cost before solving; return None if it cannot fit."""
    remaining = {
        rarity: int(budget.get(rarity, 0))
        for rarity in WILDCARD_RARITIES
    }
    rarity = commander_wildcard_rarity(commander, commander_owned)
    if rarity is None:
        return remaining
    if remaining[rarity] < 1:
        return None
    remaining[rarity] -= 1
    return remaining
