import { useEffect, useState } from 'react';
import type { BuildRequest, WildcardBudget } from '../lib/types';
import { PROFILES, getProfilesForCommander } from '../lib/profiles';
import { fetchCommanders, type Commander } from '../lib/api';

interface Props {
  initialRequest: BuildRequest;
  onGenerate: (req: BuildRequest) => void;
  onBack: () => void;
  loading?: boolean;
}

const COLOR_OPTS = [
  { key: 'W', label: 'W', fg: '#a89060', bg: '#2a2510' },
  { key: 'U', label: 'U', fg: '#5599cc', bg: '#0f1e2a' },
  { key: 'B', label: 'B', fg: '#aa99cc', bg: '#1a1525' },
  { key: 'R', label: 'R', fg: '#cc5533', bg: '#2a100a' },
  { key: 'G', label: 'G', fg: '#44aa66', bg: '#0a1e10' },
];

function ColorPip({ colorKey, active, onClick }: { colorKey: string; active: boolean; onClick: () => void }) {
  const opt = COLOR_OPTS.find(c => c.key === colorKey)!;
  return (
    <button
      className={`color-pip ${active ? 'active' : ''}`}
      style={active ? { background: opt.bg, borderColor: opt.fg, color: opt.fg } : {}}
      onClick={onClick}
      title={colorKey}
    >
      {colorKey}
    </button>
  );
}

function CommanderPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (name: string) => void;
}) {
  const [colors, setColors] = useState<string[]>(['U', 'B']);
  const [search, setSearch] = useState('');
  const [commanders, setCommanders] = useState<Commander[]>([]);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (colors.length === 0) { setCommanders([]); return; }
    setFetching(true);
    fetchCommanders(colors)
      .then(setCommanders)
      .finally(() => setFetching(false));
  }, [colors.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleColor(c: string) {
    setColors(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c].sort());
  }

  const filtered = search.trim()
    ? commanders.filter(c => c.name.toLowerCase().includes(search.toLowerCase()))
    : commanders;

  const showing = filtered.slice(0, 150);

  return (
    <div className="commander-picker">
      <div className="color-filter">
        {COLOR_OPTS.map(({ key }) => (
          <ColorPip key={key} colorKey={key} active={colors.includes(key)} onClick={() => toggleColor(key)} />
        ))}
        <span className="color-filter-hint">
          {colors.length === 0 ? 'Select colors' : `${commanders.length} commanders`}
        </span>
      </div>

      {colors.length > 0 && (
        <input
          className="commander-search"
          placeholder="Filter by name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      )}

      <div className="commander-list-wrap">
        {fetching && <div className="picker-hint">Loading…</div>}
        {!fetching && colors.length === 0 && (
          <div className="picker-hint">Select at least one color to see commanders.</div>
        )}
        {!fetching && colors.length > 0 && filtered.length === 0 && (
          <div className="picker-hint">No commanders match "{search}".</div>
        )}
        {!fetching && showing.map(c => (
          <button
            key={c.name}
            className={`commander-item ${value === c.name ? 'selected' : ''}`}
            onClick={() => onChange(c.name)}
          >
            <span className="ci-name">{c.name}</span>
            <span className="ci-meta">{c.type_line.replace('Legendary ', '')}</span>
            <span className="ci-cmc">{c.cmc > 0 ? c.cmc : '—'}</span>
          </button>
        ))}
        {!fetching && filtered.length > 150 && (
          <div className="picker-hint">{filtered.length - 150} more — refine your search.</div>
        )}
      </div>
    </div>
  );
}

function BudgetInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const isUnlimited = value === Infinity;
  return (
    <div className="budget-row">
      <label>{label}</label>
      <div className="budget-controls">
        <input
          type="number"
          min={0}
          max={99}
          value={isUnlimited ? '' : value}
          placeholder="∞"
          disabled={isUnlimited}
          onChange={e => onChange(parseInt(e.target.value, 10) || 0)}
          className="budget-num"
        />
        <label className="budget-toggle">
          <input
            type="checkbox"
            checked={isUnlimited}
            onChange={e => onChange(e.target.checked ? Infinity : 0)}
          />
          Unlimited
        </label>
      </div>
    </div>
  );
}

export default function BuildStep({ initialRequest, onGenerate, onBack, loading = false }: Props) {
  const [commander, setCommander] = useState(initialRequest.commander);
  const [profile, setProfile] = useState(initialRequest.profile);
  const [budget, setBudget] = useState<WildcardBudget>(initialRequest.wildcardBudget);

  const availableProfiles = getProfilesForCommander(commander);

  function handleCommanderChange(name: string) {
    setCommander(name);
    const profiles = getProfilesForCommander(name);
    if (profiles.length > 0) setProfile(profiles[0].id);
  }

  function updateBudget(key: keyof WildcardBudget, value: number) {
    setBudget(b => ({ ...b, [key]: value }));
  }

  function handleSubmit() {
    onGenerate({ collection: initialRequest.collection, commander, profile, wildcardBudget: budget });
  }

  const selectedProfile = PROFILES[profile];

  return (
    <div className="step build-step">
      <h2>Build Options</h2>

      <div className="build-form">
        <section className="form-section">
          <h3>Commander</h3>
          <CommanderPicker value={commander} onChange={handleCommanderChange} />
          {commander && (
            <div className="selected-commander-label">
              Selected: <strong>{commander}</strong>
            </div>
          )}
        </section>

        <section className="form-section">
          <h3>Strategic Profile</h3>
          {availableProfiles.length === 0 ? (
            <p className="muted">No profiles available for this commander.</p>
          ) : (
            <div className="profile-list">
              {availableProfiles.map(p => (
                <button
                  key={p.id}
                  className={`profile-card ${profile === p.id ? 'selected' : ''}`}
                  onClick={() => setProfile(p.id)}
                >
                  <span className="profile-name">{p.displayName}</span>
                  <span className="profile-desc">{p.description}</span>
                </button>
              ))}
            </div>
          )}
          {selectedProfile && (
            <div className="profile-targets">
              <strong>Role targets:</strong>{' '}
              {Object.entries(selectedProfile.roleTargets)
                .map(([role, t]) => `${role.replace(/_/g, ' ')} ≥${t.min}`)
                .join(' · ')}
            </div>
          )}
        </section>

        <section className="form-section">
          <h3>Wildcard Budget</h3>
          <p className="budget-note">
            Set limits per rarity. Leave "Unlimited" to ignore cost constraints.
          </p>
          <div className="budget-grid">
            <BudgetInput label="Common"   value={budget.common}   onChange={v => updateBudget('common', v)} />
            <BudgetInput label="Uncommon" value={budget.uncommon} onChange={v => updateBudget('uncommon', v)} />
            <BudgetInput label="Rare"     value={budget.rare}     onChange={v => updateBudget('rare', v)} />
            <BudgetInput label="Mythic"   value={budget.mythic}   onChange={v => updateBudget('mythic', v)} />
          </div>
        </section>
      </div>

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack} disabled={loading}>Back</button>
        <button className="btn-primary" onClick={handleSubmit} disabled={loading || !commander}>
          {loading ? 'Building…' : 'Generate Decks'}
        </button>
      </div>
    </div>
  );
}
