"""Download Scryfall oracle_cards bulk data, caching by updated_at timestamp."""

import json
import time
import urllib.request
from pathlib import Path

BULK_API = "https://api.scryfall.com/bulk-data"
DATA_DIR = Path(__file__).parent.parent / "data"
HEADERS = {"User-Agent": "ArenaForge/2.0", "Accept": "application/json"}


def _get_oracle_bulk_info() -> dict:
    req = urllib.request.Request(BULK_API, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    for item in payload["data"]:
        if item["type"] == "oracle_cards":
            return item
    raise RuntimeError("oracle_cards not found in Scryfall bulk-data listing")


def fetch_oracle_cards(force: bool = False) -> Path:
    """Return path to cached oracle_cards JSON, downloading if stale or missing."""
    DATA_DIR.mkdir(exist_ok=True)
    meta_path = DATA_DIR / "oracle_meta.json"
    cards_path = DATA_DIR / "oracle_cards.json"

    info = _get_oracle_bulk_info()
    remote_updated = info["updated_at"]

    if not force and meta_path.exists() and cards_path.exists():
        cached_meta = json.loads(meta_path.read_text())
        if cached_meta.get("updated_at") == remote_updated:
            print(f"[fetch] Cache hit — {remote_updated}")
            return cards_path

    print(f"[fetch] Downloading oracle_cards ({info['size']:,} bytes) …")
    download_url = info["download_uri"]
    req = urllib.request.Request(download_url, headers=HEADERS)
    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        cards_path.write_bytes(resp.read())
    print(f"[fetch] Done in {time.time() - t0:.1f}s")

    meta_path.write_text(json.dumps({"updated_at": remote_updated}))
    return cards_path
