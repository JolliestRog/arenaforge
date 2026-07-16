import { useState } from 'react';
import type { BuildRequest, DeckVariant, OwnedCard } from './lib/types';
import { generateDeck } from './lib/generator';
import ImportStep from './components/ImportStep';
import BuildStep from './components/BuildStep';
import VariantCompare from './components/VariantCompare';
import DeckView from './components/DeckView';
import './App.css';

type Step = 'import' | 'build' | 'compare' | 'deck';

function App() {
  const [step, setStep] = useState<Step>('import');
  const [request, setRequest] = useState<BuildRequest | null>(null);
  const [variants, setVariants] = useState<DeckVariant[]>([]);
  const [selectedVariant, setSelectedVariant] = useState<DeckVariant | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleImport(collection: OwnedCard[]) {
    const defaultReq: BuildRequest = {
      collection,
      commander: 'A-Satoru Umezawa',
      profile: 'satoru_toolbox',
      wildcardBudget: { common: Infinity, uncommon: Infinity, rare: Infinity, mythic: Infinity },
    };
    setRequest(r => r ? { ...r, collection } : defaultReq);
    setStep('build');
  }

  function handleBuildRequest(req: BuildRequest) {
    setError(null);
    try {
      const result = generateDeck(req);
      setRequest(req);
      setVariants(result);
      setStep('compare');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function handleSelectVariant(v: DeckVariant) {
    setSelectedVariant(v);
    setStep('deck');
  }

  function reset() {
    setStep('import');
    setRequest(null);
    setVariants([]);
    setSelectedVariant(null);
    setError(null);
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <span className="logo">DeckForge</span>
          <span className="tagline">Deterministic MTG Deck Optimizer</span>
          {step !== 'import' && (
            <button className="btn-ghost" onClick={reset}>Start Over</button>
          )}
        </div>
        <div className="prototype-banner">
          Phase 1 prototype — weighted heuristic, curated Dimir card pool only.
          No collection data leaves your browser.
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="error-box">
            <strong>Error:</strong> {error}
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {step === 'import' && <ImportStep onNext={handleImport} />}

        {step === 'build' && request && (
          <BuildStep
            initialRequest={request}
            onGenerate={handleBuildRequest}
            onBack={() => setStep('import')}
          />
        )}

        {step === 'compare' && variants.length > 0 && (
          <VariantCompare
            variants={variants}
            onSelect={handleSelectVariant}
            onBack={() => setStep('build')}
          />
        )}

        {step === 'deck' && selectedVariant && (
          <DeckView
            variant={selectedVariant}
            onBack={() => setStep('compare')}
          />
        )}
      </main>

      <footer className="app-footer">
        DeckForge is not affiliated with Wizards of the Coast or MTG Arena.
        Card data is curated for prototype use only.
      </footer>
    </div>
  );
}

export default App;
