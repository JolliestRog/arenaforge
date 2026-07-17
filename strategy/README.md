# ArenaForge Strategy Knowledge Base

Offline, deterministic pipeline that builds a SQLite database of MTG Arena
Historic Brawl **commander strategies** and **per-card ranking weights**.
This is the knowledge layer only — the deck generator consumes this DB.

The pipeline lives at `/srv/arenaforge/strategy/` and is fully independent
from the API/backend at `/srv/arenaforge/backend/`. It **reads** the backend's
Scryfall cache (`backend/data/oracle_cards.json`) or, as a fallback, the
`backend/data/cards.db` snapshot. It writes to its own database at
`strategy/data/strategy.db`.

## Layout

```
strategy/
    schema.sql                 -- DDL for all tables
    migrate.py                 -- apply schema / reset
    run.py                     -- pipeline CLI entrypoint
    review.py                  -- emit human-review JSON report
    rules/
        signals.py             -- versioned oracle-text signal rules
        templates.py           -- strategy templates + role targets
    pipeline/
        ingest.py              -- load Scryfall / cards.db
        classify.py            -- commander tag scoring
        strategies.py          -- template matching + fit scoring
        cards.py               -- role classification + card weights
    tests/
        test_pipeline.py
```

## Rebuild

Always run from `/srv/arenaforge/` so Python can locate the `strategy` package:

```bash
cd /srv/arenaforge
python -m strategy.run --reset                # full rebuild
python -m strategy.run                        # incremental (schema-safe)
python -m strategy.migrate --reset            # drop/recreate DB only
python -m strategy.review --db strategy/data/strategy.db --out review.json
```

Options for `run.py`:
- `--db PATH` — target DB (default `strategy/data/strategy.db`)
- `--reset` — drop and recreate pipeline-managed tables (keeps overrides table)
- `--source auto|json|db` — pick the ingest source; `auto` prefers the
  Scryfall JSON dump, falls back to `cards.db`.

## Tests

```bash
cd /srv/arenaforge
python -m pytest strategy/tests -q
```

The suite builds a fresh strategy DB into a temp path once per session, then
queries it.

## Formulas

### Signal aggregation
Each rule contributes a value in [0, 1]. Multiple contributions to the same
tag combine with an inclusive-OR curve:

    weight = 1 - product(1 - c_i)

### Commander alignment
```
required_score = mean(w_required)                       (partial hits scaled by 0.4)
optional_score = mean(0.5 * w_optional)
veto           = max(w_conflicting)
alignment      = clamp01(0.75 * required + 0.35 * optional - 0.60 * veto)
```

### Arena support depth
For each role in `strategy_role_targets`, count Arena-legal, in-color cards
whose `card_role_weights.weight >= 0.4`. If at least `preferred_count`
candidates exist, that role is "met". `support = met_roles / total_roles`.
When no role weights exist yet (bootstrap), returns a neutral `0.5`.

### Fit
```
fit = 0.75 * alignment + 0.25 * support
```

### Status thresholds
| fit         | status        |
|-------------|---------------|
| ≥ 0.75      | recommended   |
| ≥ 0.60      | viable        |
| ≥ 0.45      | experimental  |
| < 0.45      | rejected      |

### Card weight (per commander/strategy)
```
card_weight = 0.45 * strategy_role_match
            + 0.35 * commander_interaction
            + 0.20 * card_quality
```

`strategy_role_match` uses the max product of card's role weight × strategy
role target weight; `commander_interaction` gives a bonus when the card's
oracle text mentions the commander's tag themes; `card_quality` is a rarity
prior with a small penalty for high-CMC noncreature spells.

## Sample queries

Strategies for a commander (by name):
```sql
SELECT t.display_name,
       s.status,
       ROUND(s.fit_score, 3) AS fit,
       s.explanation
FROM commander_strategies s
JOIN strategy_templates t ON t.id = s.strategy_template_id
JOIN cards c              ON c.oracle_id = s.commander_oracle_id
WHERE c.name = 'Lorthos, the Tidemaker'
  AND s.status IN ('recommended', 'viable')
ORDER BY s.fit_score DESC;
```

Top cards for a commander-strategy pair:
```sql
SELECT card.name,
       ROUND(csc.card_weight, 3) AS w,
       ROUND(csc.role_contribution, 3) AS role,
       ROUND(csc.interaction_score, 3) AS interact,
       ROUND(csc.quality_score, 3) AS qual
FROM commander_strategy_cards csc
JOIN cards card ON card.oracle_id = csc.card_oracle_id
JOIN cards cmd  ON cmd.oracle_id  = csc.commander_oracle_id
WHERE cmd.name = 'Lorthos, the Tidemaker'
  AND csc.strategy_template_id = 'big_mana_tap_control'
ORDER BY csc.card_weight DESC
LIMIT 30;
```

Evidence for a specific commander/strategy fit:
```sql
SELECT tag, signal, ROUND(contribution, 2) AS c, clause
FROM commander_strategy_evidence
WHERE commander_oracle_id = (
        SELECT oracle_id FROM cards WHERE name = 'Lorthos, the Tidemaker'
      )
  AND strategy_template_id = 'big_mana_tap_control';
```

Distribution of accepted strategies per commander:
```sql
SELECT n_strategies, COUNT(*) AS commanders
FROM (
    SELECT commander_oracle_id, COUNT(*) AS n_strategies
    FROM commander_strategies
    WHERE status IN ('recommended', 'viable')
    GROUP BY commander_oracle_id
)
GROUP BY n_strategies
ORDER BY n_strategies;
```

## Human review

Every generated `commander_strategies` row starts as
`review_status = 'pending_review'`. Manual edits go in
`commander_strategy_overrides`, which the pipeline reads but never writes to.

Produce a review JSON report:
```bash
python -m strategy.review --out review.json
```

The JSON is structured per commander with proposed strategies, closest
rejected strategies, evidence clauses, and overrides.

## Determinism guarantees

- Rule / template versions are recorded in `build_metadata`.
- All hashing/UUIDs derived from Scryfall `oracle_id` (or a stable MD5 of the
  card name when Scryfall data is unavailable).
- Aggregation uses commutative functions (product / max), so evidence
  ordering does not affect weights.
- Weight aggregation runs deterministically over rule ordering.
- No randomness, no external API calls at pipeline runtime.
- Rebuild with identical inputs produces identical `fit_score` values
  (verified by `test_determinism`).
