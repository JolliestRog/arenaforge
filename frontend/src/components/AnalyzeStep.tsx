import { useEffect, useState } from 'react';
import type {
  AnalysisResultV2,
  CommanderRecommendationV2,
  OwnedCard,
  RoleCoverageItem,
} from '../lib/types';
import { analyzeCollectionV2 } from '../lib/api';

interface Props {
  collection: OwnedCard[];
  cacheRef: React.RefObject<Map<string, AnalysisResultV2>>;
  onResult: (r: AnalysisResultV2) => void;
  onSelectCommander: (name: string, profile: string) => void;
  onBack: () => void;
}

// ── Color pips ────────────────────────────────────────────────────────────────

const COLOR_SYMBOL: Record<string, string> = { W: 'W', U: 'U', B: 'B', R: 'R', G: 'G' };
const COLOR_NAMES:  Record<string, string> = {
  W: 'White', U: 'Blue', B: 'Black', R: 'Red', G: 'Green',
};

function ColorPips({ colors }: { colors: string[] }) {
  return (
    <span className="color-pips">
      {colors.map(c => (
        <span key={c} className={`color-pip pip-${c}`}>{COLOR_SYMBOL[c]}</span>
      ))}
    </span>
  );
}

// ── Color strength bars ───────────────────────────────────────────────────────

