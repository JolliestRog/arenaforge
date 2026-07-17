-- ArenaForge Strategy Knowledge Base schema.
-- All tables use IF NOT EXISTS so migrations are idempotent.
-- Weights are stored as REAL in [0.0, 1.0]. Evidence blobs are JSON.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Card cache (Arena-legal Historic Brawl cards, keyed by oracle_id).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cards (
    oracle_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    color_identity  TEXT NOT NULL DEFAULT '[]',   -- JSON array of color letters
    cmc             REAL NOT NULL DEFAULT 0,
    type_line       TEXT NOT NULL DEFAULT '',
    oracle_text     TEXT NOT NULL DEFAULT '',     -- combined text (all faces)
    faces           TEXT NOT NULL DEFAULT '[]',   -- JSON: list of per-face objects
    keywords        TEXT NOT NULL DEFAULT '[]',   -- JSON array of keyword strings
    power           TEXT,
    toughness       TEXT,
    rarity          TEXT NOT NULL DEFAULT 'common',
    is_land         INTEGER NOT NULL DEFAULT 0,
    is_creature     INTEGER NOT NULL DEFAULT 0,
    is_legendary    INTEGER NOT NULL DEFAULT 0,
    is_commander    INTEGER NOT NULL DEFAULT 0,
    arena_legal     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_cards_name ON cards (name);
CREATE INDEX IF NOT EXISTS idx_cards_is_commander ON cards (is_commander);
CREATE INDEX IF NOT EXISTS idx_cards_arena_legal ON cards (arena_legal);

-- ---------------------------------------------------------------------------
-- Tag registry.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_tags (
    tag         TEXT PRIMARY KEY,
    category    TEXT NOT NULL,                    -- macro | theme | wincon | signal
    description TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------------------
-- Strategy templates (macro plan + theme + win condition).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_templates (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,             -- short slug
    display_name        TEXT NOT NULL,
    macro_plan          TEXT NOT NULL,
    theme               TEXT NOT NULL,
    win_condition       TEXT NOT NULL,
    required_tags       TEXT NOT NULL DEFAULT '[]',  -- JSON array
    optional_tags       TEXT NOT NULL DEFAULT '[]',  -- JSON array
    conflicting_tags    TEXT NOT NULL DEFAULT '[]',  -- JSON array
    needed_roles        TEXT NOT NULL DEFAULT '[]',  -- JSON array of role names
    min_arena_depth     INTEGER NOT NULL DEFAULT 20,
    required_threshold  REAL NOT NULL DEFAULT 0.35,
    description         TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------------------
-- Commander tag weights: primitive signal scoring output.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commander_tag_weights (
    commander_oracle_id TEXT NOT NULL,
    tag                 TEXT NOT NULL,
    weight              REAL NOT NULL,
    evidence            TEXT NOT NULL DEFAULT '[]', -- JSON array of evidence rows
    PRIMARY KEY (commander_oracle_id, tag),
    FOREIGN KEY (commander_oracle_id) REFERENCES cards(oracle_id) ON DELETE CASCADE,
    FOREIGN KEY (tag)                 REFERENCES strategy_tags(tag)
);
CREATE INDEX IF NOT EXISTS idx_ctw_commander ON commander_tag_weights (commander_oracle_id);
CREATE INDEX IF NOT EXISTS idx_ctw_tag ON commander_tag_weights (tag);

-- ---------------------------------------------------------------------------
-- Commander <-> strategy fit scores.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commander_strategies (
    commander_oracle_id  TEXT NOT NULL,
    strategy_template_id TEXT NOT NULL,
    fit_score            REAL NOT NULL,
    status               TEXT NOT NULL,       -- recommended | viable | experimental | rejected
    confidence           REAL NOT NULL DEFAULT 0.5,
    review_status        TEXT NOT NULL DEFAULT 'pending_review',
    explanation          TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (commander_oracle_id, strategy_template_id),
    FOREIGN KEY (commander_oracle_id)  REFERENCES cards(oracle_id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_template_id) REFERENCES strategy_templates(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cs_commander ON commander_strategies (commander_oracle_id);
CREATE INDEX IF NOT EXISTS idx_cs_status ON commander_strategies (status);

-- ---------------------------------------------------------------------------
-- Evidence links (denormalized per-strategy evidence for review UIs).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commander_strategy_evidence (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    commander_oracle_id  TEXT NOT NULL,
    strategy_template_id TEXT NOT NULL,
    tag                  TEXT NOT NULL,
    clause               TEXT NOT NULL,
    signal               TEXT NOT NULL,
    contribution         REAL NOT NULL,
    FOREIGN KEY (commander_oracle_id)  REFERENCES cards(oracle_id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_template_id) REFERENCES strategy_templates(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cse_pair
    ON commander_strategy_evidence (commander_oracle_id, strategy_template_id);

-- ---------------------------------------------------------------------------
-- Universal card role weights.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS card_role_weights (
    oracle_id TEXT NOT NULL,
    role      TEXT NOT NULL,
    weight    REAL NOT NULL,
    evidence  TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (oracle_id, role),
    FOREIGN KEY (oracle_id) REFERENCES cards(oracle_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_crw_role ON card_role_weights (role);

-- ---------------------------------------------------------------------------
-- Per-strategy role targets (how many of each role a strategy wants).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_role_targets (
    strategy_template_id TEXT NOT NULL,
    role                 TEXT NOT NULL,
    min_count            INTEGER NOT NULL DEFAULT 0,
    preferred_count      INTEGER NOT NULL DEFAULT 0,
    weight               REAL NOT NULL DEFAULT 0.5,
    PRIMARY KEY (strategy_template_id, role),
    FOREIGN KEY (strategy_template_id) REFERENCES strategy_templates(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Precomputed commander/strategy/card fit weights.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commander_strategy_cards (
    commander_oracle_id  TEXT NOT NULL,
    strategy_template_id TEXT NOT NULL,
    card_oracle_id       TEXT NOT NULL,
    card_weight          REAL NOT NULL,
    role_contribution    REAL NOT NULL DEFAULT 0,
    interaction_score    REAL NOT NULL DEFAULT 0,
    quality_score        REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (commander_oracle_id, strategy_template_id, card_oracle_id),
    FOREIGN KEY (commander_oracle_id)  REFERENCES cards(oracle_id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_template_id) REFERENCES strategy_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (card_oracle_id)       REFERENCES cards(oracle_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_csc_pair
    ON commander_strategy_cards (commander_oracle_id, strategy_template_id);
CREATE INDEX IF NOT EXISTS idx_csc_weight
    ON commander_strategy_cards (card_weight DESC);

-- ---------------------------------------------------------------------------
-- Manual overrides.  The pipeline reads these but never writes them.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commander_strategy_overrides (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    commander_oracle_id  TEXT NOT NULL,
    strategy_template_id TEXT,               -- null = commander-wide override
    card_oracle_id       TEXT,               -- null = strategy-level override
    kind                 TEXT NOT NULL,      -- ban | add | adjust_score | note
    value                REAL,               -- optional numeric adjustment
    note                 TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cso_commander
    ON commander_strategy_overrides (commander_oracle_id);

-- ---------------------------------------------------------------------------
-- Build metadata.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS build_metadata (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_version     TEXT NOT NULL,
    signal_rule_version  TEXT NOT NULL,
    template_version     TEXT NOT NULL,
    scryfall_snapshot    TEXT NOT NULL,
    run_started_at       TEXT NOT NULL,
    run_finished_at      TEXT,
    card_count           INTEGER NOT NULL DEFAULT 0,
    commander_count      INTEGER NOT NULL DEFAULT 0,
    strategy_pair_count  INTEGER NOT NULL DEFAULT 0
);
