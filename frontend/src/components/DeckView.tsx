import { useState } from 'react';
import type { DeckCard, DeckVariant } from '../lib/types';

interface Props {
  variant: DeckVariant;
  onBack: () => void;
}

type Tab = 'list' | 'analysis' | 'export';

function RarityDot({ rarity }: { rarity: string }) {
  const colors: Record<string, string> = {
    common: '#aaa',
    uncommon: '#7ecfff',
    rare: '#ffd700',
    mythic: '#ff7c00',
  };
  return (
    <span
      className="rarity-dot"
      style={{ background: colors[rarity] ?? '#aaa' }}
      title={rarity}
    />
  );
}

function CardLine({ dc }: { dc: DeckCard }) {
  return (
    <div className={`card-line ${!dc.owned ? 'not-owned' : ''}`}>
      <RarityDot rarity={dc.card.rarity} />
      <span className="card-mv">{dc.card.isLand ? 'L' : dc.card.mv}</span>
      <span className="card-name">{dc.card.name}</span>
      <span className="card-roles">{dc.card.roles.slice(0, 2).join(' · ')}</span>
      {!dc.owned && dc.wildcardCost && (
        <span className="wc-needed">{dc.wildcardCost[0].toUpperCase()}</span>
      )}
    </div>
  );
}

export default function DeckView({ variant, onBack }: Props) {
  const [tab, setTab] = useState<Tab>('list');
  const [copied, setCopied] = useState(false);

  const lands = variant.cards.filter(c => c.card.isLand);
  const spells = variant.cards.filter(c => !c.card.isLand);
  const notOwned = variant.cards.filter(c => !c.owned);

  function copyExport() {
    navigator.clipboard.writeText(variant.arenaExport).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="step deck-step">
      <div className="deck-header">
        <div>
          <h2>{variant.label}</h2>
          <p className="deck-commander">Commander: <strong>{variant.commander.name}</strong></p>
        </div>
        <div className="deck-quick-stats">
          <span>{variant.cards.length + 1} cards</span>
          <span>{(variant.functionalHandEstimate * 100).toFixed(1)}% functional hand</span>
          <span>{notOwned.length} wildcards needed</span>
        </div>
      </div>

      <div className="tab-bar">
        <button className={tab === 'list' ? 'tab active' : 'tab'} onClick={() => setTab('list')}>Card List</button>
        <button className={tab === 'analysis' ? 'tab active' : 'tab'} onClick={() => setTab('analysis')}>Analysis</button>
        <button className={tab === 'export' ? 'tab active' : 'tab'} onClick={() => setTab('export')}>Arena Export</button>
      </div>

      {tab === 'list' && (
        <div className="tab-content card-list-view">
          <div className="card-section">
            <h3>Commander (1)</h3>
            <div className="card-line owned">
              <RarityDot rarity={variant.commander.rarity} />
              <span className="card-mv">{variant.commander.mv}</span>
              <span className="card-name">{variant.commander.name}</span>
              <span className="card-roles">{variant.commander.roles.slice(0, 2).join(' · ')}</span>
            </div>
          </div>

          <div className="card-section">
            <h3>Spells ({spells.length})</h3>
            {[...spells]
              .sort((a, b) => a.card.mv - b.card.mv || a.card.name.localeCompare(b.card.name))
              .map(dc => <CardLine key={dc.card.name} dc={dc} />)}
          </div>

          <div className="card-section">
            <h3>Lands ({lands.length})</h3>
            {[...lands]
              .sort((a, b) => a.card.name.localeCompare(b.card.name))
              .map(dc => <CardLine key={dc.card.name} dc={dc} />)}
          </div>

          <div className="legend">
            <RarityDot rarity="common" /> Common
            <RarityDot rarity="uncommon" /> Uncommon
            <RarityDot rarity="rare" /> Rare
            <RarityDot rarity="mythic" /> Mythic
            <span className="wc-needed">R</span> = Wildcard needed (dim = not owned)
          </div>
        </div>
      )}

      {tab === 'analysis' && (
        <div className="tab-content analysis-view">
          <section className="analysis-section">
            <h3>Opening Hand Estimate</h3>
            <div className="big-stat">
              <span className="big-num">{(variant.functionalHandEstimate * 100).toFixed(1)}%</span>
              <span className="big-label">functional opening hand probability</span>
            </div>
          </section>

          <section className="analysis-section">
            <h3>Wildcard Cost</h3>
            <div className="wc-breakdown">
              {(['common', 'uncommon', 'rare', 'mythic'] as const).map(r => (
                <div key={r} className="wc-row">
                  <RarityDot rarity={r} />
                  <span>{r}</span>
                  <span className="wc-count">{variant.wildcardCost[r]}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="analysis-section">
            <h3>Role Coverage</h3>
            <div className="role-table">
              {Object.entries(variant.roleCounts)
                .sort((a, b) => b[1] - a[1])
                .map(([role, count]) => (
                  <div key={role} className="role-table-row">
                    <span>{role.replace(/_/g, ' ')}</span>
                    <span>{count}</span>
                  </div>
                ))}
            </div>
          </section>

          <section className="analysis-section">
            <h3>Weakest Inclusions</h3>
            <p className="analysis-note">Lowest-scored non-land cards — candidates to cut first.</p>
            <ol className="weakest-list">
              {variant.weakestCards.map(name => <li key={name}>{name}</li>)}
            </ol>
          </section>

          <section className="analysis-section">
            <h3>Top Excluded Cards</h3>
            <p className="analysis-note">High-scoring cards that didn't make the cut.</p>
            <div className="excluded-list">
              {variant.excludedHighScorers.map(e => (
                <div key={e.name} className="excluded-row">
                  <span className="excl-name">{e.name}</span>
                  <span className="excl-reason">{e.reason}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="analysis-section">
            <h3>Cards Requiring Wildcards</h3>
            {notOwned.length === 0 ? (
              <p className="muted">All cards are in your collection!</p>
            ) : (
              <div className="not-owned-list">
                {notOwned.map(dc => (
                  <div key={dc.card.name} className="not-owned-row">
                    <RarityDot rarity={dc.card.rarity} />
                    <span>{dc.card.name}</span>
                    <span className="wc-needed">{dc.wildcardCost}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {tab === 'export' && (
        <div className="tab-content export-view">
          <p className="export-instructions">
            Copy this text, open MTG Arena, go to Decks, click Import, and paste.
          </p>
          <div className="export-box">
            <pre>{variant.arenaExport}</pre>
          </div>
          <button className="btn-primary" onClick={copyExport}>
            {copied ? 'Copied!' : 'Copy to Clipboard'}
          </button>
        </div>
      )}

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack}>Back to Variants</button>
      </div>
    </div>
  );
}
