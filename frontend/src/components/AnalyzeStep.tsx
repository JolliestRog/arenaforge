import { useEffect, useRef, useState } from 'react';
import type {
  AnalysisQueueStatus,
  AnalysisResultV2,
  CommanderRecommendationV2,
  CraftLeverage,
  OwnedCard,
  RoleCoverageItem,
} from '../lib/types';
import { analyzeCollectionV2, fetchAnalysisQueue } from '../lib/api';

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
const COLOR_ORDER = 'WUBRG';
const GUILD_GREETINGS: Record<string, string> = {
  UB: "Ah, a Dimir summoner. Here's what shadows and secrets can build.",
  WU: 'An Azorius architect steps forward. Order will prevail.',
  BR: 'A Rakdos devotee arrives. Let chaos reign.',
  RG: 'A Gruul warrior claims the forge. Strength above all.',
  WG: 'A Selesnya cultivator. Your collection grows strong.',
  WB: 'An Orzhov magnate surveys their assets.',
  UR: 'An Izzet theorist approaches the board.',
  BG: 'A Golgari harvester. Life from death.',
  WR: 'A Boros commander reports for battle.',
  UG: 'A Simic researcher scans the possibilities.',
};

function getThematicGreeting(result: AnalysisResultV2 | null): string {
  if (!result) return 'What can your collection build?';
  const strengthByColor = new Map(
    result.color_strength.map(strength => [
      strength.color,
      strength.owned + strength.rares * 2 + strength.mythics * 3,
    ]),
  );
  const strongestPositive = result.strongest_colors.filter(
    color => (strengthByColor.get(color) ?? 0) > 0,
  );
  if (strongestPositive.length < 2) {
    return "Welcome, summoner. Here's what your collection can build.";
  }
  const pair = strongestPositive.slice(0, 2)
    .sort((a, b) => COLOR_ORDER.indexOf(a) - COLOR_ORDER.indexOf(b))
    .join('');
  return GUILD_GREETINGS[pair]
    ?? "Welcome, summoner. Here's what your collection can build.";
}

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
      <p className="color-bar-legend">R = rares · M = mythics</p>
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
  const unmet = items.filter(item => !item.meets_minimum);
  const partial = items.filter(item => item.meets_minimum && !item.meets_preferred);
  const met = items.filter(item => item.meets_preferred);
  const ordered = [...unmet, ...partial, ...met];
  return (
    <div className="role-coverage">
      <p className="role-coverage-summary">
        {unmet.length} unmet · {partial.length} partially met
      </p>
      {ordered.map(item => (
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

function CraftLeverageRows({
  cardsByRarity,
  total,
}: {
  cardsByRarity: CraftLeverage['cards_by_rarity'];
  total: number;
}) {
  return RARITY_ORDER.filter(rarity => cardsByRarity[rarity]?.length).map(rarity => (
    <div key={rarity} className="craft-oracle-rarity-row">
      <span className={`cmdr-rarity-badge cmdr-rarity-badge--${rarity}`}>
        {RARITY_LABEL[rarity]}
      </span>
      <div className="craft-oracle-cards">
        {cardsByRarity[rarity]!.map(card => (
          <div key={card.name} className="craft-oracle-item">
            <span className={`cmdr-key-card cmdr-key-card--${rarity}`}>{card.name}</span>
            <span className="craft-oracle-decks">
              {card.deck_count} of {total} deck{total === 1 ? '' : 's'}
            </span>
          </div>
        ))}
      </div>
    </div>
  ));
}

function CraftOracleCard({
  leverage,
  strategyFilter,
}: {
  leverage: CraftLeverage;
  strategyFilter: string;
}) {
  const total = leverage.total_decks_analyzed;
  const scope = strategyFilter === 'All' ? 'recommended decks' : `${strategyFilter} decks`;
  const landsByRarity = leverage.lands_by_rarity ?? {};
  const hasLands = RARITY_ORDER.some(rarity => landsByRarity[rarity]?.length);
  const hasSpells = RARITY_ORDER.some(rarity => leverage.cards_by_rarity[rarity]?.length);
  return (
    <div className="cmdr-card craft-oracle-card">
      <div className="craft-oracle-header">
        <span className="craft-oracle-title">Craft Leverage</span>
        <span className="craft-oracle-subtitle">
          Missing cards that strengthen the most {scope}
        </span>
      </div>
      <div className="craft-oracle-body">
        {hasLands && (
          <section className="craft-oracle-section craft-oracle-section--lands">
            <div className="craft-oracle-section-title">
              Lands <span>Reusable mana-base upgrades</span>
            </div>
            <CraftLeverageRows cardsByRarity={landsByRarity} total={total} />
          </section>
        )}
        {hasSpells && (
          <section className="craft-oracle-section">
            <div className="craft-oracle-section-title">Spells</div>
            <CraftLeverageRows cardsByRarity={leverage.cards_by_rarity} total={total} />
          </section>
        )}
      </div>
      <p className="craft-oracle-footer">
        Based on {total} eligible owned-commander deck{total === 1 ? '' : 's'}
      </p>
    </div>
  );
}

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
  const [showUnmatched, setShowUnmatched]   = useState(false);
  const [queueStatus, setQueueStatus]       = useState<AnalysisQueueStatus | null>(null);
  const queueTimerRef = useRef<number | null>(null);

  function stopQueuePolling() {
    if (queueTimerRef.current !== null) {
      window.clearInterval(queueTimerRef.current);
      queueTimerRef.current = null;
    }
  }

  function startQueuePolling() {
    stopQueuePolling();
    const poll = () => {
      fetchAnalysisQueue()
        .then(status => {
          if (status) setQueueStatus(status);
        })
        .catch(() => { /* Queue feedback is optional. */ });
    };
    poll();
    queueTimerRef.current = window.setInterval(poll, 5000);
  }

  const fetchFilter = (filter: string) => {
    const cached = cacheRef.current.get(filter);
    if (cached) {
      stopQueuePolling();
      setQueueStatus(null);
      setResult(cached);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setQueueStatus(null);
    startQueuePolling();
    analyzeCollectionV2(collection, filter)
      .then(r => {
        cacheRef.current.set(filter, r);
        setResult(r);
        onResult(r);
      })
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => {
        stopQueuePolling();
        setQueueStatus(null);
        setLoading(false);
      });
  };

  // Initial load — skip if already in cache.
  useEffect(() => {
    if (preloaded != null) return;
    fetchFilter('All');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => stopQueuePolling(), []);

  function handleFilterChange(filter: string) {
    if (filter === filterMacro && result !== null) return;
    setFilterMacro(filter);
    setShowAllOwned(false);
    setShowUnmatched(false);
    fetchFilter(filter);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const strongestLabels = result?.strongest_colors
    .filter(color => {
      const strength = result.color_strength.find(item => item.color === color);
      return (strength?.owned ?? 0) > 0;
    })
    .map(c => COLOR_NAMES[c])
    .join(', ') ?? '';

  return (
    <div className="analyze-step">
      {/* Hero */}
      <div className="analyze-hero">
        <h2>{getThematicGreeting(result)}</h2>
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
              <div className="analyze-import-warning">
                <div className="unmatched-warning-row">
                  <span>
                    {result.unmatched_cards.length} imported card
                    {result.unmatched_cards.length === 1 ? '' : 's'} could not be matched and
                    were excluded from ranking.
                  </span>
                  <button
                    className="unmatched-toggle"
                    onClick={() => setShowUnmatched(show => !show)}
                    aria-expanded={showUnmatched}
                    aria-controls="unmatched-card-list"
                  >
                    {showUnmatched ? 'Hide list ▲' : 'Show list ▼'}
                  </button>
                </div>
                {showUnmatched && (
                  <ul id="unmatched-card-list" className="unmatched-card-list">
                    {result.unmatched_cards.map(name => <li key={name}>{name}</li>)}
                  </ul>
                )}
              </div>
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
          {/* Strategy filter — server-side, triggers new fetch */}
          <span className="core-strategies-label">Core Strategies</span>
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
            {queueStatus && queueStatus.waiting > 0 ? (
              <p>
                High demand — {queueStatus.active} analysis
                {queueStatus.active === 1 ? '' : 'es'} running and {queueStatus.waiting} waiting.
                Your request remains queued.
              </p>
            ) : (
              <p>
                Scoring {filterMacro === 'All' ? 'all' : filterMacro} commanders and
                building decks from your collection…
              </p>
            )}
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
          const leverage = result.craft_leverage ?? null;
          const initialOwnedCount = leverage ? CARDS_PER_SECTION - 1 : CARDS_PER_SECTION;
          const visOwned = showAllOwned ? owned : owned.slice(0, initialOwnedCount);
          const visUnowned = unowned.slice(0, CARDS_PER_SECTION);

          return (
            <>
              {owned.length > 0 && (
                <>
                  <h4 className="analyze-recs-subtitle">Best decks for commanders you own</h4>
                  <div className="cmdr-card-grid">
                    {leverage && (
                      <CraftOracleCard leverage={leverage} strategyFilter={filterMacro} />
                    )}
                    {visOwned.map(rec => (
                      <CommanderCardV2
                        key={`${rec.name}::${rec.strategy_id}`}
                        rec={rec}
                        onSelect={() => onSelectCommander(rec.name, rec.strategy_id)}
                      />
                    ))}
                  </div>
                  {owned.length > initialOwnedCount && !showAllOwned && (
                    <button
                      className="btn-ghost show-more-btn"
                      onClick={() => setShowAllOwned(true)}
                    >
                      Show {owned.length - initialOwnedCount} more owned commanders
                    </button>
                  )}
                </>
              )}

              {unowned.length > 0 && (
                <>
                  <h4 className="analyze-recs-subtitle">Closest strong decks with a commander to craft</h4>
                  <div className="cmdr-card-grid">
                    {visUnowned.map(rec => (
                      <CommanderCardV2
                        key={`${rec.name}::${rec.strategy_id}`}
                        rec={rec}
                        onSelect={() => onSelectCommander(rec.name, rec.strategy_id)}
                      />
                    ))}
                  </div>
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
