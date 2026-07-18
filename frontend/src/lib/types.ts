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

export interface FeaturedCards {
  engines: string[];
  finishers: string[];
  setup: string[];
  interaction: string[];
  protection: string[];
  ramp: string[];
}

export interface DeckVariant {
  variantKey: 'free' | 'cheap' | 'competitive' | 'optimized' | string;
  label: string;
  description: string;
  strategyName: string;
  strategyId: string;
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
  featuredCards: FeaturedCards;
}

export interface ParseResult {
  cards: OwnedCard[];
  errors: string[];
}

// ── Collection analysis types ──────────────────────────────────────────────────

export interface ColorStrength {
  color: string;
  label: string;
  owned: number;
  rares: number;
  mythics: number;
}

export interface CommanderRecommendation {
  name: string;
  color_identity: string[];
  cmc: number;
  rarity: Rarity;
  type_line: string;
  owned: boolean;
  profile_id: string;
  profile_name: string;
  collection_fit: number;
  owned_pct: number;
  owned_pool: number;
  total_pool: number;
  role_coverage: Record<string, number>;
  score_breakdown: Record<string, number>;
  key_owned: string[];
  key_missing: { name: string; rarity: string }[];
}

export interface AnalysisResult {
  total_unique: number;
  total_copies: number;
  color_strength: ColorStrength[];
  type_distribution: Record<string, number>;
  role_counts: Record<string, number>;
  strongest_colors: string[];
  summary: string;
  recommendations: CommanderRecommendation[];
}

// ── Collection analysis V2 types ───────────────────────────────────────────────

export interface WildcardCostByRarity {
  common: number;
  uncommon: number;
  rare: number;
  mythic: number;
}

export interface RoleCoverageItem {
  role: string;
  target: number;
  deck_count: number;
  meets_minimum: boolean;
  meets_preferred: boolean;
}

export interface CommanderRecommendationV2 {
  name: string;
  color_identity: string[];
  cmc: number;
  rarity: Rarity;
  type_line: string;
  owned: boolean;
  strategy_id: string;
  strategy_name: string;
  strategy_intrinsic_fit: number;
  strategy_collection_coverage: number;
  build_readiness: number;
  wildcard_cost_by_rarity: WildcardCostByRarity;
  mana_readiness: number;
  strategy_role_coverage: RoleCoverageItem[];
  commander_owned: boolean;
  confidence: number;
  key_owned: string[];
  key_missing: { name: string; rarity: string }[];
  strengths: string[];
  deficits: string[];
  deck_quality: number;
  collection_readiness: number;
  completion_cost_by_rarity: WildcardCostByRarity;
  completion_cost_points: number;
  commander_wildcard_required: boolean;
  provisional: boolean;
  ranking_reason: string;
}

export interface AnalysisResultV2 {
  total_unique: number;
  total_copies: number;
  color_strength: ColorStrength[];
  type_distribution: Record<string, number>;
  role_counts: Record<string, number>;
  strongest_colors: string[];
  summary: string;
  strategy_filter: string;
  ranking_version: string;
  unmatched_cards: string[];
  analysis_warnings: string[];
  owned_recommendations: CommanderRecommendationV2[];
  unowned_recommendations: CommanderRecommendationV2[];
  recommendations: CommanderRecommendationV2[];
}
