# Development and Verification

DeckForge's required checks run from a clean checkout without the ignored
production card databases or network access. Use Python 3.12 and Node 22.

## Frontend

```bash
cd frontend
npm ci
npm run lint
npm test
npm run build
```

## Backend

```bash
python3.12 -m venv .venv-backend
. .venv-backend/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -m "not live_data" --strict-markers
```

The required backend test generates production-shaped card data, builds fresh
card and strategy SQLite databases in a temporary directory, normalizes an
Arena export alias, analyzes a collection, solves a 99-card deck, and validates
the resulting 100-card Arena export.

The broader VPS snapshot regressions are marked `live_data`. They are optional
and may be run only where `backend/data/cards.db` and
`strategy/data/strategy.db` are present:

```bash
cd backend
python -m pytest -m live_data
```

## Strategy pipeline

```bash
python3.12 -m venv .venv-strategy
. .venv-strategy/bin/activate
python -m pip install -r strategy/requirements-dev.txt
python -m pytest strategy/tests --strict-markers
```

These tests generate a fresh strategy database from the deterministic fixture
and fail if accepted strategies or weighted card rows are absent.

## Windows exporter

Run from a Windows Python 3.12 environment:

```powershell
cd exporter
python -m pip install -r requirements-dev.txt
pytest
pyinstaller ArenaForge-MTGA-Exporter.spec --noconfirm --clean
```

## Docker smoke check

```bash
docker build --file backend/Dockerfile backend
```
