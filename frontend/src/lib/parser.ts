import type { OwnedCard, ParseResult } from './types';

// Parse Arena collection/deck export:
//   2 Brainstorm (STA) 12
//   1 Counterspell (TSR) 73
// Also handles plain "Brainstorm" or "2 Brainstorm" lines.
// Also handles CSV with name,count or count,name headers.

function normalizeCardName(raw: string): string {
  return raw.trim().replace(/\s+/g, ' ');
}

function parseArenaLine(line: string): OwnedCard | null {
  // Arena format: "<count> <name> (<set>) [<collector_number>]"
  // Collector number is optional — our exporter emits "1 Brainstorm (STA)" without it.
  const arenaMatch = line.match(/^(\d+)\s+(.+?)\s+\([A-Z0-9]+\)(?:\s+\d+)?\s*$/);
  if (arenaMatch) {
    return { count: parseInt(arenaMatch[1], 10), name: normalizeCardName(arenaMatch[2]) };
  }

  // "count name" without set info
  const countFirst = line.match(/^(\d+)\s+(.+)$/);
  if (countFirst) {
    return { count: parseInt(countFirst[1], 10), name: normalizeCardName(countFirst[2]) };
  }

  // Plain card name
  const plain = line.match(/^([A-Za-z,'\-\s]+)$/);
  if (plain && plain[1].trim().length > 1) {
    return { count: 1, name: normalizeCardName(plain[1]) };
  }

  return null;
}

function parseCsv(text: string): ParseResult {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  if (lines.length === 0) return { cards: [], errors: [] };

  const cards: OwnedCard[] = [];
  const errors: string[] = [];

  const header = lines[0].toLowerCase().split(/[,\t]/);
  const nameIdx = header.findIndex(h => h.includes('name') || h === 'card');
  const countIdx = header.findIndex(h => h.includes('count') || h.includes('qty') || h.includes('quantity'));

  if (nameIdx === -1) {
    return { cards: [], errors: ['CSV missing a "name" column.'] };
  }

  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(/[,\t]/);
    const name = cols[nameIdx]?.trim();
    if (!name) continue;
    const count = countIdx >= 0 ? parseInt(cols[countIdx] ?? '1', 10) : 1;
    if (isNaN(count) || count <= 0) {
      errors.push(`Line ${i + 1}: invalid count for "${name}"`);
      continue;
    }
    cards.push({ name: normalizeCardName(name), count });
  }

  return { cards, errors };
}

export function parseCollection(raw: string): ParseResult {
  const text = raw.trim();
  if (!text) return { cards: [], errors: ['Input is empty.'] };

  // Detect CSV
  if (text.split('\n')[0].toLowerCase().includes(',') && text.split('\n')[0].toLowerCase().match(/name|card/)) {
    return parseCsv(text);
  }

  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);

  // A real Arena collection or deck export always has lines starting with a count (digit).
  // If none exist, the user almost certainly pasted the wrong thing.
  const digitLines = lines.filter(l => /^\d/.test(l));
  if (digitLines.length === 0 && lines.length > 2) {
    return {
      cards: [],
      errors: ["This doesn't look like an Arena export — no card counts found. Each line should start with a number, e.g. \"2 Counterspell (TSR) 73\". Make sure you're pasting the output from the Arena Exporter."],
    };
  }

  const cards: OwnedCard[] = [];
  const errors: string[] = [];
  const seen = new Map<string, number>();

  // Skip Arena deck section headers like "Deck", "Sideboard", "Commander"
  const skipPatterns = /^(Deck|Sideboard|Commander|About|Format|Name|Companion)\s*$/i;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (skipPatterns.test(line)) continue;

    const card = parseArenaLine(line);
    if (!card) {
      if (line.length > 1) errors.push(`Line ${i + 1}: could not parse "${line}"`);
      continue;
    }

    const key = card.name.toLowerCase();
    if (seen.has(key)) {
      seen.set(key, seen.get(key)! + card.count);
    } else {
      seen.set(key, card.count);
      cards.push(card);
    }
  }

  // Apply merged counts
  for (const card of cards) {
    card.count = seen.get(card.name.toLowerCase()) ?? card.count;
  }

  return { cards, errors };
}
