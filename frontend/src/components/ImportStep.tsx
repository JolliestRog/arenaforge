import { useEffect, useState } from 'react';
import type { OwnedCard } from '../lib/types';
import { parseCollection } from '../lib/parser';

interface Props {
  onNext: (collection: OwnedCard[]) => void;
}

type ImportMode = 'landing' | 'paste' | 'done';

const STORAGE_KEY = 'deckforge_collection';

function loadSaved(): { raw: string; cards: OwnedCard[] } | null {
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    return s ? JSON.parse(s) : null;
  } catch { return null; }
}

function saveSaved(raw: string, cards: OwnedCard[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ raw, cards })); } catch { /* ignore */ }
}

function clearSaved() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}

// ── Sub-views ─────────────────────────────────────────────────────────────────

function LandingView({ onHaveExport, onSkip }: { onHaveExport: () => void; onSkip: () => void }) {
  return (
    <div className="import-landing">
      <h2>Import your MTG Arena collection</h2>
      <p className="import-subtext">
        See what your collection can already build. DeckForge analyzes your cards,
        recommends commanders, and creates Arena Brawl decks around the wildcards
        you are willing to spend.
      </p>

      <div className="onboarding-steps">
        <div className="onboard-step">
          <div className="onboard-num">1</div>
          <div className="onboard-body">
            <strong>Download the Arena Exporter</strong>
            <span>A small Windows app that reads your local Arena installation.</span>
          </div>
        </div>
        <div className="onboard-arrow">→</div>
        <div className="onboard-step">
          <div className="onboard-num">2</div>
          <div className="onboard-body">
            <strong>Run it to export your collection</strong>
            <span>Produces a file with every card and copy you own.</span>
          </div>
        </div>
        <div className="onboard-arrow">→</div>
        <div className="onboard-step">
          <div className="onboard-num">3</div>
          <div className="onboard-body">
            <strong>Import the file here</strong>
            <span>DeckForge reads your ownership and optimizes around it.</span>
          </div>
        </div>
      </div>

      <div className="landing-ctas">
        <a className="btn-primary btn-download-hero" href="/downloads/ArenaForge-MTGA-Exporter.exe" download>
          Download Arena Exporter
          <span className="btn-sub">Windows · ~14 MB</span>
        </a>
        <button className="btn-ghost btn-have-export" onClick={onHaveExport}>
          I already have an export →
        </button>
      </div>

      <button className="btn-skip-link" onClick={onSkip}>
        Skip — browse without a collection
      </button>
    </div>
  );
}

function PasteView({
  raw,
  setRaw,
  errors,
  onParse,
  onBack,
}: {
  raw: string;
  setRaw: (v: string) => void;
  errors: string[];
  onParse: () => void;
  onBack: () => void;
}) {
  return (
    <div className="import-paste">
      <button className="btn-back-link" onClick={onBack}>← Back</button>
      <h2>Import your collection</h2>

      <div className="import-formats">
        <div className="format-pill active">Paste Arena export</div>
        <div className="format-pill">Plain card list</div>
        <div className="format-pill">CSV (name, count)</div>
      </div>

      <p className="import-subtext">
        In MTG Arena, go to <strong>Decks → Export Collection</strong> (or use the
        Arena Exporter), then paste the result below.
      </p>

      <textarea
        className="collection-input"
        placeholder={`Paste your collection here, e.g.\n\n1 Counterspell (TSR) 73\n2 Brainstorm\n\nOr leave blank to use a sample collection.`}
        rows={12}
        value={raw}
        onChange={e => setRaw(e.target.value)}
      />

      {errors.length > 0 && (
        <div className="parse-errors">
          <strong>Parse warnings:</strong>
          <ul>{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
        </div>
      )}

      <div className="import-actions">
        <button className="btn-primary" onClick={onParse}>Parse Collection</button>
      </div>
    </div>
  );
}

function DoneView({
  parsed,
  onContinue,
  onReimport,
}: {
  parsed: OwnedCard[];
  onContinue: () => void;
  onReimport: () => void;
}) {
  const totalCopies = parsed.reduce((s, c) => s + c.count, 0);
  const now = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <div className="import-done">
      <h2>Collection imported</h2>

      <div className="collection-summary">
        <div className="summary-stat">
          <span className="summary-num">{parsed.length.toLocaleString()}</span>
          <span className="summary-label">Unique cards</span>
        </div>
        <div className="summary-stat">
          <span className="summary-num">{totalCopies.toLocaleString()}</span>
          <span className="summary-label">Total copies</span>
        </div>
        <div className="summary-stat">
          <span className="summary-num">{now}</span>
          <span className="summary-label">Imported</span>
        </div>
        <div className="summary-stat">
          <span className="summary-num saved-tag-inline">Saved locally</span>
          <span className="summary-label">Storage</span>
        </div>
      </div>

      <div className="done-ctas">
        <button className="btn-primary btn-analyze" onClick={onContinue}>
          Analyze my collection
        </button>
        <button className="btn-ghost" onClick={onReimport}>
          Re-import collection
        </button>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function ImportStep({ onNext }: Props) {
  const [mode, setMode] = useState<ImportMode>('landing');
  const [raw, setRaw] = useState('');
  const [errors, setErrors] = useState<string[]>([]);
  const [parsed, setParsed] = useState<OwnedCard[] | null>(null);

  useEffect(() => {
    const saved = loadSaved();
    if (saved) {
      setRaw(saved.raw);
      setParsed(saved.cards);
      setMode('done');
    }
  }, []);

  function handleParse() {
    const result = parseCollection(raw.trim() || '');
    setErrors(result.errors);
    if (result.cards.length > 0) {
      setParsed(result.cards);
      saveSaved(raw, result.cards);
      setMode('done');
    }
  }

  function handleReimport() {
    clearSaved();
    setRaw('');
    setParsed(null);
    setErrors([]);
    setMode('paste');
  }

  function handleRawChange(v: string) {
    setRaw(v);
    setErrors([]);
  }

  if (mode === 'landing') {
    return (
      <LandingView
        onHaveExport={() => setMode('paste')}
        onSkip={() => onNext([])}
      />
    );
  }

  if (mode === 'paste') {
    return (
      <PasteView
        raw={raw}
        setRaw={handleRawChange}
        errors={errors}
        onParse={handleParse}
        onBack={() => setMode('landing')}
      />
    );
  }

  return (
    <DoneView
      parsed={parsed!}
      onContinue={() => onNext(parsed!)}
      onReimport={handleReimport}
    />
  );
}
