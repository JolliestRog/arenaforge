import type {
  BuildRequest, CardData, DeckCard, DeckVariant, ExcludedCard,
  OwnedCard, WildcardBudget,
} from './types';
import type { CommanderProfile } from './profiles';
import { DIMIR_POOL } from '../data/dimir-pool';
import { PROFILES } from './profiles';

const DECK_SIZE = 100;

function buildOwnedMap(collection: OwnedCard[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const c of collection) m.set(c.name.toLowerCase(), c.count);
  return m;
}

function wildcardCostFor(card: CardData): 'common' | 'uncommon' | 'rare' | 'mythic' | null {
  if (card.isLand && card.rarity === 'common') return null; // basic lands free
  return card.rarity;
}

function wildcardCostValue(rarity: 'common' | 'uncommon' | 'rare' | 'mythic'): number {
  return { common: 1, uncommon: 2, rare: 8, mythic: 16 }[rarity];
}

function isColorLegal(card: CardData, commanderIdentity: string[]): boolean {
  if (card.colorIdentity.length === 0) return true;
  return card.colorIdentity.every(c => commanderIdentity.includes(c));
}

function scoreCard(
  card: CardData,
  profile: CommanderProfile,
  owned: boolean,
  variant: 'performance' | 'wildcard' | 'consistency',
): number {
  let score = 0;

  // Role-based score
  for (const role of card.roles) {
    const weight = profile.roleWeights[role] ?? 0;
    score += weight * 10;
  }

  // Synergy bonus
  if (card.synergyTags.includes(profile.synergyTag)) {
    score += 25;
  }

  // Owned bonus varies by variant
  if (owned) {
    score += variant === 'wildcard' ? 80 : 20;
  } else {
    // Wildcard cost penalty
    const wc = wildcardCostFor(card);
    if (wc) score -= wildcardCostValue(wc) * (variant === 'wildcard' ? 3 : 1);
  }

  // High-MV bonus for yuriko variant
  if (profile.synergyTag === 'yuriko' && card.mv >= 7) {
    score += 20;
  }

  // Consistency variant: penalize high MV non-land, non-payoff cards
  if (variant === 'consistency' && !card.isLand) {
    if (card.mv >= 6 && !card.roles.includes('high_mana_reveal') && !card.roles.includes('etb_payoff')) {
      score -= card.mv * 5;
    }
    // Bonus for low MV
    if (card.mv <= 2) score += 10;
  }

  return score;
}

function manaCurve(cards: DeckCard[]): Record<number, number> {
  const curve: Record<number, number> = {};
  for (const dc of cards) {
    if (dc.card.isLand) continue;
    const mv = Math.min(dc.card.mv, 7);
    curve[mv] = (curve[mv] ?? 0) + 1;
  }
  return curve;
}

function roleCounts(cards: DeckCard[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const dc of cards) {
    for (const role of dc.card.roles) {
      counts[role] = (counts[role] ?? 0) + 1;
    }
  }
  return counts;
}

function wildcardCosts(cards: DeckCard[]): WildcardBudget {
  const budget: WildcardBudget = { common: 0, uncommon: 0, rare: 0, mythic: 0 };
  for (const dc of cards) {
    if (!dc.owned && dc.wildcardCost) budget[dc.wildcardCost]++;
  }
  return budget;
}

function estimateFunctionalHand(cards: DeckCard[], profileId: string): number {
  const landCount = cards.filter(c => c.card.isLand).length;
  const p2to4lands = hypergeom(7, DECK_SIZE, landCount, 2, 4);

  if (profileId === 'satoru_toolbox' || profileId === 'yuffie_ninjutsu') {
    const enablerCount = cards.filter(c => c.card.roles.includes('evasive_enabler')).length;
    const pEnabler = 1 - hypergeomBelow(7, DECK_SIZE, enablerCount, 1);
    return +(p2to4lands * pEnabler * 0.85).toFixed(3);
  }

  if (profileId === 'yuriko_tempo') {
    const enablerCount = cards.filter(c => c.card.roles.includes('evasive_enabler')).length;
    const pEnabler = 1 - hypergeomBelow(7, DECK_SIZE, enablerCount, 1);
    return +(p2to4lands * pEnabler * 0.88).toFixed(3);
  }

  // talion_control: just want mana and interaction
  const interactionCount = cards.filter(c =>
    c.card.roles.includes('counterspell') ||
    c.card.roles.includes('creature_removal') ||
    c.card.roles.includes('draw')
  ).length;
  const pInteraction = 1 - hypergeomBelow(7, DECK_SIZE, interactionCount, 1);
  return +(p2to4lands * pInteraction * 0.9).toFixed(3);
}

