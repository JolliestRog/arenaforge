# ArenaForge Recovery

ArenaForge is recoverable from either GitHub plus source data, or directly
from the blue03 Restic repository on blue01.

## Backup location

- Repository: `sftp:blue01:/mnt/media/backups/restic/blue03`
- Password file on blue03: `/home/blue03/.config/restic/blue03-media-backup.password`
- Nightly user timer: `restic-blue03-backup.timer`
- Backup coverage: the full `/srv/arenaforge` tree, excluding `.git`,
  `frontend/node_modules`, and Python test/cache directories.

The backup contains the runtime databases, Scryfall input snapshot, deployed
frontend build, compose configuration, exporter, and source checkout.

## Full restore

On a replacement blue03 host with Restic and SSH access to blue01:

```bash
export RESTIC_REPOSITORY='sftp:blue01:/mnt/media/backups/restic/blue03'
export RESTIC_PASSWORD_FILE='/home/blue03/.config/restic/blue03-media-backup.password'
restic snapshots --host blue03 --path /srv/arenaforge
restic restore latest --host blue03 --path /srv/arenaforge --target /
cd /srv/arenaforge
docker compose up -d --build
```

Verify:

```bash
docker exec arenaforge-api python -c 'import json,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8000/health")))'
```

## Regenerate instead of restoring generated data

The GitHub repository contains the deterministic strategy rules and pipeline.
The Restic backup contains both accepted pipeline inputs:

- `backend/data/oracle_cards.json` and `oracle_meta.json`
- `backend/data/cards.db`

After restoring either input, rebuild the strategy database:

```bash
cd /srv/arenaforge
python3 -m strategy.run --reset
cd frontend
npm ci
npm run build
cd ..
docker compose up -d --build
```

The pipeline prefers `oracle_cards.json` and falls back to `cards.db`.

## Source-only recovery

```bash
git clone git@github.com:JolliestRog/arenaforge.git /srv/arenaforge
cd /srv/arenaforge
python3 backend/run_pipeline.py --force
python3 -m strategy.run --reset
cd frontend
npm ci
npm run build
cd ..
docker compose up -d --build
```

The backend pipeline downloads a fresh Scryfall `oracle_cards` snapshot and
builds `cards.db`; the strategy pipeline then builds `strategy.db`. If Restic
is available, restoring `/srv/arenaforge/backend/data` first avoids the
download.

## Off-host credentials

The Restic password and the SSH private key used to reach blue01 cannot be
recovered from inside the encrypted repository. Keep both in a password
manager or a separate encrypted recovery kit; never commit them to this
repository. If those credentials are unavailable, use the source-only path
above with a fresh Scryfall download.

## Integrity checks

Each backup writes `arenaforge-recovery.txt` under its temporary metadata
tree. It records the Git commit and SHA-256 hashes for `strategy.db`,
`cards.db`, and `oracle_cards.json`.
