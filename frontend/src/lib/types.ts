export type Rarity = 'common' | 'uncommon' | 'rare' | 'mythic';

export type CardRole =
  | 'land'
  | 'fixing'
  | 'ramp'
  | 'draw'
  | 'selection'
  | 'tutor'
  | 'protection'
  | 'counterspell'
  | 'interaction'
  | 'creature_removal'
  | 'sweeper'
  | 'evasive_enabler'
  | 'ninjutsu_payoff'
  | 'etb_payoff'
  | 'engine'
  | 'finisher'
  | 'high_mana_reveal'
  | 'topdeck_setup'
  | 'graveyard_hate'
  | 'artifact_answer'
  | 'bridge';

export interface CardData {
  name: string;
  mv: number;
  colors: string[];
  colorIdentity: string[];
  rarity: Rarity;
  roles: CardRole[];
  synergyTags: string[];
  isLand: boolean;
  isCreature: boolean;
  typeLine: string;
}

export interface OwnedCard {
  name: string;
  count: number;
}

export interface WildcardBudget {
  common: number;
  uncommon: number;
  rare: number;
  mythic: number;
}

export interface BuildRequest {
  collection: OwnedCard[];
  commander: string;
  profile: string;
  wildcardBudget: WildcardBudget;
}

export interface DeckCard {
  card: CardData;
  owned: boolean;
  wildcardCost: Rarity | null;
  reason: string;
  score: number;
}

export interface ExcludedCard {
  name: string;
  score: number;
  reason: string;
}

export interface DeckVariant {
  variantKey: 'performance' | 'wildcard' | 'consistency';
  label: string;
  description: string;
  commander: CardData;
  cards: DeckCard[];
  roleCounts: Record<string, number>;
  manaCurve: Record<number, number>;
  wildcardCost: WildcardBudget;
  functionalHandEstimate: number;
  weakestCards: string[];
  excludedHighScorers: ExcludedCard[];
  arenaExport: string;
  score: number;
  infeasible: boolean;
}

export interface ParseResult {
  cards: OwnedCard[];
  errors: string[];
}