// Hypergeometric probability P(X in [lo, hi]) for drawing `k` successes
// from population N with K successes in sample n.
function hypergeom(n: number, N: number, K: number, lo: number, hi: number): number {
  let p = 0;
  for (let k = lo; k <= hi; k++) p += hypergeomPMF(n, N, K, k);
  return Math.min(1, Math.max(0, p));
}

// P(X < lo) i.e. fewer than lo successes
function hypergeomBelow(n: number, N: number, K: number, lo: number): number {
  let p = 0;
  for (let k = 0; k < lo; k++) p += hypergeomPMF(n, N, K, k);
  return Math.min(1, Math.max(0, p));
}

function hypergeomPMF(n: number, N: number, K: number, k: number): number {
  if (k > Math.min(n, K) || k < Math.max(0, n - (N - K))) return 0;
  return Math.exp(
    logComb(K, k) + logComb(N - K, n - k) - logComb(N, n)
  );
}

const logFactCache: number[] = [0];
function logFact(n: number): number {
  if (n < 0) return -Infinity;
  while (logFactCache.length <= n) {
    logFactCache.push(logFactCache[logFactCache.length - 1] + Math.log(logFactCache.length));
  }
  return logFactCache[n];
}

function logComb(n: number, k: number): number {
  if (k < 0 || k > n) return -Infinity;
  return logFact(n) - logFact(k) - logFact(n - k);
}

function buildDeckVariant(
  commanderCard: CardData,
  pool: CardData[],
  ownedMap: Map<string, number>,
  profile: CommanderProfile,
  wildcardBudget: WildcardBudget,
  variant: 'performance' | 'wildcard' | 'consistency',
): { cards: DeckCard[]; excluded: ExcludedCard[] } {
  const commanderIdentity = commanderCard.colorIdentity;

  // Score all candidates
  const candidates: Array<{ card: CardData; score: number; owned: boolean }> = [];
  for (const card of pool) {
    if (card.name === commanderCard.name) continue;
    if (!isColorLegal(card, commanderIdentity)) continue;

    const owned = (ownedMap.get(card.name.toLowerCase()) ?? 0) >= 1;
    const s = scoreCard(card, profile, owned, variant);
    candidates.push({ card, score: s, owned });
  }

  // Deterministic sort: score DESC, name ASC
  candidates.sort((a, b) => b.score - a.score || a.card.name.localeCompare(b.card.name));

  const selected: DeckCard[] = [];
  const excluded: ExcludedCard[] = [];
  const remainingWc = { ...wildcardBudget };
  const targetLands = profile.landTarget;
  const slots = DECK_SIZE - 1; // commander takes one

  // Split into lands and spells
  const lands = candidates.filter(c => c.card.isLand);
  const spells = candidates.filter(c => !c.card.isLand);

  function canAfford(card: CardData, owned: boolean): { ok: boolean; reason?: string } {
    if (owned) return { ok: true };
    const wc = wildcardCostFor(card);
    if (!wc) return { ok: true };
    const budget = remainingWc[wc];
    if (budget === Infinity || budget > 0) return { ok: true };
    return { ok: false, reason: `exceeds ${wc} wildcard budget` };
  }

  function addCard(c: { card: CardData; score: number; owned: boolean }, reason: string) {
    const wc = c.owned ? null : wildcardCostFor(c.card);
    if (wc && !c.owned) remainingWc[wc]--;
    selected.push({ card: c.card, owned: c.owned, wildcardCost: wc, reason, score: c.score });
  }

  // Fill lands first (prefer fixing, then basics)
  let landsFilled = 0;
  for (const lc of lands) {
    if (landsFilled >= targetLands) break;
    const aff = canAfford(lc.card, lc.owned);
    if (!aff.ok) {
      excluded.push({ name: lc.card.name, score: lc.score, reason: aff.reason! });
      continue;
    }
    addCard(lc, lc.card.roles.includes('fixing') ? 'color fixing' : 'mana base');
    landsFilled++;
  }

  // Fill role minimums with highest-scoring spell that fills a needed role
  const rolesFilled: Partial<Record<string, number>> = {};

  function roleFilled(role: string): number {
    return rolesFilled[role] ?? 0;
  }

  for (const [role, target] of Object.entries(profile.roleTargets) as Array<[string, { min: number; preferred: number; max?: number }]>) {
    const needed = target.min - roleFilled(role);
    if (needed <= 0) continue;

    let filled = 0;
    for (const sc of spells) {
      if (filled >= needed) break;
      if (selected.some(s => s.card.name === sc.card.name)) continue;
      if (!sc.card.roles.includes(role as never)) continue;

      const aff = canAfford(sc.card, sc.owned);
      if (!aff.ok) {
        excluded.push({ name: sc.card.name, score: sc.score, reason: aff.reason! });
        continue;
      }
      addCard(sc, `fills ${role} minimum`);
      for (const r of sc.card.roles) rolesFilled[r] = (rolesFilled[r] ?? 0) + 1;
      filled++;
    }
  }

  // Fill remaining slots with highest-scoring available spells
  for (const sc of spells) {
    if (selected.length >= slots) break;
    if (selected.some(s => s.card.name === sc.card.name)) continue;

    const aff = canAfford(sc.card, sc.owned);
    if (!aff.ok) {
      excluded.push({ name: sc.card.name, score: sc.score, reason: aff.reason! });
      continue;
    }
    addCard(sc, 'highest score');
    for (const r of sc.card.roles) rolesFilled[r] = (rolesFilled[r] ?? 0) + 1;
  }

  // Pad with basics if land count short
  const currentLandCount = selected.filter(c => c.card.isLand).length;
  const basicIsland = pool.find(c => c.name === 'Island')!;
  const basicSwamp = pool.find(c => c.name === 'Swamp')!;
  let padIslands = true;
  while (selected.filter(c => c.card.isLand).length < targetLands && selected.length < slots) {
    const basic = padIslands ? basicIsland : basicSwamp;
    padIslands = !padIslands;
    selected.push({ card: basic, owned: true, wildcardCost: null, reason: 'basic land padding', score: 0 });
  }
  void currentLandCount;

  // Collect excluded high-scorers (top 5 by score that weren't selected)
  const selectedNames = new Set(selected.map(c => c.card.name));
  const topExcluded = spells
    .filter(sc => !selectedNames.has(sc.card.name))
    .slice(0, 5)
    .map(sc => {
      const existingExcl = excluded.find(e => e.name === sc.card.name);
      return {
        name: sc.card.name,
        score: sc.score,
        reason: existingExcl?.reason ?? 'not selected in top slots',
      };
    });

  return { cards: selected, excluded: topExcluded };
}

