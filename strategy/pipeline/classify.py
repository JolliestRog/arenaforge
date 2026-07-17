"""Commander tag scoring.

For each commander we:
    1. Split the (per-face) oracle text into clauses.
    2. Run every rule in ``rules.signals`` against every clause.
    3. Aggregate contributions per tag using an inclusive-OR curve so a lot of
       independent evidence pushes the weight toward 1.0 without exceeding it.
    4. Persist commander_tag_weights with evidence blobs.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import asdict
from typing import Dict, Iterable, List, Sequence, Tuple

from ..rules.signals import SignalHit, TAG_CATALOG, scan

log = logging.getLogger(__name__)


def _aggregate(contributions: Sequence[float]) -> float:
    """Inclusive-OR aggregator: 1 - prod(1 - c).

    Each independent contribution can only *raise* the weight, but the total
    stays within [0, 1]. Larger single contributions still dominate.
    """
    remaining = 1.0
    for c in contributions:
        c = max(0.0, min(1.0, c))
        remaining *= (1.0 - c)
    return 1.0 - remaining


def classify_commander(name: str, oracle_text: str) -> Dict[str, Dict]:
    """Return {tag: {weight, evidence[]}} for one commander."""
    hits = scan(name, oracle_text)
    by_tag: Dict[str, List[SignalHit]] = defaultdict(list)
    for hit in hits:
        by_tag[hit.tag].append(hit)

    result: Dict[str, Dict] = {}
    for tag, tag_hits in by_tag.items():
        contributions = [h.contribution for h in tag_hits]
        weight = _aggregate(contributions)
        result[tag] = {
            "weight": weight,
            "evidence": [
                {
                    "source":       "oracle_text",
                    "clause":       h.clause,
                    "signal":       h.signal,
                    "contribution": h.contribution,
                }
                for h in tag_hits
            ],
        }
    return result


# ---------------------------------------------------------------------------
# Persistence.
# ---------------------------------------------------------------------------
def seed_tag_catalog(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO strategy_tags (tag, category, description) "
            "VALUES (?, ?, ?)",
            TAG_CATALOG,
        )


def classify_all_commanders(conn: sqlite3.Connection) -> int:
    """Compute + persist tag weights for every commander in the DB."""
    cur = conn.execute(
        "SELECT oracle_id, name, oracle_text FROM cards WHERE is_commander = 1"
    )
    commanders = cur.fetchall()
    with conn:
        conn.execute("DELETE FROM commander_tag_weights")
        for row in commanders:
            oid = row["oracle_id"]
            tags = classify_commander(row["name"], row["oracle_text"] or "")
            conn.executemany(
                "INSERT INTO commander_tag_weights "
                "(commander_oracle_id, tag, weight, evidence) VALUES (?, ?, ?, ?)",
                [
                    (oid, tag, tag_data["weight"], json.dumps(tag_data["evidence"]))
                    for tag, tag_data in tags.items()
                    if tag_data["weight"] > 0
                ],
            )
    log.info("classified %d commanders", len(commanders))
    return len(commanders)


def load_commander_tags(conn: sqlite3.Connection, oracle_id: str) -> Dict[str, Dict]:
    rows = conn.execute(
        "SELECT tag, weight, evidence FROM commander_tag_weights "
        "WHERE commander_oracle_id = ?",
        (oracle_id,),
    ).fetchall()
    return {
        r["tag"]: {"weight": float(r["weight"]), "evidence": json.loads(r["evidence"])}
        for r in rows
    }
