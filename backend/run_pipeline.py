#!/usr/bin/env python3
"""Fetch Scryfall oracle_cards and load Historic Brawl-legal cards into SQLite."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pipeline.fetch import fetch_oracle_cards
from pipeline.ingest import ingest


def main():
    parser = argparse.ArgumentParser(description="ArenaForge Scryfall pipeline")
    parser.add_argument("--force", action="store_true", help="Re-download even if cache is fresh")
    args = parser.parse_args()

    cards_path = fetch_oracle_cards(force=args.force)
    ingest(cards_path)


if __name__ == "__main__":
    main()
