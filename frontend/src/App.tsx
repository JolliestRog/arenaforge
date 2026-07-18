import { useState } from 'react';
import type { AnalysisResult, BuildRequest, DeckVariant, OwnedCard } from './lib/types';
import { buildDeck } from './lib/api';
import ImportStep from './components/ImportStep';
import AnalyzeStep from './components/AnalyzeStep';
import BuildStep from './components/BuildStep';
import VariantCompare from './components/VariantCompare';
import DeckView from './components/DeckView';
import PlayGuideStep from './components/PlayGuideStep';
import './App.css';

type Step = 'import' | 'analyze' | 'build' | 'compare' | 'deck' | 'guide';

const STEPS: { key: Step; label: string }[] = [
  { key: 'import',  label: 'Import' },
  { key: 'analyze', label: 'Collection Profile' },
  { key: 'build',   label: 'Commander & Budget' },
  { key: 'compare', label: 'Compare Builds' },
  { key: 'deck',    label: 'Deck & Export' },
  { key: 'guide',   label: 'Play Guide' },
];

function StepBar({ current }: { current: Step }) {
  const currentIdx = STEPS.findIndex(s => s.key === current);
  return (
    <nav className="step-bar" aria-label="Progress">
      {STEPS.map((s, i) => {
        const state = i < currentIdx ? 'done' : i === currentIdx ? 'active' : 'upcoming';
        return (
          <div key={s.key} className={`step-pip step-pip--${state}`}>
            <div className="step-pip-dot">
              {state === 'done' ? '✓' : i + 1}
            </div>
            <span className="step-pip-label">{s.label}</span>
            {i < STEPS.length - 1 && <div className="step-pip-line" />}
          </div>
        );
      })}
    </nav>
  );
}

function App() {
  const [step, setStep] = useState<Step>('import');
  const [request, setRequest] = useState<BuildRequest | null>(null);
  const [variants, setVariants] = useState<DeckVariant[]>([]);
  const [selectedVariant, setSelectedVariant] = useState<DeckVariant | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
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
    setStep('analyze');
  }

  function handleSkip() {
    setRequest({
      collection: [],
      commander: 'A-Satoru Umezawa',
      profile: 'satoru_toolbox',
      wildcardBudget: { common: Infinity, uncommon: Infinity, rare: Infinity, mythic: Infinity },
    });
    setStep('build');
  }

  function handleSelectCommander(name: string, profile: string) {
    setRequest(r => r ? { ...r, commander: name, profile } : {
      collection: [],
      commander: name,
      profile,
      wildcardBudget: { common: Infinity, uncommon: Infinity, rare: Infinity, mythic: Infinity },
    });
    setStep('build');
  }

  async function handleBuildRequest(req: BuildRequest) {
    setError(null);
    setLoading(true);
    try {
      const result = await buildDeck(req.collection, req.commander, req.profile, req.wildcardBudget);
      const feasible = result.filter(v => !v.infeasible);
      if (feasible.length === 0) {
        setError(
          `No valid deck found for ${req.commander} within your wildcard budget. ` +
          `Try increasing your budget or choosing a different commander or strategy.`
        );
        setStep('build');
      } else {
        setRequest(req);
        setVariants(feasible);
        setStep('compare');
      }
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
    setAnalysisResult(null);
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

      <header className="app-header">
        <span className="header-wordmark">DeckForge</span>
        {step !== 'import' && (
          <button className="btn-ghost header-reset" onClick={reset}>Start Over</button>
        )}
      </header>

      <main className="app-main">
        {error && (
          <div className="error-box">
            <strong>Error:</strong> {error}
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {step === 'import' && <ImportStep onNext={handleImport} onSkip={handleSkip} />}

        {step === 'analyze' && request && (
          <AnalyzeStep
            collection={request.collection}
            cachedResult={analysisResult}
            onResult={setAnalysisResult}
            onSelectCommander={handleSelectCommander}
            onBack={() => setStep('import')}
          />
        )}

        {step === 'build' && request && (
          <BuildStep
            initialRequest={request}
            onGenerate={handleBuildRequest}
            onBack={() => setStep(request.collection.length > 0 ? 'analyze' : 'import')}
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
            onViewGuide={() => setStep('guide')}
          />
        )}

        {step === 'guide' && selectedVariant && (
          <PlayGuideStep
            variant={selectedVariant}
            onBack={() => setStep('deck')}
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

      <StepBar current={step} />
    </div>
  );
}

export default App;
