import type { CardRole } from './types';

export interface RoleTarget {
  min: number;
  preferred: number;
  max?: number;
}

export interface CommanderProfile {
  id: string;
  commander: string;
  displayName: string;
  description: string;
  landTarget: number;
  roleTargets: Partial<Record<CardRole, RoleTarget>>;
  roleWeights: Partial<Record<CardRole, number>>;
  synergyTag: string;
  priorityRoles: CardRole[];
  highMVTarget?: number;
  functionalHandDefinition: string;
}

export const PROFILES: Record<string, CommanderProfile> = {
  satoru_toolbox: {
    id: 'satoru_toolbox',
    commander: 'A-Satoru Umezawa',
    displayName: 'Satoru Toolbox Tempo',
    description: 'Ninjutsu enablers to deploy huge threats for free. Prioritizes evasive one-drops, ETB payoffs, and interaction.',
    landTarget: 36,
    roleTargets: {
      evasive_enabler: { min: 11, preferred: 14 },
      interaction: { min: 14, preferred: 18 },
      counterspell: { min: 4, preferred: 6 },
      creature_removal: { min: 5, preferred: 8 },
      draw: { min: 8, preferred: 12 },
      tutor: { min: 2, preferred: 4 },
      protection: { min: 3, preferred: 5 },
      etb_payoff: { min: 3, preferred: 6, max: 8 },
      ramp: { min: 4, preferred: 6 },
    },
    roleWeights: {
      evasive_enabler: 9,
      etb_payoff: 8,
      tutor: 8,
      protection: 7,
      draw: 7,
      selection: 6,
      counterspell: 6,
      creature_removal: 6,
      interaction: 5,
      ramp: 5,
      engine: 7,
      finisher: 6,
      topdeck_setup: 5,
      bridge: 4,
      sweeper: 4,
      ninjutsu_payoff: 8,
    },
    synergyTag: 'satoru',
    priorityRoles: ['evasive_enabler', 'etb_payoff', 'protection', 'interaction'],
    highMVTarget: 6,
    functionalHandDefinition: 'viable mana + evasive enabler + interaction or payoff',
  },

  yuriko_tempo: {
    id: 'yuriko_tempo',
    commander: 'Yuriko, the Tiger\'s Shadow',
    displayName: 'Yuriko Combat Tempo',
    description: 'One-drops set up ninjutsu chains for Yuriko reveals. Maximizes high-MV spells and topdeck manipulation.',
    landTarget: 34,
    roleTargets: {
      evasive_enabler: { min: 13, preferred: 16 },
      high_mana_reveal: { min: 5, preferred: 8 },
      topdeck_setup: { min: 4, preferred: 7 },
      draw: { min: 6, preferred: 10 },
      interaction: { min: 10, preferred: 14 },
      ramp: { min: 3, preferred: 5 },
    },
    roleWeights: {
      evasive_enabler: 10,
      high_mana_reveal: 9,
      topdeck_setup: 8,
      ninjutsu_payoff: 8,
      draw: 7,
      selection: 6,
      counterspell: 5,
      creature_removal: 5,
      interaction: 5,
      ramp: 4,
      finisher: 5,
      engine: 6,
    },
    synergyTag: 'yuriko',
    priorityRoles: ['evasive_enabler', 'high_mana_reveal', 'topdeck_setup'],
    highMVTarget: 10,
    functionalHandDefinition: 'blue + black mana + zero/one-drop evasive creature + Yuriko ninjutsu by turn 2-3',
  },

  talion_control: {
    id: 'talion_control',
    commander: 'Talion, the Kindly Lord',
    displayName: 'Talion Adaptive Control',
    description: 'Passive damage and card draw trigger off chosen number. Prioritizes interaction, draw, and sweepers.',
    landTarget: 38,
    roleTargets: {
      counterspell: { min: 7, preferred: 10 },
      creature_removal: { min: 6, preferred: 9 },
      sweeper: { min: 2, preferred: 3 },
      draw: { min: 10, preferred: 14 },
      tutor: { min: 2, preferred: 4 },
      ramp: { min: 5, preferred: 7 },
    },
    roleWeights: {
      draw: 9,
      counterspell: 9,
      creature_removal: 8,
      sweeper: 7,
      interaction: 7,
      tutor: 7,
      selection: 6,
      ramp: 6,
      engine: 7,
      protection: 6,
      bridge: 4,
    },
    synergyTag: 'talion',
    priorityRoles: ['draw', 'counterspell', 'creature_removal', 'sweeper'],
    functionalHandDefinition: 'viable mana + early interaction or card advantage + no excessive high-cost congestion',
  },

  yuffie_ninjutsu: {
    id: 'yuffie_ninjutsu',
    commander: 'Yuffie Kisaragi',
    displayName: 'Yuffie Ninjutsu Tempo',
    description: 'Hybrid Satoru/Yuriko style using Yuffie as the ninjutsu enabler commander.',
    landTarget: 35,
    roleTargets: {
      evasive_enabler: { min: 12, preferred: 15 },
      ninjutsu_payoff: { min: 4, preferred: 7 },
      interaction: { min: 12, preferred: 16 },
      draw: { min: 7, preferred: 11 },
      ramp: { min: 4, preferred: 6 },
    },
    roleWeights: {
      evasive_enabler: 9,
      ninjutsu_payoff: 9,
      draw: 7,
      selection: 6,
      counterspell: 6,
      creature_removal: 6,
      interaction: 6,
      ramp: 5,
      engine: 7,
      finisher: 5,
      topdeck_setup: 5,
      protection: 6,
    },
    synergyTag: 'yuriko',
    priorityRoles: ['evasive_enabler', 'ninjutsu_payoff', 'interaction'],
    functionalHandDefinition: 'blue + black mana + evasive enabler + ninjutsu payoff or interaction',
  },
};

export function getProfilesForCommander(commanderName: string): CommanderProfile[] {
  return Object.values(PROFILES).filter(p => p.commander === commanderName);
}
