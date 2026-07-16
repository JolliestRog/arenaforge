# ArenaForge MTGA Collection Exporter

Windows exporter for MTG Arena collections. This is a community fix of
`NthPhantom10/MTGA-collection-exporter` for current MTG Arena local database
schemas and current Scryfall API behavior.

Version: `2.0.1 community fix`

## Quick Start

1. Open MTG Arena.
2. Go to Collection or Decks and scroll around so the collection loads into memory.
3. Run `ArenaForge-MTGA-Exporter.exe`.
4. Choose an output folder.
5. Enter anchor cards you own and their quantities.
6. Click `Start export`.
7. Find these files in the output folder:
   - `mtga_collection.json`
   - `mtga_collection.txt`
   - `mtga_collection.csv`

Rare or mythic cards with unusual owned quantities make better anchors. If the
scan fails, scroll through the Arena collection again and try different anchors.

## What This Fixes

- Scryfall fallback now uses `https://api.scryfall.com/bulk-data/default_cards`.
- Scryfall requests include a compliant custom `User-Agent`.
- Missing `download_uri` is reported instead of crashing with `KeyError`.
- The current MTGA Raw folder is detected:
  `C:\Program Files\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Raw`.
- Local DB loading supports both:
  - `Localizations_enUS(LocId, Loc)`
  - `Localizations(Id, Text, Format)`
- Local DB failures are logged with the actual reason.
- Memory scan binary patterns are escaped before `pymem.pattern_scan_all`.
- Process access failures explain when to try running as Administrator.

## CLI Usage

The GUI is recommended for normal users. Advanced users can run:

```powershell
python mtg.py --anchor "Island=4" --anchor "Go for the Throat=2"
```

Options:

```text
--output-dir PATH      Folder for cache and exported files
--raw-dir PATH         Optional MTGA Downloads\Raw override
--refresh-cache        Rebuild arena_id_lookup.json
--anchor "Name=Qty"    Anchor card; may be repeated
```

## Build Locally On Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pytest
pyinstaller ArenaForge-MTGA-Exporter.spec --noconfirm --clean
```

The executable will be created at:

```text
dist\ArenaForge-MTGA-Exporter.exe
```


## Hosting The Built EXE In ArenaForge

After the Windows workflow produces `ArenaForge-MTGA-Exporter.exe`, place the same file in both locations on blue03:

```text
/srv/arenaforge/ArenaForge-MTGA-Exporter.exe
/srv/arenaforge/frontend/public/downloads/ArenaForge-MTGA-Exporter.exe
```

The second path is served by the DeckForge/ArenaForge frontend at:

```text
/downloads/ArenaForge-MTGA-Exporter.exe
```

## Troubleshooting

- If MTG Arena is not detected, open Arena first and visit Collection or Decks.
- If memory access fails, run the exporter as Administrator.
- If anchors fail, scroll through the collection and use different owned cards.
- If the local card database cannot be read, use the Raw folder override or allow
  the Scryfall fallback to download card metadata.