function ColorStrengthSection({ strengths }: { strengths: AnalysisResultV2['color_strength'] }) {
  const maxOwned = Math.max(...strengths.map(s => s.owned), 1);
  return (
    <div className="analysis-section">
      <h3 className="analysis-section-title">Color Strength</h3>
      <div className="color-bars">
        {strengths.map(s => (
          <div key={s.color} className="color-bar-row">
            <div className={`color-bar-label pip-${s.color}-text`}>{s.label}</div>
            <div className="color-bar-track">
              <div
                className={`color-bar-fill color-bar-fill--${s.color}`}
                style={{ width: `${(s.owned / maxOwned) * 100}%` }}
              />
            </div>
            <div className="color-bar-stats">
              <span className="cbs-owned">{s.owned}</span>
              {s.rares   > 0 && <span className="cbs-rare">{s.rares}R</span>}
              {s.mythics > 0 && <span className="cbs-mythic">{s.mythics}M</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Type distribution ─────────────────────────────────────────────────────────

const TYPE_ORDER = ['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Planeswalker', 'Land', 'Other'];

function TypeDistSection({ dist }: { dist: Record<string, number> }) {
  const total   = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
  const ordered = TYPE_ORDER.filter(t => dist[t]);
  return (
    <div className="analysis-section">
      <h3 className="analysis-section-title">Card Types</h3>
      <div className="type-dist">
        {ordered.map(t => (
          <div key={t} className="type-dist-row">
            <span className="type-dist-label">{t}</span>
            <div className="type-dist-track">
              <div className="type-dist-fill" style={{ width: `${(dist[t] / total) * 100}%` }} />
            </div>
            <span className="type-dist-count">{dist[t]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Strategic assets ──────────────────────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  draw:            'Card Draw',
  interaction:     'Interaction',
  counterspell:    'Counterspells',
  creature_removal:'Removal',
  sweeper:         'Sweepers',
  ramp:            'Ramp',
  tutor:           'Tutors',
  protection:      'Protection',
  evasive_enabler: 'Evasion',
  engine:          'Engines',
  finisher:        'Finishers',
  graveyard_hate:  'GY Hate',
  artifact_answer: 'Artifact Answers',
};

function StrategicAssetsSection({ roleCounts }: { roleCounts: Record<string, number> }) {
  const relevant = Object.entries(roleCounts)
    .filter(([role]) => ROLE_LABELS[role])
    .sort((a, b) => b[1] - a[1]);
  return (
    <div className="analysis-section">
      <h3 className="analysis-section-title">Strategic Assets</h3>
      <div className="asset-chips">
        {relevant.map(([role, count]) => (
          <div
            key={role}
            className={`asset-chip ${count >= 15 ? 'asset-chip--strong' : count >= 8 ? 'asset-chip--mid' : 'asset-chip--weak'}`}
          >
            <span className="asset-chip-label">{ROLE_LABELS[role]}</span>
            <span className="asset-chip-count">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Strategy filter ───────────────────────────────────────────────────────────

const STRATEGY_FILTERS = ['All', 'Control', 'Tempo', 'Aggro', 'Midrange', 'Ramp'];

// ── Wildcard badge row ────────────────────────────────────────────────────────

function WildcardRow({ wc }: { wc: CommanderRecommendationV2['wildcard_cost_by_rarity'] }) {
  const total = wc.common + wc.uncommon + wc.rare + wc.mythic;
  if (total === 0) {
    return <div className="wc-row"><span className="wc-zero">No wildcards needed</span></div>;
  }
  return (
    <div className="wc-row">
      {wc.mythic   > 0 && <span className="wc-badge wc-mythic">{wc.mythic}M</span>}
      {wc.rare     > 0 && <span className="wc-badge wc-rare">{wc.rare}R</span>}
      {wc.uncommon > 0 && <span className="wc-badge wc-uncommon">{wc.uncommon}U</span>}
      {wc.common   > 0 && <span className="wc-badge wc-common">{wc.common}C</span>}
    </div>
  );
}

// ── Role coverage ─────────────────────────────────────────────────────────────

function RoleCoverageSection({ items }: { items: RoleCoverageItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="role-coverage">
      {items.map(item => (
        <div
          key={item.role}
          className={`role-item ${item.meets_preferred ? 'role-item--met' : item.meets_minimum ? 'role-item--partial' : 'role-item--unmet'}`}
        >
          <span className="role-item-name">{item.role.replace(/_/g, ' ')}</span>
          <span className="role-item-count">{item.deck_count}/{item.target}</span>
        </div>
      ))}
    </div>
  );
}

// ── Readiness gauges ──────────────────────────────────────────────────────────

function ReadinessGauge({ label, value }: { label: string; value: number }) {
  const cls = value >= 70 ? 'gauge--high' : value >= 40 ? 'gauge--mid' : 'gauge--low';
  return (
    <div className={`readiness-gauge ${cls}`}>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${value}%` }} />
      </div>
      <div className="gauge-label-row">
        <span className="gauge-label">{label}</span>
        <span className="gauge-val">{value.toFixed(0)}%</span>
      </div>
    </div>
  );
}

// ── Commander card ────────────────────────────────────────────────────────────

const RARITY_ORDER = ['mythic', 'rare', 'uncommon', 'common'] as const;
const RARITY_LABEL: Record<string, string> = { mythic: 'M', rare: 'R', uncommon: 'U', common: 'C' };

function KeyMissingByRarity({ missing }: { missing: { name: string; rarity: string }[] }) {
  if (missing.length === 0) return null;
  const byRarity: Record<string, string[]> = {};
  for (const k of missing) {
    (byRarity[k.rarity] ??= []).push(k.name);
  }
  return (
    <div className="cmdr-card-missing">
      <div className="cmdr-keys-label">Key cards to acquire:</div>
      {RARITY_ORDER.filter(r => byRarity[r]?.length).map(r => (
        <div key={r} className="cmdr-missing-rarity-row">
          <span className={`cmdr-rarity-badge cmdr-rarity-badge--${r}`}>{RARITY_LABEL[r]}</span>
          <div className="cmdr-missing-names">
            {byRarity[r].slice(0, 3).map(n => (
              <span key={n} className={`cmdr-key-card cmdr-key-card--missing cmdr-key-card--${r}`}>{n}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function CommanderCardV2({
  rec,
  onSelect,
}: {
  rec: CommanderRecommendationV2;
  onSelect: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const readinessClass =
    rec.deck_quality >= 70 ? 'fit-high' : rec.deck_quality >= 55 ? 'fit-mid' : 'fit-low';

  const wc = rec.completion_cost_by_rarity;
  const totalWc = wc.common + wc.uncommon + wc.rare + wc.mythic;

  return (
    <div className={`cmdr-card ${rec.commander_owned ? 'cmdr-card--owned' : ''}`}>
      {/* Header */}
      <div className="cmdr-card-header">
        <div className="cmdr-card-name-row">
          <span className="cmdr-card-name">{rec.name}</span>
          <ColorPips colors={rec.color_identity} />
        </div>
        <div className="cmdr-card-meta">
          {rec.commander_owned && <span className="badge badge--owned">Owned</span>}
          {rec.commander_wildcard_required && (
            <span className="badge badge--craft">Commander to craft</span>
          )}
          {rec.provisional && <span className="badge badge--provisional">Provisional</span>}
          <span className="cmdr-card-profile">{rec.strategy_name}</span>
        </div>
      </div>

      {/* Key missing cards — primary content, by rarity */}
      <KeyMissingByRarity missing={rec.key_missing} />

      {/* Key owned cards */}
      {rec.key_owned.length > 0 && (
        <div className="cmdr-card-keys">
          <div className="cmdr-keys-label">You already own:</div>
          <div className="cmdr-key-list">
            {rec.key_owned.slice(0, 4).map(n => (
              <span key={n} className="cmdr-key-card cmdr-key-card--owned">{n}</span>
            ))}
          </div>
        </div>
      )}

      {/* Readiness gauges */}
      <div className={`cmdr-readiness-row ${readinessClass}`}>
        <ReadinessGauge label="Deck Quality" value={rec.deck_quality} />
        <ReadinessGauge label="Already Owned" value={rec.collection_readiness} />
      </div>

      {/* Wildcard cost */}
      <div className="cmdr-wc-section">
        <WildcardRow wc={wc} />
        {totalWc === 0 && rec.commander_owned && (
          <span className="cmdr-free-badge">Build for free!</span>
        )}
        <span className="cmdr-cost-points">{rec.completion_cost_points} weighted wildcard points</span>
      </div>

      <p className="cmdr-ranking-reason">{rec.ranking_reason}</p>

      {/* Strengths / deficits inline */}
      {(rec.strengths.length > 0 || rec.deficits.length > 0) && (
        <div className="cmdr-evidence">
          {rec.strengths.slice(0, 2).map(s => (
            <div key={s} className="evidence-tag evidence-tag--strength">✓ {s}</div>
          ))}
          {rec.deficits.slice(0, 2).map(d => (
            <div key={d} className="evidence-tag evidence-tag--deficit">✗ {d}</div>
          ))}
        </div>
      )}

      {/* Role coverage (expandable) */}
      {rec.strategy_role_coverage.length > 0 && (
        <div className="cmdr-role-coverage-section">
          <button
            className="btn-ghost cmdr-expand-btn"
            onClick={() => setExpanded(e => !e)}
          >
            {expanded ? 'Hide roles ▲' : 'Show roles ▼'}
          </button>
          {expanded && <RoleCoverageSection items={rec.strategy_role_coverage} />}
        </div>
      )}

      <button className="btn-primary cmdr-select-btn" onClick={onSelect}>
        Build around this →
      </button>
    </div>
  );
}

// ── Loading / results ─────────────────────────────────────────────────────────

const CARDS_PER_SECTION = 6;

// ── Main component ────────────────────────────────────────────────────────────

export default function AnalyzeStep({
  collection, cacheRef, onResult, onSelectCommander, onBack,
}: Props) {
  const preloaded = cacheRef.current.get('All') ?? null;

  const [filterMacro, setFilterMacro] = useState('All');
  const [result, setResult]           = useState<AnalysisResultV2 | null>(preloaded);
  const [loading, setLoading]         = useState(preloaded == null);
  const [error, setError]             = useState<string | null>(null);
  const [showAllOwned, setShowAllOwned]     = useState(false);
  const [showAllUnowned, setShowAllUnowned] = useState(false);

  const fetchFilter = (filter: string) => {
    const cached = cacheRef.current.get(filter);
    if (cached) {
      setResult(cached);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    analyzeCollectionV2(collection, filter)
      .then(r => {
        cacheRef.current.set(filter, r);
        setResult(r);
        onResult(r);
      })
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  };

  // Initial load — skip if already in cache.
  useEffect(() => {
    if (preloaded != null) return;
    fetchFilter('All');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFilterChange(filter: string) {
    if (filter === filterMacro && result !== null) return;
    setFilterMacro(filter);
    setShowAllOwned(false);
    setShowAllUnowned(false);
    fetchFilter(filter);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const strongestLabels = result?.strongest_colors.map(c => COLOR_NAMES[c]).join(', ') ?? '';

  return (
    <div className="analyze-step">
      {/* Hero */}
      <div className="analyze-hero">
        <h2>What can your collection build?</h2>
        {result && (
          <>
            <p className="analyze-summary">{result.summary}</p>
            <div className="analyze-hero-stats">
              <span><strong>{result.total_unique.toLocaleString()}</strong> unique cards</span>
              <span><strong>{result.total_copies.toLocaleString()}</strong> total copies</span>
              {strongestLabels && (
                <span>Strongest in <strong>{strongestLabels}</strong></span>
              )}
            </div>
            {result.unmatched_cards.length > 0 && (
              <p className="analyze-import-warning">
                {result.unmatched_cards.length} imported card
                {result.unmatched_cards.length === 1 ? '' : 's'} could not be matched and
                were excluded from ranking.
              </p>
            )}
          </>
        )}
      </div>

      {/* Charts — only shown when we have data */}
      {result && (
        <div className="analyze-charts">
          <ColorStrengthSection strengths={result.color_strength} />
          <TypeDistSection dist={result.type_distribution} />
          <StrategicAssetsSection roleCounts={result.role_counts} />
        </div>
      )}

      {/* Recommendations */}
      <div className="analyze-recs">
        <div className="analyze-recs-header">
          <h3 className="analyze-recs-title">Commander Recommendations</h3>

          {/* Strategy filter — server-side, triggers new fetch */}
          <div className="strategy-filter">
            {STRATEGY_FILTERS.map(f => (
              <button
                key={f}
                className={`strategy-chip ${filterMacro === f ? 'strategy-chip--active' : ''}`}
                onClick={() => handleFilterChange(f)}
                disabled={loading}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="analyze-loading">
            <div className="analyze-spinner" />
            <p>
              Scoring {filterMacro === 'All' ? 'all' : filterMacro} commanders and
              building decks from your collection…
            </p>
            <p className="analyze-loading-sub">
              This may take 20–30 seconds on first load.
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="analyze-error">
            <p>Analysis failed: {error}</p>
            <button className="btn-ghost" onClick={() => fetchFilter(filterMacro)}>
              Retry
            </button>
          </div>
        )}

        {!loading && !error && result && (() => {
          const owned = result.owned_recommendations
            ?? result.recommendations.filter(r => r.commander_owned);
          const unowned = result.unowned_recommendations
            ?? result.recommendations.filter(r => !r.commander_owned);
          const recs = [...owned, ...unowned];
          const visOwned   = showAllOwned   ? owned   : owned.slice(0, CARDS_PER_SECTION);
          const visUnowned = showAllUnowned ? unowned : unowned.slice(0, CARDS_PER_SECTION);

          return (
            <>
              {owned.length > 0 && (
                <>
                  <h4 className="analyze-recs-subtitle">Best decks for commanders you own</h4>
                  <p className="analyze-recs-sub">
                    Strongest optimized decks first, with collection readiness as the tie-breaker.
                  </p>
                  <div className="cmdr-card-grid">
                    {visOwned.map(rec => (
                      <CommanderCardV2
                        key={`${rec.name}::${rec.strategy_id}`}
                        rec={rec}
                        onSelect={() => onSelectCommander(rec.name, rec.strategy_id)}
                      />
                    ))}
                  </div>
                  {owned.length > CARDS_PER_SECTION && !showAllOwned && (
                    <button
                      className="btn-ghost show-more-btn"
                      onClick={() => setShowAllOwned(true)}
                    >
                      Show {owned.length - CARDS_PER_SECTION} more owned commanders
                    </button>
                  )}
                </>
              )}

              {unowned.length > 0 && (
                <>
                  <h4 className="analyze-recs-subtitle">Closest strong decks with a commander to craft</h4>
                  <p className="analyze-recs-sub">
                    Quality-qualified decks ranked by the weighted wildcard cost to complete them.
                  </p>
                  <div className="cmdr-card-grid">
                    {visUnowned.map(rec => (
                      <CommanderCardV2
                        key={`${rec.name}::${rec.strategy_id}`}
                        rec={rec}
                        onSelect={() => onSelectCommander(rec.name, rec.strategy_id)}
                      />
                    ))}
                  </div>
                  {unowned.length > CARDS_PER_SECTION && !showAllUnowned && (
                    <button
                      className="btn-ghost show-more-btn"
                      onClick={() => setShowAllUnowned(true)}
                    >
                      Show {unowned.length - CARDS_PER_SECTION} more commanders to build toward
                    </button>
                  )}
                </>
              )}

              {recs.length === 0 && (
                <p className="analyze-recs-sub">
                  No recommendations found for {filterMacro === 'All' ? 'any strategy' : filterMacro}.
                  Try a different filter.
                </p>
              )}
            </>
          );
        })()}
      </div>

      <div className="analyze-footer-actions">
        <button className="btn-ghost" onClick={onBack}>← Back to import</button>
      </div>
    </div>
  );
}
