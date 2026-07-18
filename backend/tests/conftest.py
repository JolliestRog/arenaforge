"""Shared fixtures for backend tests.

The tests run against the real cards.db and strategy.db on the host path.
All tests that need the DBs are skipped if either DB is absent (e.g., CI without
the data volume mounted).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make backend importable without an install step.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

CARDS_DB   = BACKEND_DIR / "data" / "cards.db"
# Strategy DB is at different paths on host vs container.
_STRAT_CANDIDATES = [
    BACKEND_DIR / "strategy_data" / "strategy.db",           # container (volume mount)
    BACKEND_DIR.parent / "strategy" / "data" / "strategy.db", # host layout
]
STRATEGY_DB = next((p for p in _STRAT_CANDIDATES if p.exists()), _STRAT_CANDIDATES[0])


@pytest.fixture(scope="session", autouse=True)
def init_databases():
    """Initialize the global DB connections used by the backend modules."""
    if not CARDS_DB.exists() or not STRATEGY_DB.exists():
        pytest.skip("cards.db or strategy.db not found — skipping integration tests")

    import db
    import strategy_db
    db.init()
    strategy_db.init()
    yield
    db.close()
    strategy_db.close()


# ── Fixture collections ────────────────────────────────────────────────────────

# A small control-leaning collection: counterspells, removal, draw, some ramp.
# Deliberately weak in token/aggro pieces. Cards must exist in the real cards DB.
CONTROL_FIXTURE = [
    {"name": "Counterspell",          "count": 1},
    {"name": "Negate",                "count": 1},
    {"name": "Mana Leak",             "count": 1},
    {"name": "Cancel",                "count": 1},
    {"name": "Doom Blade",            "count": 1},
    {"name": "Go for the Throat",     "count": 1},
    {"name": "Murder",                "count": 1},
    {"name": "Tragic Slip",           "count": 1},
    {"name": "Divination",            "count": 1},
    {"name": "Ponder",                "count": 1},
    {"name": "Preordain",             "count": 1},
    {"name": "Brainstorm",            "count": 1},
    {"name": "Opt",                   "count": 1},
    {"name": "Think Twice",           "count": 1},
    {"name": "Thought Scour",         "count": 1},
    {"name": "Disallow",              "count": 1},
    {"name": "Absorb",                "count": 1},
    {"name": "Wrath of God",          "count": 1},
    {"name": "Damnation",             "count": 1},
    {"name": "Languish",              "count": 1},
    {"name": "Arcane Denial",         "count": 1},
    {"name": "Swan Song",             "count": 1},
    {"name": "Spell Pierce",          "count": 1},
    {"name": "Demonic Tutor",         "count": 1},
    {"name": "Rhystic Study",         "count": 1},
    {"name": "Phyrexian Arena",       "count": 1},
    {"name": "Sign in Blood",         "count": 1},
    {"name": "Night's Whisper",       "count": 1},
    {"name": "Sol Ring",              "count": 1},
    {"name": "Arcane Signet",         "count": 1},
    {"name": "Commander's Sphere",    "count": 1},
    {"name": "Dimir Signet",          "count": 1},
    {"name": "Talisman of Dominance", "count": 1},
    {"name": "Path to Exile",         "count": 1},
    {"name": "Swords to Plowshares",  "count": 1},
    {"name": "Condemn",               "count": 1},
    {"name": "Cryptic Command",       "count": 1},
    {"name": "Force Spike",           "count": 1},
    {"name": "Mystical Tutor",        "count": 1},
    {"name": "Scheming Symmetry",     "count": 1},
]

# Intentionally empty collection to test worst-case / cheapest-path behaviour.
EMPTY_FIXTURE: list[dict] = []