function arenaExport(commander: CardData, cards: DeckCard[]): string {
  const lines: string[] = [];
  lines.push(`Commander`);
  lines.push(`1 ${commander.name}`);
  lines.push('');
  lines.push(`Deck`);

  // Group by name (should be singleton, but just in case)
  const counts = new Map<string, number>();
  for (const dc of cards) counts.set(dc.card.name, (counts.get(dc.card.name) ?? 0) + 1);
  for (const [name, count] of counts) lines.push(`${count} ${name}`);

  return lines.join('\n');
}

function findWeakest(cards: DeckCard[]): string[] {
  return [...cards]
    .filter(c => !c.card.isLand)
    .sort((a, b) => a.score - b.score)
    .slice(0, 5)
    .map(c => c.card.name);
}

export function generateDeck(request: BuildRequest): DeckVariant[] {
  const profile = PROFILES[request.profile];
  if (!profile) throw new Error(`Unknown profile: ${request.profile}`);

  const commanderCard = DIMIR_POOL.find(c => c.name === request.commander);
  if (!commanderCard) throw new Error(`Unknown commander: ${request.commander}`);

  const ownedMap = buildOwnedMap(request.collection);
  const infiniteBudget: WildcardBudget = { common: Infinity, uncommon: Infinity, rare: Infinity, mythic: Infinity };

  const variantDefs: Array<{ key: 'performance' | 'wildcard' | 'consistency'; label: string; description: string; budget: WildcardBudget }> = [
    {
      key: 'performance',
      label: 'Highest Performance',
      description: 'Maximum power — wildcards used freely for the strongest possible deck.',
      budget: infiniteBudget,
    },
    {
      key: 'wildcard',
      label: 'Lowest Wildcard Cost',
      description: 'Prefers cards you already own. Uses wildcards only where essential.',
      budget: request.wildcardBudget,
    },
    {
      key: 'consistency',
      label: 'Highest Consistency',
      description: 'Optimized for functional opening hands and smooth mana development.',
      budget: infiniteBudget,
    },
  ];

  return variantDefs.map(vd => {
    const { cards, excluded } = buildDeckVariant(
      commanderCard, DIMIR_POOL, ownedMap, profile, vd.budget, vd.key,
    );

    return {
      variantKey: vd.key,
      label: vd.label,
      description: vd.description,
      strategyName: '',
      commander: commanderCard,
      cards,
      roleCounts: roleCounts(cards),
      manaCurve: manaCurve(cards),
      wildcardCost: wildcardCosts(cards),
      functionalHandEstimate: estimateFunctionalHand(cards, request.profile),
      weakestCards: findWeakest(cards),
      excludedHighScorers: excluded,
      arenaExport: arenaExport(commanderCard, cards),
      score: cards.reduce((sum, c) => sum + c.score, 0),
      infeasible: false,
    };
  });
}
