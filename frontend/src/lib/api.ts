import type {
  AnalysisResult, CardData, DeckCard, DeckVariant,
  ExcludedCard, OwnedCard, WildcardBudget,
} from './types';

const API_BASE = '/api';

// ── Request transform ──────────────────────────────────────────────────────────

function toApiWildcardBudget(b: WildcardBudget): Record<string, number> {
  const cap = (n: number) => (n === Infinity ? 9999 : n);
  return { common: cap(b.common), uncommon: cap(b.uncommon), rare: cap(b.rare), mythic: cap(b.mythic) };
}

// ── Response adapter ───────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function adaptCard(raw: any, roles: string[] = []): CardData {
  return {
    name: raw.name,
    mv: raw.cmc,
    colors: raw.color_identity,
    colorIdentity: raw.color_identity,
    rarity: raw.rarity,
    roles: roles as CardData['roles'],
    synergyTags: [],
    isLand: raw.is_land,
    isCreature: raw.is_creature,
    typeLine: raw.type_line,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function adaptDeckCard(raw: any): DeckCard {
  return {
    card: adaptCard(raw.card, raw.roles ?? []),
    owned: raw.owned,
    wildcardCost: raw.wildcard_cost,
    reason: raw.reason,
    score: raw.score,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function adaptVariant(raw: any): DeckVariant {
  const manaCurve: Record<number, number> = {};
  for (const [k, v] of Object.entries(raw.mana_curve as Record<string, number>)) {
    manaCurve[Number(k)] = v;
  }

  const excludedHighScorers: ExcludedCard[] = (raw.excluded_high_scorers ?? []).map(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (e: any) => ({ name: e.name, score: e.score, reason: e.reason })
  );

  const fc = raw.featured_cards ?? {};
  return {
    variantKey: raw.variant_key,
    label: raw.label,
    description: raw.description,
    strategyName: raw.strategy_name ?? '',
    strategyId: raw.strategy_id ?? '',
    commander: adaptCard(raw.commander),
    cards: (raw.cards ?? []).map(adaptDeckCard),
    roleCounts: raw.role_counts ?? {},
    manaCurve,
    wildcardCost: raw.wildcard_cost ?? { common: 0, uncommon: 0, rare: 0, mythic: 0 },
    functionalHandEstimate: raw.functional_hand_estimate ?? 0,
    weakestCards: raw.weakest_cards ?? [],
    excludedHighScorers,
    arenaExport: raw.arena_export ?? '',
    score: raw.score ?? 0,
    infeasible: raw.infeasible ?? false,
    featuredCards: {
      engines: fc.engines ?? [],
      finishers: fc.finishers ?? [],
      setup: fc.setup ?? [],
      interaction: fc.interaction ?? [],
      protection: fc.protection ?? [],
      ramp: fc.ramp ?? [],
    },
  };
}

// ── Public types ───────────────────────────────────────────────────────────────

export interface Commander {
  name: string;
  cmc: number;
  color_identity: string[];
  type_line: string;
  rarity: string;
}

export interface CommanderStrategy {
  id: string;
  display_name: string;
  fit_score: number;
  status: string;
  description: string;
}

// ── Public API ─────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function fetchCommanders(colors: string[]): Promise<Commander[]> {
  if (colors.length === 0) return [];
  const params = new URLSearchParams({ colors: colors.join(',') });
  const res = await fetch(`${API_BASE}/commanders?${params}`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchCommanderStrategies(commanderName: string): Promise<CommanderStrategy[]> {
  if (!commanderName) return [];
  const res = await fetch(`${API_BASE}/commanders/${encodeURIComponent(commanderName)}/strategies`);
  if (!res.ok) return [];
  return res.json();
}

export async function buildDeck(
  collection: OwnedCard[],
  commander: string,
  profile: string,
  wildcardBudget: WildcardBudget,
): Promise<DeckVariant[]> {
  const body = {
    collection,
    commander,
    profile,
    wildcard_budget: toApiWildcardBudget(wildcardBudget),
  };

  const res = await fetch(`${API_BASE}/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, err.detail ?? 'Build failed');
  }

  const data = await res.json();
  return (data as unknown[]).map(adaptVariant);
}

export async function analyzeCollection(collection: OwnedCard[]): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(collection),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, err.detail ?? 'Analysis failed');
  }

  return res.json();
}
