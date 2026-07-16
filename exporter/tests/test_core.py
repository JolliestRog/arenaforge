from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path
from unittest.mock import Mock

from arenaforge_exporter.core import (
    SCRYFALL_BULK_URL,
    SCRYFALL_HEADERS,
    ExportPaths,
    escaped_anchor_pattern,
    fetch_scryfall_database,
    load_card_database,
    load_local_mtga_database,
    normalize_collection,
    write_exports,
)


def create_current_schema_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE Localizations_enUS (LocId INTEGER, Formatted TEXT, Loc TEXT)")
        cur.execute(
            "CREATE TABLE Cards (GrpId INTEGER, TitleId INTEGER, ExpansionCode TEXT, CollectorNumber TEXT)"
        )
        for index in range(1101):
            cur.execute(
                "INSERT INTO Localizations_enUS VALUES (?, ?, ?)",
                (index + 5000, f"Formatted {index}", f"Card {index}"),
            )
            cur.execute(
                "INSERT INTO Cards VALUES (?, ?, ?, ?)",
                (index + 10000, index + 5000, "TST", str(index)),
            )
        conn.commit()
    finally:
        conn.close()


def create_old_schema_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE Localizations (Id INTEGER, Text TEXT, Format TEXT)")
        cur.execute("CREATE TABLE Cards (GrpId INTEGER, TitleId INTEGER)")
        for index in range(1101):
            cur.execute("INSERT INTO Localizations VALUES (?, ?, ?)", (index + 1, f"Old Card {index}", "en-US"))
            cur.execute("INSERT INTO Cards VALUES (?, ?)", (index + 20000, index + 1))
        conn.commit()
    finally:
        conn.close()


def test_current_localizations_enus_schema_loads(tmp_path: Path) -> None:
    raw = tmp_path / "Raw"
    raw.mkdir()
    db_path = raw / "Raw_CardDatabase_test.mtga"
    create_current_schema_db(db_path)

    lookup = load_local_mtga_database(raw)

    assert len(lookup) == 1101
    assert lookup[10000]["name"] == "Card 0"
    assert lookup[10000]["set"] == "TST"


def test_old_localizations_schema_loads(tmp_path: Path) -> None:
    raw = tmp_path / "Raw"
    raw.mkdir()
    db_path = raw / "Raw_CardDatabase_old.mtga"
    create_old_schema_db(db_path)

    lookup = load_local_mtga_database(raw)

    assert len(lookup) == 1101
    assert lookup[20000]["name"] == "Old Card 0"


def test_scryfall_uses_default_cards_endpoint_and_headers(monkeypatch) -> None:
    meta = Mock()
    meta.raise_for_status.return_value = None
    meta.json.return_value = {"download_uri": "https://example.test/cards.json"}
    cards = Mock()
    cards.raise_for_status.return_value = None
    cards.json.return_value = [
        {"arena_id": 123, "name": "Test Card", "set": "tst", "collector_number": "7"}
    ]
    get = Mock(side_effect=[meta, cards])
    monkeypatch.setattr("arenaforge_exporter.core.requests.get", get)

    lookup = fetch_scryfall_database()

    assert lookup[123]["name"] == "Test Card"
    assert get.call_args_list[0].args[0] == SCRYFALL_BULK_URL
    assert get.call_args_list[0].kwargs["headers"] == SCRYFALL_HEADERS
    assert get.call_args_list[1].kwargs["headers"] == SCRYFALL_HEADERS


def test_scryfall_missing_download_uri_does_not_raise(monkeypatch) -> None:
    meta = Mock()
    meta.raise_for_status.return_value = None
    meta.json.return_value = {"object": "error"}
    monkeypatch.setattr("arenaforge_exporter.core.requests.get", Mock(return_value=meta))

    assert fetch_scryfall_database() == {}


def test_anchor_pattern_is_escaped_bytes() -> None:
    raw = struct.pack("<II", 41, 2)

    escaped = escaped_anchor_pattern(41, 2)

    assert escaped != raw
    assert b"\\)" in escaped


def test_write_exports_creates_required_formats(tmp_path: Path) -> None:
    final = normalize_collection(
        {100: 2},
        {100: {"name": "Go for the Throat", "set": "BRO", "collector_number": "102"}},
    )

    paths = ExportPaths(tmp_path)
    write_exports(final, paths)

    assert paths.output_txt.read_text(encoding="utf-8") == "2 Go for the Throat (BRO)\n"
    assert json.loads(paths.output_json.read_text(encoding="utf-8"))[0]["name"] == "Go for the Throat"
    assert "Count,Name,Edition" in paths.output_csv.read_text(encoding="utf-8")


def test_cache_loads_without_scryfall_or_local_scan(tmp_path: Path, monkeypatch) -> None:
    paths = ExportPaths(tmp_path)
    paths.lookup_file.write_text(json.dumps({"42": {"name": "Cached", "set": "TST"}}), encoding="utf-8")
    local = Mock()
    scryfall = Mock()
    monkeypatch.setattr("arenaforge_exporter.core.load_local_mtga_database", local)
    monkeypatch.setattr("arenaforge_exporter.core.fetch_scryfall_database", scryfall)

    lookup = load_card_database(paths)

    assert lookup[42]["name"] == "Cached"
    local.assert_not_called()
    scryfall.assert_not_called()
