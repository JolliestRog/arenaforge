import { useState } from 'react';
import type { BuildRequest, WildcardBudget } from '../lib/types';
import { PROFILES, getProfilesForCommander } from '../lib/profiles';
import { COMMANDERS } from '../data/dimir-pool';

interface Props {
  initialRequest: BuildRequest;
  onGenerate: (req: BuildRequest) => void;
  onBack: () => void;
  loading?: boolean;
}

const COMMANDER_LIST = Object.keys(COMMANDERS);

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
    onGenerate({
      collection: initialRequest.collection,
      commander,
      profile,
      wildcardBudget: budget,
    });
  }

  const selectedProfile = PROFILES[profile];

  return (
    <div className="step build-step">
      <h2>Build Options</h2>

      <div className="build-form">
        <section className="form-section">
          <h3>Commander</h3>
          <div className="commander-grid">
            {COMMANDER_LIST.map(name => (
              <button
                key={name}
                className={`commander-card ${commander === name ? 'selected' : ''}`}
                onClick={() => handleCommanderChange(name)}
              >
                <span className="commander-name">{name}</span>
                <span className="commander-colors">U/B</span>
              </button>
            ))}
          </div>
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
                .map(([role, t]) => `${role} ≥${t.min}`)
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
            <BudgetInput label="Common" value={budget.common} onChange={v => updateBudget('common', v)} />
            <BudgetInput label="Uncommon" value={budget.uncommon} onChange={v => updateBudget('uncommon', v)} />
            <BudgetInput label="Rare" value={budget.rare} onChange={v => updateBudget('rare', v)} />
            <BudgetInput label="Mythic" value={budget.mythic} onChange={v => updateBudget('mythic', v)} />
          </div>
        </section>
      </div>

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack} disabled={loading}>Back</button>
        <button className="btn-primary" onClick={handleSubmit} disabled={loading}>
          {loading ? 'Building…' : 'Generate Decks'}
        </button>
      </div>
    </div>
  );
}
