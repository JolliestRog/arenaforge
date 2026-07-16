import { useState } from 'react';
import type { OwnedCard } from '../lib/types';
import { parseCollection } from '../lib/parser';

interface Props {
  onNext: (collection: OwnedCard[]) => void;
}

const SAMPLE_COLLECTION = `2 Brainstorm
2 Ponder
2 Counterspell
1 Force of Negation
1 Vampiric Tutor
2 Fatal Push
2 Thoughtseize
1 Sol Ring
1 Arcane Signet
2 Watery Grave
2 Underground River
2 Slither Blade
2 Changeling Outcast
1 Faerie Seer
2 Lightning Greaves
2 Swiftfoot Boots
4 Island
4 Swamp`;

export default function ImportStep({ onNext }: Props) {
  const [raw, setRaw] = useState('');
  const [errors, setErrors] = useState<string[]>([]);
  const [parsed, setParsed] = useState<OwnedCard[] | null>(null);

  function handleParse() {
    const input = raw.trim() || SAMPLE_COLLECTION;
    const result = parseCollection(input);
    setErrors(result.errors);
    setParsed(result.cards.length > 0 ? result.cards : null);
  }

  function handleContinue() {
    if (parsed) onNext(parsed);
  }

  function handleSkip() {
    onNext([]);
  }

  return (
    <div className="step import-step">
      <h2>Import Your Collection</h2>
      <p className="step-desc">
        Paste your MTG Arena collection export, a deck list, or a CSV with name and count columns.
        DeckForge will identify which cards you own and minimize wildcard costs.
      </p>

      <div className="exporter-callout">
        <div className="exporter-callout-text">
          <strong>Need to export from Arena?</strong>
          <span>
            Download the ArenaForge Exporter — a Windows app that reads your local Arena
            installation and outputs a collection file ready to paste below.
          </span>
        </div>
        <a
          className="btn-download"
          href="/downloads/ArenaForge-MTGA-Exporter.exe"
          download
        >
          Download Exporter (.exe)
        </a>
      </div>

      <div className="import-formats">
        <div className="format-pill">Arena export</div>
        <div className="format-pill">Plain card list</div>
        <div className="format-pill">CSV (name, count)</div>
      </div>

      <textarea
        className="collection-input"
        placeholder={`Paste your collection here, e.g.\n\n1 Counterspell (TSR) 73\n2 Brainstorm\n\nOr leave blank to use a sample collection.`}
        rows={12}
        value={raw}
        onChange={e => { setRaw(e.target.value); setParsed(null); setErrors([]); }}
      />

      <div className="import-actions">
        <button className="btn-primary" onClick={handleParse}>
          Parse Collection
        </button>
        <button className="btn-ghost" onClick={handleSkip}>
          Skip (no collection)
        </button>
      </div>

      {errors.length > 0 && (
        <div className="parse-errors">
          <strong>Parse warnings:</strong>
          <ul>{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
        </div>
      )}

      {parsed && (
        <div className="parse-result">
          <div className="parse-summary">
            Parsed <strong>{parsed.length}</strong> unique cards
            ({parsed.reduce((s, c) => s + c.count, 0)} total copies).
          </div>
          <div className="parsed-preview">
            {parsed.slice(0, 8).map(c => (
              <span key={c.name} className="card-pill">
                {c.count}x {c.name}
              </span>
            ))}
            {parsed.length > 8 && <span className="card-pill muted">+{parsed.length - 8} more</span>}
          </div>
          <button className="btn-primary" onClick={handleContinue}>
            Continue to Build Options
          </button>
        </div>
      )}
    </div>
  );
}
