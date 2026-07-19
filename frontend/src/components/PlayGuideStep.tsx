import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import type { DeckVariant } from '../lib/types';
import { generatePlayGuide } from '../lib/guide';

interface Props {
  variant: DeckVariant;
  onBack: () => void;
}

function CardPills({ cards, fallback }: { cards: string[]; fallback?: string }) {
  if (cards.length === 0) {
    return <span className="guide-empty">{fallback ?? 'None identified in this build'}</span>;
  }
  return (
    <div className="guide-card-pills">
      {cards.map(name => <span key={name} className="guide-card-pill">{name}</span>)}
    </div>
  );
}

function GuideSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="guide-section">
      <h3 className="guide-section-title">{title}</h3>
      {children}
    </section>
  );
}

export default function PlayGuideStep({ variant, onBack }: Props) {
  const guide = generatePlayGuide(variant);
  const [qrDataUrl, setQrDataUrl] = useState<string>('');

  useEffect(() => {
    QRCode.toDataURL('https://deckforge.facey.page', {
      width: 140,
      margin: 1,
      color: { dark: '#1a1a2e', light: '#ffffff' },
    }).then(setQrDataUrl);
  }, []);

  function handlePrint() {
    window.print();
  }

  return (
    <div className="step guide-step" id="guide-print-root">

      {/* ── Print-only header ── */}
      <div className="guide-print-header" aria-hidden="true">
        <img src="/dragon-left.png" alt="" className="guide-print-dragon guide-print-dragon--left" />
        <div className="guide-print-title-block">
          <div className="guide-print-wordmark">DeckForge</div>
          <div className="guide-print-subtitle">deckforge.facey.page</div>
        </div>
        <img src="/dragon-right.png" alt="" className="guide-print-dragon guide-print-dragon--right" />
      </div>

      {/* ── Screen header ── */}
      <div className="guide-header">
        <div className="guide-header-main">
          <h1 className="guide-commander">{guide.commanderName}</h1>
          <div className="guide-meta">
            <span className="guide-strategy">{guide.strategyName}</span>
          </div>
        </div>
        <p className="guide-macro">{guide.macroPlan}</p>
      </div>

      {guide.warnings.length > 0 && (
        <div className="guide-warnings">
          {guide.warnings.map((w, i) => (
            <div key={i} className="guide-warning">
              <span className="guide-warning-icon">!</span>
              {w}
            </div>
          ))}
        </div>
      )}

      <div className="guide-body">

        <GuideSection title="How This Deck Wins">
          <p className="guide-text">{guide.howItWins}</p>
        </GuideSection>

        <GuideSection title="Opening Hands">
          <div className="guide-mulligan">
            <div className="guide-mulligan-keep">
              <strong>Keep hands with:</strong>
              <ul className="guide-list">
                {guide.mulligan.keepHandsWith.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="guide-mulligan-send">
              <strong>Mulligan if:</strong>
              <p className="guide-text">{guide.mulligan.mulliganIf}</p>
            </div>
            <div className="guide-mulligan-score">
              <p className="guide-text guide-text--dim">{guide.mulligan.scoreSummary}</p>
            </div>
          </div>
        </GuideSection>

        <GuideSection title="Early Game (Turns 1–3)">
          <p className="guide-text">{guide.earlyGame}</p>
        </GuideSection>

        <GuideSection title="Mid Game (Turns 4–6)">
          <p className="guide-text">{guide.midGame}</p>
        </GuideSection>

        <GuideSection title="Closing the Game">
          <p className="guide-text">{guide.lateGame}</p>
        </GuideSection>

        <div className="guide-cards-grid">
          {guide.keyEngines.length > 0 && (
            <div className="guide-card-group">
              <h4 className="guide-card-group-title">Key Engines</h4>
              <CardPills cards={guide.keyEngines} />
            </div>
          )}
          {guide.keyFinishers.length > 0 && (
            <div className="guide-card-group">
              <h4 className="guide-card-group-title">Finishers</h4>
              <CardPills cards={guide.keyFinishers} />
            </div>
          )}
          {guide.keySetup.length > 0 && (
            <div className="guide-card-group">
              <h4 className="guide-card-group-title">Card Selection</h4>
              <CardPills cards={guide.keySetup} />
            </div>
          )}
          {guide.keyRamp.length > 0 && (
            <div className="guide-card-group">
              <h4 className="guide-card-group-title">Ramp</h4>
              <CardPills cards={guide.keyRamp} />
            </div>
          )}
        </div>

        <GuideSection title="Interaction">
          <p className="guide-text">{guide.interactionAdvice}</p>
          {guide.keyInteraction.length > 0 && (
            <>
              <h4 className="guide-subhead">Your interaction pieces:</h4>
              <CardPills cards={guide.keyInteraction} />
            </>
          )}
        </GuideSection>

        {guide.keyProtection.length > 0 && (
          <GuideSection title="Cards to Protect">
            <p className="guide-text guide-text--dim">These cards are your engine — losing them sets you back significantly. Keep them alive.</p>
            <CardPills cards={guide.keyProtection} />
          </GuideSection>
        )}

        <GuideSection title="Common Mistakes">
          <ul className="guide-list guide-list--mistakes">
            {guide.commonMistakes.map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        </GuideSection>

      </div>

      {/* ── Print footer (shown only in print) ── */}
      <div className="guide-print-footer" aria-hidden="true">
        {qrDataUrl && (
          <div className="guide-print-qr-block">
            <img src={qrDataUrl} alt="QR code for deckforge.facey.page" className="guide-print-qr" />
            <div className="guide-print-qr-label">Scan to build your next deck</div>
          </div>
        )}
        <div className="guide-print-url">deckforge.facey.page</div>
        <div className="guide-print-disclaimer">
          DeckForge is an unofficial fan tool · not affiliated with Wizards of the Coast or MTG Arena
        </div>
      </div>

      {/* ── Screen actions ── */}
      <div className="step-actions guide-screen-actions">
        <button className="btn-ghost" onClick={onBack}>Back to Deck</button>
        <a
          className="btn-ghost guide-bmc-link"
          href="https://buymeacoffee.com/facey"
          target="_blank"
          rel="noopener noreferrer"
        >
          ☕ Support DeckForge
        </a>
        <button className="btn-primary" onClick={handlePrint}>
          Print / Save as PDF
        </button>
      </div>
    </div>
  );
}
