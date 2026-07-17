"""Template matching + commander/strategy fit scoring.

Formula (per commander/template):

    commander_alignment = weighted average of required + optional tag weights
                          (required tags fully weighted, optional half-weighted)
                        - veto from conflicting tags

    arena_support_depth = fraction of strategy_role_targets whose preferred_count
                          can plausibly be met by the arena pool (color-restricted)

    fit = 0.75 * commander_alignment + 0.25 * arena_support_depth

Because ``arena_support_depth`` requires role classification data (populated by
``cards.classify_all_cards``), the strategy step must run *after* the card
classification step.  When role data is missing (first run), we set the
support term to a neutral 0.5 so the pipeline can still bootstrap.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from typing import Dict, List, Sequence, Tuple

from ..rules.templates import ROLE_TARGETS, TEMPLATE_VERSION, TEMPLATES, Template

log = logging.getLogger(__name__)


STATUS_THRESHOLDS = (
    ("recommended",  0.75),
    ("viable",       0.60),
    ("experimental", 0.45),
)


# ---------------------------------------------------------------------------
# Template seeding.
# ---------------------------------------------------------------------------
def seed_templates(conn: sqlite3.Connection) -> None:
    rows = [
        (
            t.id, t.name, t.display_name, t.macro_plan, t.theme, t.win_condition,
            json.dumps(list(t.required_tags)),
            json.dumps(list(t.optional_tags)),
            json.dumps(list(t.conflicting_tags)),
            json.dumps(list(t.needed_roles)),
            t.min_arena_depth,
            t.required_threshold,
            t.description,
        )
        for t in TEMPLATES
    ]
    with conn:
        conn.execute("DELETE FROM strategy_templates")
        conn.executemany(
            "INSERT INTO strategy_templates ("
            "id, name, display_name, macro_plan, theme, win_condition,"
            " required_tags, optional_tags, conflicting_tags, needed_roles,"
            " min_arena_depth, required_threshold, description"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        # Role targets.
        conn.execute("DELETE FROM strategy_role_targets")
        for tid, targets in ROLE_TARGETS.items():
            conn.executemany(
                "INSERT INTO strategy_role_targets "
                "(strategy_template_id, role, min_count, preferred_count, weight) "
                "VALUES (?, ?, ?, ?, ?)",
                [(tid, role, mn, pf, w) for (role, mn, pf, w) in targets],
            )


# ---------------------------------------------------------------------------
# Alignment computation.
# ---------------------------------------------------------------------------
def commander_alignment(
    template: Template,
    tag_weights: Dict[str, float],
) -> tuple[float, list[dict]]:
    """Return (alignment, per-tag contribution list)."""
    contributions: list[dict] = []

    # Required tags dominate.
    req_sum = 0.0
    req_hits = 0
    req_missing = 0
    for tag in template.required_tags:
        w = tag_weights.get(tag, 0.0)
        contributions.append({
            "tag": tag, "role": "required", "weight": w,
        })
        if w >= template.required_threshold:
            req_sum += w
            req_hits += 1
        else:
            req_missing += 1

    if not template.required_tags:
        required_score = 0.5  # theme-agnostic template (rare)
    elif req_missing > 0:
        # Even a partial hit still returns *some* value, but capped low.
        required_score = (req_sum / len(template.required_tags)) * 0.4
    else:
        required_score = req_sum / len(template.required_tags)

    # Optional tags add smaller, decaying bonus.
    opt_sum = 0.0
    for tag in template.optional_tags:
        w = tag_weights.get(tag, 0.0)
        contributions.append({
            "tag": tag, "role": "optional", "weight": w,
        })
        opt_sum += 0.5 * w
    if template.optional_tags:
        opt_score = opt_sum / len(template.optional_tags)
    else:
        opt_score = 0.0

    # Conflicting tags veto.
    veto = 0.0
    for tag in template.conflicting_tags:
        w = tag_weights.get(tag, 0.0)
        contributions.append({
            "tag": tag, "role": "conflict", "weight": w,
        })
        veto = max(veto, w)
    veto_penalty = veto * 0.6

    alignment = max(0.0, min(1.0, 0.75 * required_score + 0.35 * opt_score - veto_penalty))
    return alignment, contributions


def build_role_color_index(conn: sqlite3.Connection) -> dict[str, list[frozenset]]:
    """Precompute, per role, the list of color-identity frozensets for every
    Arena-legal card that has a role weight >= 0.4.

    Used by ``arena_support_depth`` to answer "how many cards of role R exist
    within commander color set C" in O(len(cards_with_role)) per query without
    any SQL / JSON parsing.
    """
    total = conn.execute("SELECT COUNT(*) FROM card_role_weights").fetchone()[0]
    if total == 0:
        return {}
    rows = conn.execute(
        "SELECT r.role AS role, c.color_identity AS ci"
        " FROM card_role_weights r"
        " JOIN cards c ON c.oracle_id = r.oracle_id"
        " WHERE r.weight >= 0.4 AND c.arena_legal = 1"
    ).fetchall()
    index: dict[str, list[frozenset]] = {}
    for r in rows:
        ci = frozenset(json.loads(r["ci"] or "[]"))
        index.setdefault(r["role"], []).append(ci)
    return index


def arena_support_depth(
    template: Template,
    commander_colors: Sequence[str],
    role_targets: list[tuple[str, int]],
    role_color_index: dict[str, list[frozenset]],
) -> float:
    """Fraction of role targets whose preferred_count is reachable."""
    if not role_targets:
        return 0.5
    if not role_color_index:
        return 0.5  # bootstrap: no role weights yet

    color_set = frozenset(commander_colors)
    ok = 0
    for role, preferred in role_targets:
        cards = role_color_index.get(role, ())
        available = 0
        for ci in cards:
            if ci <= color_set:
                available += 1
                if available >= preferred:
                    break
        if available >= preferred:
            ok += 1
    return ok / len(role_targets)


def _status(fit: float) -> str:
    for name, threshold in STATUS_THRESHOLDS:
        if fit >= threshold:
            return name
    return "rejected"


def _confidence(alignment: float, evidence_count: int) -> float:
    """Confidence grows with evidence volume but caps out."""
    base = alignment
    # Each additional piece of evidence adds diminishing certainty.
    conf = base * (1 - math.exp(-max(0, evidence_count) / 4))
    return max(0.0, min(1.0, conf))


# ---------------------------------------------------------------------------
# Pipeline entrypoint.
# ---------------------------------------------------------------------------
def score_all_commanders(conn: sqlite3.Connection) -> int:
    """Compute + persist commander_strategies + evidence."""
    commanders = conn.execute(
        "SELECT oracle_id, name, color_identity FROM cards WHERE is_commander = 1"
    ).fetchall()

    # Precompute the role-color index once.
    role_color_index = build_role_color_index(conn)

    # Precompute per-template role targets (role, preferred_count).
    template_role_targets: dict[str, list[tuple[str, int]]] = {}
    for r in conn.execute(
        "SELECT strategy_template_id, role, preferred_count"
        " FROM strategy_role_targets"
    ):
        template_role_targets.setdefault(r["strategy_template_id"], []).append(
            (r["role"], int(r["preferred_count"]))
        )

    # Preload all commander tag weights in one shot.
    all_tags: dict[str, list[sqlite3.Row]] = {}
    for r in conn.execute(
        "SELECT commander_oracle_id, tag, weight, evidence FROM commander_tag_weights"
    ):
        all_tags.setdefault(r["commander_oracle_id"], []).append(r)

    with conn:
        conn.execute("DELETE FROM commander_strategies")
        conn.execute("DELETE FROM commander_strategy_evidence")

        for cmd in commanders:
            oid = cmd["oracle_id"]
            colors = json.loads(cmd["color_identity"] or "[]")
            tag_rows = all_tags.get(oid, [])
            tag_weights = {r["tag"]: float(r["weight"]) for r in tag_rows}
            tag_evidence = {r["tag"]: json.loads(r["evidence"]) for r in tag_rows}

            for template in TEMPLATES:
                alignment, contribs = commander_alignment(template, tag_weights)
                support = arena_support_depth(
                    template, colors,
                    template_role_targets.get(template.id, []),
                    role_color_index,
                )
                fit = 0.75 * alignment + 0.25 * support
                fit = max(0.0, min(1.0, fit))

                # Evidence count for confidence: number of clauses across
                # required+optional tags that actually fired.
                relevant_tags = set(template.required_tags) | set(template.optional_tags)
                ev_count = sum(
                    len(tag_evidence.get(t, [])) for t in relevant_tags
                )

                status = _status(fit)
                confidence = _confidence(alignment, ev_count)
                explanation = _explanation(template, contribs, support, fit)

                conn.execute(
                    "INSERT INTO commander_strategies "
                    "(commander_oracle_id, strategy_template_id, fit_score,"
                    " status, confidence, review_status, explanation) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (oid, template.id, fit, status, confidence,
                     "pending_review", explanation),
                )

                # Persist evidence for accepted (recommended/viable) strategies
                # so a reviewer can trace exactly why we chose them.
                if status in ("recommended", "viable"):
                    ev_rows = []
                    for tag in template.required_tags + template.optional_tags:
                        for ev in tag_evidence.get(tag, []):
                            ev_rows.append((
                                oid, template.id, tag,
                                ev.get("clause", ""),
                                ev.get("signal", ""),
                                float(ev.get("contribution", 0.0)),
                            ))
                    if ev_rows:
                        conn.executemany(
                            "INSERT INTO commander_strategy_evidence "
                            "(commander_oracle_id, strategy_template_id, tag,"
                            " clause, signal, contribution) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            ev_rows,
                        )

    log.info("scored %d commanders across %d templates", len(commanders), len(TEMPLATES))
    return len(commanders)


def _format_contribs(contribs: List[dict]) -> str:
    pieces = []
    for c in contribs:
        tag = c["tag"]
        w = c["weight"]
        pieces.append(f"{tag}={w:.2f}")
    return ", ".join(pieces)


def _explanation(
    template: Template,
    contribs: List[dict],
    support: float,
    fit: float,
) -> str:
    req = [c for c in contribs if c["role"] == "required"]
    opt = [c for c in contribs if c["role"] == "optional" and c["weight"] > 0]
    con = [c for c in contribs if c["role"] == "conflict" and c["weight"] > 0]
    parts = [f"required=[{_format_contribs(req)}]"]
    if opt:
        parts.append(f"optional=[{_format_contribs(opt)}]")
    if con:
        parts.append(f"conflict=[{_format_contribs(con)}]")
    parts.append(f"support={support:.2f} fit={fit:.2f}")
    return " ".join(parts)
