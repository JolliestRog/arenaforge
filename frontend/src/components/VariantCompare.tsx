import type { DeckVariant } from '../lib/types';

interface Props {
  variants: DeckVariant[];
  onSelect: (v: DeckVariant) => void;
  onBack: () => void;
}

function WildcardLine({ label, n }: { label: string; n: number }) {
  if (n === 0) return null;
  return <span className="wc-badge">{n} {label}</span>;
}

function RoleBar({ label, count }: { label: string; count: number }) {
  return (
    <div className="role-row">
      <span className="role-label">{label.replace(/_/g, ' ')}</span>
      <div className="role-bar-track">
        <div className="role-bar-fill" style={{ width: `${Math.min(100, count * 7)}%` }} />
      </div>
      <span className="role-count">{count}</span>
    </div>
  );
}

function CurveBars({ curve }: { curve: Record<number, number> }) {
  const max = Math.max(1, ...Object.values(curve));
  return (
    <div className="curve-bars">
      {[0, 1, 2, 3, 4, 5, 6, 7].map(mv => (
        <div key={mv} className="curve-bar-col">
          <div
            className="curve-bar"
            style={{ height: `${((curve[mv] ?? 0) / max) * 60}px` }}
            title={`${mv}${mv === 7 ? '+' : ''}: ${curve[mv] ?? 0}`}
          />
          <span className="curve-label">{mv}{mv === 7 ? '+' : ''}</span>
        </div>
      ))}
    </div>
  );
}

export default function VariantCompare({ variants, onSelect, onBack }: Props) {
  const priorityRoles = ['evasive_enabler', 'etb_payoff', 'draw', 'counterspell', 'creature_removal', 'interaction', 'ramp'];

  return (
    <div className="step compare-step">
      <h2>Compare Variants</h2>
      <p className="step-desc">
        Three builds for <strong>{variants[0]?.commander.name}</strong>. Click a variant to view the full deck.
      </p>

      <div className="variants-grid">
        {variants.map(v => (
          <div key={v.variantKey} className="variant-card">
            <div className="variant-header">
              <h3>
                {v.label}
                {v.infeasible && <span className="infeasible-badge">budget exceeded</span>}
              </h3>
              <p className="variant-desc">{v.description}</p>
            </div>

            <div className="variant-stats">
              <div className="stat-row">
                <span className="stat-label">Functional hand est.</span>
                <span className="stat-value">{(v.functionalHandEstimate * 100).toFixed(1)}%</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Cards in build</span>
                <span className="stat-value">{v.cards.length + 1}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Wildcards needed</span>
                <span className="stat-value wc-inline">
                  <WildcardLine label="C" n={v.wildcardCost.common} />
                  <WildcardLine label="U" n={v.wildcardCost.uncommon} />
                  <WildcardLine label="R" n={v.wildcardCost.rare} />
                  <WildcardLine label="M" n={v.wildcardCost.mythic} />
                  {Object.values(v.wildcardCost).every(x => x === 0) && <span className="wc-badge zero">0 wildcards</span>}
                </span>
              </div>
            </div>

            <div className="variant-curve">
              <h4>Mana Curve</h4>
              <CurveBars curve={v.manaCurve} />
            </div>

            <div className="variant-roles">
              <h4>Role Coverage</h4>
              {priorityRoles
                .filter(r => (v.roleCounts[r] ?? 0) > 0)
                .map(r => <RoleBar key={r} label={r} count={v.roleCounts[r] ?? 0} />)}
            </div>

            <button className="btn-primary variant-select" onClick={() => onSelect(v)}>
              View Full Deck
            </button>
          </div>
        ))}
      </div>

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack}>Back to Build Options</button>
      </div>
    </div>
  );
}
