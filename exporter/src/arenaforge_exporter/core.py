from __future__ import annotations

import csv
import difflib
import json
import os
import re
import sqlite3
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import requests

from . import __version__


SCRYFALL_BULK_URL = "https://api.scryfall.com/bulk-data/default_cards"
SCRYFALL_HEADERS = {
    "User-Agent": "MTGA-collection-exporter-local/2.0",
    "Accept": "application/json",
}

LogFn = Callable[[str], None]
ProgressFn = Callable[[str, int, int], None]


def default_script_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path.cwd()


@dataclass(frozen=True)
class ExportPaths:
    base_dir: Path

    @property
    def lookup_file(self) -> Path:
        return self.base_dir / "arena_id_lookup.json"

    @property
    def anchor_file(self) -> Path:
        return self.base_dir / "last_anchors.json"

    @property
    def output_json(self) -> Path:
        return self.base_dir / "mtga_collection.json"

    @property
    def output_txt(self) -> Path:
        return self.base_dir / "mtga_collection.txt"

    @property
    def output_csv(self) -> Path:
        return self.base_dir / "mtga_collection.csv"


@dataclass
class Anchor:
    arena_id: int
    quantity: int
    name: str


@dataclass
class ExportResult:
    unique_entries: int
    exported_cards: int
    output_json: Path
    output_txt: Path
    output_csv: Path


class ExporterError(RuntimeError):
    """Expected user-facing exporter failure."""


def log_noop(_: str) -> None:
    return None


def progress_noop(_: str, __: int, ___: int) -> None:
    return None


