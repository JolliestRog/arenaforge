import { useState } from 'react';
import type { BuildRequest, DeckVariant, OwnedCard } from './lib/types';
import { buildDeck } from './lib/api';
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
  const [loading, setLoading] = useState(false);

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

  async function handleBuildRequest(req: BuildRequest) {
    setError(null);
    setLoading(true);
    try {
      const result = await buildDeck(req.collection, req.commander, req.profile, req.wildcardBudget);
      setRequest(req);
      setVariants(result);
      setStep('compare');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
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
      <div className="side-art side-art-left" aria-hidden="true">
        <img src="/dragon-left.png" alt="" />
      </div>
      <div className="side-art side-art-right" aria-hidden="true">
        <img src="/dragon-right.png" alt="" />
      </div>

      <header className={`app-header ${step === 'import' ? 'header-hero' : 'header-compact'}`}>
        <img
          src="/banner.png"
          alt="DeckForge — Arena brawl and commander planning tool"
          className="header-banner"
        />
        {step !== 'import' && (
          <div className="header-nav">
            <button className="btn-ghost" onClick={reset}>Start Over</button>
          </div>
        )}
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
            loading={loading}
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
        <p>DeckForge is an unofficial fan tool, not affiliated with Wizards of the Coast or MTG Arena.</p>
        <p className="footer-links">
          <a href="/privacy.html">Privacy</a> ·
          <a href="/terms.html">Terms</a> ·
          <a href="/rules.html">Rules</a> ·
          <a href="/safety.html">Safety</a> ·
          <a href="/support.html">Support the project ☕</a>
        </p>
      </footer>
    </div>
  );
}

export default App;
