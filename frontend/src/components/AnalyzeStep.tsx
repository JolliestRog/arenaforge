import { useEffect, useState } from 'react';
import type { AnalysisResult, CommanderRecommendation, OwnedCard } from '../lib/types';
import { analyzeCollection } from '../lib/api';

interface Props {
  collection: OwnedCard[];
  onSelectCommander: (name: string, profile: string) => void;
  onBack: () => void;
}

// ── Color pips ────────────────────────────────────────────────────────────────

const COLOR_SYMBOL: Record<string, string> = { W: 'W', U: 'U', B: 'B', R: 'R', G: 'G' };
const COLOR_NAMES: Record<string, string> = {
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

function ColorStrengthSection({ strengths }: { strengths: AnalysisResult['color_strength'] }) {
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
              {s.rares > 0 && <span className="cbs-rare">{s.rares}R</span>}
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
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
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
  draw: 'Card Draw',
  interaction: 'Interaction',
  counterspell: 'Counterspells',
  creature_removal: 'Removal',
  sweeper: 'Sweepers',
  ramp: 'Ramp',
  tutor: 'Tutors',
  protection: 'Protection',
  evasive_enabler: 'Evasion',
  engine: 'Engines',
  finisher: 'Finishers',
  graveyard_hate: 'GY Hate',
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
          <div key={role} className={`asset-chip ${count >= 15 ? 'asset-chip--strong' : count >= 8 ? 'asset-chip--mid' : 'asset-chip--weak'}`}>
            <span className="asset-chip-label">{ROLE_LABELS[role]}</span>
            <span className="asset-chip-count">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Commander card ────────────────────────────────────────────────────────────

function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{label}</span>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${(value / max) * 100}%` }} />
      </div>
      <span className="score-bar-val">{value.toFixed(0)}</span>
    </div>
  );
}

function CommanderCard({
  rec,
  onSelect,
}: {
  rec: CommanderRecommendation;
  onSelect: () => void;
}) {
  const breakdownMax = Math.max(...Object.values(rec.score_breakdown), 1);
  const fitClass = rec.collection_fit >= 80 ? 'fit-high' : rec.collection_fit >= 50 ? 'fit-mid' : 'fit-low';

  return (
    <div className={`cmdr-card ${rec.owned ? 'cmdr-card--owned' : ''}`}>
      <div className="cmdr-card-header">
        <div className="cmdr-card-name-row">
          <span className="cmdr-card-name">{rec.name}</span>
          <ColorPips colors={rec.color_identity} />
        </div>
        <div className="cmdr-card-meta">
          {rec.owned && <span className="badge badge--owned">Owned</span>}
          <span className="cmdr-card-profile">{rec.profile_name}</span>
        </div>
      </div>

      <div className="cmdr-card-score-row">
        <div className={`cmdr-fit-score ${fitClass}`}>
          <span className="cmdr-fit-num">{rec.collection_fit.toFixed(0)}</span>
          <span className="cmdr-fit-label">fit</span>
        </div>
        <div className="cmdr-fit-details">
          <div className="cmdr-pool-pct">{rec.owned_pct.toFixed(0)}% of pool owned</div>
          <div className="cmdr-pool-count">{rec.owned_pool} / {rec.total_pool} cards</div>
        </div>
      </div>

      <div className="cmdr-score-breakdown">
        {Object.entries(rec.score_breakdown).map(([key, val]) => (
          <ScoreBar
            key={key}
            label={key.replace(/_/g, ' ')}
            value={val}
            max={breakdownMax}
          />
        ))}
      </div>

      {rec.key_owned.length > 0 && (
        <div className="cmdr-card-keys">
          <div className="cmdr-keys-label">You own:</div>
          <div className="cmdr-key-list">
            {rec.key_owned.slice(0, 4).map(n => (
              <span key={n} className="cmdr-key-card cmdr-key-card--owned">{n}</span>
            ))}
          </div>
        </div>
      )}

      {rec.key_missing.length > 0 && (
        <div className="cmdr-card-keys">
          <div className="cmdr-keys-label">Key missing:</div>
          <div className="cmdr-key-list">
            {rec.key_missing.slice(0, 3).map(n => (
              <span key={n} className="cmdr-key-card cmdr-key-card--missing">{n}</span>
            ))}
          </div>
        </div>
      )}

      <button className="btn-primary cmdr-select-btn" onClick={onSelect}>
        Build around this →
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AnalyzeStep({ collection, onSelectCommander, onBack }: Props) {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    analyzeCollection(collection)
      .then(setResult)
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [collection]);

  if (loading) {
    return (
      <div className="analyze-loading">
        <div className="analyze-spinner" />
        <p>Analyzing your collection…</p>
        <p className="analyze-loading-sub">Scoring {collection.length > 0 ? collection.length.toLocaleString() + ' cards' : 'your collection'} against all commanders</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="analyze-error">
        <p>Analysis failed: {error}</p>
        <button className="btn-ghost" onClick={onBack}>Go back</button>
      </div>
    );
  }

  if (!result) return null;

  const strongestLabels = result.strongest_colors.map(c => COLOR_NAMES[c]).join(', ');

  return (
    <div className="analyze-step">
      <div className="analyze-hero">
        <h2>What can your collection build?</h2>
        <p className="analyze-summary">{result.summary}</p>
        <div className="analyze-hero-stats">
          <span><strong>{result.total_unique.toLocaleString()}</strong> unique cards</span>
          <span><strong>{result.total_copies.toLocaleString()}</strong> total copies</span>
          <span>Strongest in <strong>{strongestLabels}</strong></span>
        </div>
      </div>

      <div className="analyze-charts">
        <ColorStrengthSection strengths={result.color_strength} />
        <TypeDistSection dist={result.type_distribution} />
        <StrategicAssetsSection roleCounts={result.role_counts} />
      </div>

      <div className="analyze-recs">
        <h3 className="analyze-recs-title">Commander Recommendations</h3>
        <p className="analyze-recs-sub">
          Ranked by how well your collection already supports each commander.
          Owned commanders appear first.
        </p>
        <div className="cmdr-card-grid">
          {result.recommendations.map(rec => (
            <CommanderCard
              key={rec.name}
              rec={rec}
              onSelect={() => onSelectCommander(rec.name, rec.profile_id)}
            />
          ))}
        </div>
      </div>

      <div className="analyze-footer-actions">
        <button className="btn-ghost" onClick={onBack}>← Back to import</button>
      </div>
    </div>
  );
}
