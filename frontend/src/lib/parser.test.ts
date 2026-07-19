import { describe, expect, it } from 'vitest';

import { parseCollection } from './parser';

describe('parseCollection', () => {
  it('parses Arena deck sections and merges duplicate card counts', () => {
    const result = parseCollection(`Commander
1 Lorthos, the Tidemaker (JMP) 13

Deck
2 Island (ANB) 113
1 Counterspell (STA) 15
3 Island`);

    expect(result.errors).toEqual([]);
    expect(result.cards).toEqual([
      { name: 'Lorthos, the Tidemaker', count: 1 },
      { name: 'Island', count: 5 },
      { name: 'Counterspell', count: 1 },
    ]);
  });

  it('rejects empty input instead of silently inventing sample data', () => {
    expect(parseCollection('')).toEqual({
      cards: [],
      errors: ['Input is empty.'],
    });
  });
});
