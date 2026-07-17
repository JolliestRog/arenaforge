"""Generate a human-review JSON report for the strategy database."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from .migrate import DEFAULT_DB, connect


def _load_commander_row(conn: sqlite3.Connection, oid: str) -> dict:
    row = conn.execute(
        "SELECT oracle_id, name, color_identity, type_line, oracle_text"
        " FROM cards WHERE oracle_id = ?",
        (oid,),
    ).fetchone()
    return dict(row) if row else {}


def build_report(conn: sqlite3.Connection) -> dict:
    commanders = conn.execute(
        "SELECT DISTINCT commander_oracle_id AS oid FROM commander_strategies"
    ).fetchall()

    templates = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM strategy_templates")
    }

    report = {"commanders": []}
    for row in commanders:
        oid = row["oid"]
        cmd = _load_commander_row(conn, oid)
        if not cmd:
            continue

        strat_rows = conn.execute(
            "SELECT strategy_template_id AS tid, fit_score, status,"
            "       confidence, review_status, explanation"
            " FROM commander_strategies WHERE commander_oracle_id = ?"
            " ORDER BY fit_score DESC",
            (oid,),
        ).fetchall()

        proposed = []
        rejected_close = []
        for s in strat_rows:
            tpl = templates.get(s["tid"], {})
            evidence = conn.execute(
                "SELECT tag, clause, signal, contribution"
                " FROM commander_strategy_evidence"
                " WHERE commander_oracle_id = ? AND strategy_template_id = ?",
                (oid, s["tid"]),
            ).fetchall()
            entry = {
                "id":         s["tid"],
                "display":    tpl.get("display_name", s["tid"]),
                "macro_plan": tpl.get("macro_plan"),
                "theme":      tpl.get("theme"),
                "wincon":     tpl.get("win_condition"),
                "fit":        float(s["fit_score"]),
                "status":     s["status"],
                "confidence": float(s["confidence"]),
                "review":     s["review_status"],
                "explanation": s["explanation"],
                "evidence": [
                    {
                        "tag":         e["tag"],
                        "clause":      e["clause"],
                        "signal":      e["signal"],
                        "contribution": float(e["contribution"]),
                    }
                    for e in evidence
                ],
            }
            if s["status"] in ("recommended", "viable"):
                proposed.append(entry)
            elif s["status"] == "experimental":
                rejected_close.append(entry)

        rejected_close = rejected_close[:3]

        overrides = conn.execute(
            "SELECT strategy_template_id, card_oracle_id, kind, value, note"
            " FROM commander_strategy_overrides WHERE commander_oracle_id = ?",
            (oid,),
        ).fetchall()

        report["commanders"].append({
            "oracle_id":       oid,
            "name":            cmd["name"],
            "color_identity":  json.loads(cmd["color_identity"] or "[]"),
            "proposed":        proposed,
            "closest_rejected": rejected_close,
            "overrides":       [dict(o) for o in overrides],
        })

    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=Path("strategy_review.json"))
    args = ap.parse_args()

    conn = connect(args.db)
    report = build_report(conn)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"[review] wrote {args.out} ({len(report['commanders'])} commanders)")


if __name__ == "__main__":
    main()