def candidate_raw_paths() -> list[Path]:
    paths = [
        Path(r"C:\Program Files\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Raw"),
        Path(r"C:\Program Files (x86)\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Raw"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\MTGA\MTGA_Data\Downloads\Raw"),
        Path(r"C:\Program Files\Steam\steamapps\common\MTGA\MTGA_Data\Downloads\Raw"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        paths.append(Path(local_app_data) / "Programs" / "MTGA" / "MTGA_Data" / "Downloads" / "Raw")
    return paths


def get_local_mtga_path(manual_path: str | Path | None = None) -> Path | None:
    if manual_path:
        path = Path(manual_path).expanduser()
        return path if path.exists() else None
    for path in candidate_raw_paths():
        if path.exists():
            return path
    return None


def _table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    return {row[1] for row in cursor.execute(f'PRAGMA table_info("{table}")')}


def _load_localizations(cursor: sqlite3.Cursor, tables: set[str]) -> dict[int, str]:
    if "Localizations_enUS" in tables:
        cols = _table_columns(cursor, "Localizations_enUS")
        if {"LocId", "Loc"}.issubset(cols):
            cursor.execute('SELECT LocId, Loc FROM "Localizations_enUS"')
            return {int(loc_id): text for loc_id, text in cursor.fetchall() if text}
        if {"LocId", "Formatted"}.issubset(cols):
            cursor.execute('SELECT LocId, Formatted FROM "Localizations_enUS"')
            return {int(loc_id): text for loc_id, text in cursor.fetchall() if text}

    if "Localizations" in tables:
        cols = _table_columns(cursor, "Localizations")
        if {"Id", "Text", "Format"}.issubset(cols):
            try:
                cursor.execute(
                    'SELECT Id, Text FROM "Localizations" '
                    "WHERE Format LIKE '%en-US%' OR Format IS NULL"
                )
                rows = cursor.fetchall()
                if rows:
                    return {int(loc_id): text for loc_id, text in rows if text}
            except sqlite3.Error:
                pass
        if {"Id", "Text"}.issubset(cols):
            cursor.execute('SELECT Id, Text FROM "Localizations"')
            return {int(loc_id): text for loc_id, text in cursor.fetchall() if text}

    raise ExporterError(
        "No supported localization table found. Expected Localizations_enUS(LocId, Loc) "
        "or Localizations(Id, Text, Format)."
    )


def _load_cards_from_db(db_file: Path) -> dict[int, dict[str, str]]:
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "Cards" not in tables:
            raise ExporterError("Cards table not found.")

        loc_map = _load_localizations(cursor, tables)
        cols = _table_columns(cursor, "Cards")
        if not {"GrpId", "TitleId"}.issubset(cols):
            raise ExporterError("Cards table is missing GrpId or TitleId.")

        set_expr = "ExpansionCode" if "ExpansionCode" in cols else "NULL"
        cn_expr = "CollectorNumber" if "CollectorNumber" in cols else "NULL"
        cursor.execute(f'SELECT GrpId, TitleId, {set_expr}, {cn_expr} FROM "Cards"')

        lookup: dict[int, dict[str, str]] = {}
        for grp_id, title_id, set_code, collector_number in cursor.fetchall():
            name = loc_map.get(int(title_id)) if title_id is not None else None
            if name:
                lookup[int(grp_id)] = {
                    "name": name,
                    "set": set_code or "",
                    "collector_number": str(collector_number or ""),
                }
        return lookup
    finally:
        conn.close()


def load_local_mtga_database(
    manual_path: str | Path | None = None,
    log: LogFn = log_noop,
    progress: ProgressFn = progress_noop,
) -> dict[int, dict[str, str]]:
    raw_path = get_local_mtga_path(manual_path)
    if not raw_path:
        searched = "\n  - ".join(str(p) for p in candidate_raw_paths())
        log(f"Local MTGA Raw folder not found. Searched:\n  - {searched}")
        return {}

    log(f"Scanning local MTGA files in {raw_path}...")
    all_files = sorted(raw_path.glob("Raw_CardDatabase_*.mtga"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not all_files:
        all_files = sorted(raw_path.glob("*.mtga"), key=lambda f: f.stat().st_size, reverse=True)
    if not all_files:
        log(f"No .mtga files found in {raw_path}.")
        return {}

    failures: list[str] = []
    for index, db_file in enumerate(all_files, 1):
        progress(f"Checking {db_file.name}", index, len(all_files))
        if db_file.stat().st_size < 500 * 1024 and not db_file.name.startswith("Raw_CardDatabase_"):
            failures.append(f"{db_file.name}: skipped small file")
            continue
        try:
            lookup = _load_cards_from_db(db_file)
            if len(lookup) > 1000:
                log(f"Loaded {len(lookup)} cards from {db_file.name}.")
                return lookup
            failures.append(f"{db_file.name}: only {len(lookup)} localized cards found")
        except (sqlite3.Error, ExporterError) as exc:
            failures.append(f"{db_file.name}: {exc}")

    log("Local database scan did not find a usable card DB:")
    for failure in failures[:8]:
        log(f"  - {failure}")
    if len(failures) > 8:
        log(f"  - ...and {len(failures) - 8} more")
    return {}


def fetch_scryfall_database(log: LogFn = log_noop) -> dict[int, dict[str, str]]:
    log("Fetching card data from Scryfall API...")
    try:
        meta_response = requests.get(SCRYFALL_BULK_URL, headers=SCRYFALL_HEADERS, timeout=30)
        meta_response.raise_for_status()
        bulk_meta = meta_response.json()
        download_uri = bulk_meta.get("download_uri")
        if not download_uri:
            raise ExporterError(f"Scryfall response did not include download_uri: {bulk_meta}")

        cards_response = requests.get(download_uri, headers=SCRYFALL_HEADERS, timeout=120)
        cards_response.raise_for_status()
        cards_data = cards_response.json()

        lookup: dict[int, dict[str, str]] = {}
        for card in cards_data:
            arena_id = card.get("arena_id")
            if arena_id:
                lookup[int(arena_id)] = {
                    "name": card.get("name", "Unknown"),
                    "set": card.get("set", "").upper(),
                    "collector_number": card.get("collector_number", ""),
                }
        log(f"Loaded {len(lookup)} Arena cards from Scryfall.")
        return lookup
    except Exception as exc:
        log(f"Scryfall download failed: {exc}")
        return {}


def load_card_database(
    paths: ExportPaths,
    manual_raw_path: str | Path | None = None,
    refresh_cache: bool = False,
    log: LogFn = log_noop,
    progress: ProgressFn = progress_noop,
) -> dict[int, dict[str, str]]:
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    if paths.lookup_file.exists() and not refresh_cache:
        try:
            log("Loading cached card database...")
            with paths.lookup_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
            return {int(k): v for k, v in data.items() if isinstance(v, dict)}
        except Exception as exc:
            log(f"Cache could not be read and will be rebuilt: {exc}")

    lookup = load_local_mtga_database(manual_raw_path, log=log, progress=progress)
    if not lookup:
        log("Local database unavailable. Falling back to Scryfall.")
        lookup = fetch_scryfall_database(log=log)

    if lookup:
        try:
            with paths.lookup_file.open("w", encoding="utf-8") as file:
                json.dump({str(k): v for k, v in lookup.items()}, file)
            log("Card database cached.")
        except Exception as exc:
            log(f"Could not write card database cache: {exc}")
    return lookup


def load_saved_anchors(paths: ExportPaths) -> list[Anchor]:
    if not paths.anchor_file.exists():
        return []
    with paths.anchor_file.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    anchors: list[Anchor] = []
    for item in raw:
        if isinstance(item, dict):
            anchors.append(Anchor(int(item["arena_id"]), int(item["quantity"]), str(item["name"])))
        else:
            arena_id, quantity, name = item
            anchors.append(Anchor(int(arena_id), int(quantity), str(name)))
    return anchors


def save_anchors(paths: ExportPaths, anchors: Iterable[Anchor]) -> None:
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    data = [
        {"arena_id": anchor.arena_id, "quantity": anchor.quantity, "name": anchor.name}
        for anchor in anchors
    ]
    with paths.anchor_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def resolve_anchor(name: str, quantity: int, name_to_id: dict[str, int]) -> Anchor:
    clean = name.strip()
    if not clean:
        raise ExporterError("Anchor card name is required.")
    if quantity < 1:
        raise ExporterError(f"Anchor quantity for {clean} must be at least 1.")

    search = clean.lower()
    arena_id = name_to_id.get(search)
    if arena_id:
        return Anchor(arena_id, quantity, clean)

    matches = difflib.get_close_matches(search, name_to_id.keys(), n=1, cutoff=0.72)
    if matches:
        match = matches[0]
        return Anchor(name_to_id[match], quantity, match.title())

    raise ExporterError(f"Anchor card not found in card database: {clean}")


def escaped_anchor_pattern(arena_id: int, quantity: int) -> bytes:
    return re.escape(struct.pack("<II", arena_id, quantity))


def connect_to_mtga(log: LogFn = log_noop):
    try:
        import pymem

        pm = pymem.Pymem("MTGA.exe")
        log(f"Connected to MTGA.exe (PID: {pm.process_id}).")
        return pm
    except ModuleNotFoundError as exc:
        raise ExporterError("pymem is not installed. Install requirements or use the packaged Windows exe.") from exc
    except Exception as exc:
        message = str(exc)
        if "Could not find process" in message or "MTGA.exe" in message:
            raise ExporterError("MTGA.exe is not running. Open MTG Arena, visit Collection/Decks, then try again.") from exc
        raise ExporterError(
            f"Could not access MTGA.exe memory: {exc}\n"
            "If MTG Arena is running, try running ArenaForge MTGA Exporter as Administrator."
        ) from exc


def find_blocks(pm, addr: int) -> list[dict[int, int]]:
    try:
        data = pm.read_bytes(max(0, addr - 1024 * 1024), 4 * 1024 * 1024)
        usable = len(data) - (len(data) % 4)
        ints = struct.unpack(f"<{usable // 4}I", data[:usable])

        blocks: list[dict[int, int]] = []
        for offset in (0, 1):
            current: dict[int, int] = {}
            misses = 0
            for index in range(offset, len(ints) - 1, 2):
                card_id, quantity = ints[index], ints[index + 1]
                if 1000 <= card_id < 500000 and 1 <= quantity <= 400:
                    current[card_id] = quantity
                    misses = 0
                else:
                    misses += 1

                if misses > 50:
                    if len(current) > 50:
                        blocks.append(current)
                    current = {}
                    misses = 0
            if len(current) > 50:
                blocks.append(current)
        return blocks
    except Exception:
        return []


def scan_collection_memory(pm, anchors: list[Anchor], log: LogFn = log_noop, progress: ProgressFn = progress_noop) -> dict[int, int]:
    if not anchors:
        raise ExporterError("At least one anchor card is required.")

    matches: list[int] = []
    for index, anchor in enumerate(anchors, 1):
        progress(f"Scanning for {anchor.name}", index, len(anchors))
        try:
            result = pm.pattern_scan_all(
                escaped_anchor_pattern(anchor.arena_id, anchor.quantity),
                return_multiple=True,
            )
        except Exception as exc:
            raise ExporterError(f"Memory scan failed for {anchor.name}: {exc}") from exc
        if result:
            matches.extend(result)
            log(f"Found anchor match for {anchor.name}.")
            if anchor.quantity > 1:
                break

    if not matches:
        raise ExporterError(
            "Scanner failed to locate collection data from the supplied anchors. "
            "Open Collection/Decks in MTG Arena, scroll through your collection, and try different owned cards."
        )

    candidates: list[dict[int, int]] = []
    for match in matches:
        candidates.extend(find_blocks(pm, match))

    if not candidates:
        raise ExporterError("Anchor matches were found, but no valid collection data block was detected.")

    collection = max(candidates, key=len)
    log(f"Found {len(collection)} unique memory entries.")
    return collection


def normalize_collection(collection: dict[int, int], card_db: dict[int, dict[str, str]]) -> list[dict[str, object]]:
    processed: dict[tuple[str, str], dict[str, object]] = {}
    for card_id, quantity in collection.items():
        info = card_db.get(card_id)
        if not info:
            continue
        key = (info["name"], info.get("set", ""))
        if key not in processed:
            processed[key] = {
                "count": 0,
                "name": info["name"],
                "set": info.get("set", ""),
                "cn": info.get("collector_number", ""),
                "arena_ids": [],
            }
        processed[key]["count"] = int(processed[key]["count"]) + int(quantity)
        processed[key]["arena_ids"].append(card_id)
    return sorted(processed.values(), key=lambda item: (str(item["name"]), str(item["set"])))


def write_exports(final_list: list[dict[str, object]], paths: ExportPaths) -> None:
    paths.base_dir.mkdir(parents=True, exist_ok=True)

    with paths.output_txt.open("w", encoding="utf-8") as file:
        for item in final_list:
            set_str = f" ({item['set']})" if item.get("set") else ""
            file.write(f"{item['count']} {item['name']}{set_str}\n")

    with paths.output_json.open("w", encoding="utf-8") as file:
        json.dump(final_list, file, indent=2)

    with paths.output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Count", "Name", "Edition", "Condition", "Language", "Foil", "Tag"])
        for item in final_list:
            writer.writerow([item["count"], item["name"], item.get("set", ""), "Near Mint", "English", "", ""])


def run_export(
    anchors: list[Anchor],
    output_dir: str | Path,
    manual_raw_path: str | Path | None = None,
    refresh_cache: bool = False,
    log: LogFn = log_noop,
    progress: ProgressFn = progress_noop,
) -> ExportResult:
    paths = ExportPaths(Path(output_dir))
    log(f"ArenaForge MTGA Exporter | {__version__}")
    log(f"Output folder: {paths.base_dir}")
    card_db = load_card_database(paths, manual_raw_path, refresh_cache, log=log, progress=progress)
    if not card_db:
        raise ExporterError("Database init failed. Local MTGA DB and Scryfall fallback were unavailable.")

    resolved_anchors: list[Anchor] = []
    name_to_id = {info["name"].lower(): card_id for card_id, info in card_db.items()}
    for anchor in anchors:
        if anchor.arena_id:
            resolved_anchors.append(anchor)
        else:
            resolved_anchors.append(resolve_anchor(anchor.name, anchor.quantity, name_to_id))
    save_anchors(paths, resolved_anchors)

    pm = connect_to_mtga(log=log)
    collection = scan_collection_memory(pm, resolved_anchors, log=log, progress=progress)
    final_list = normalize_collection(collection, card_db)
    write_exports(final_list, paths)

    return ExportResult(
        unique_entries=len(collection),
        exported_cards=len(final_list),
        output_json=paths.output_json,
        output_txt=paths.output_txt,
        output_csv=paths.output_csv,
    )


def open_output_folder(path: Path) -> None:
    try:
        subprocess.Popen(f'explorer /select,"{path}"')
    except Exception:
        pass
