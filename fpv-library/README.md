# FPV Library

Automated mirror and catalog of FPV / drone open-source projects from GitHub.

## Is continuous sync realistic?

**Yes, with limits.**

| What works well | What needs care |
|-----------------|-----------------|
| Daily `discover` + `sync` via GitHub Actions | GitHub API rate limits (~5k req/hr authenticated) |
| Tracking upstream commit SHA per repo | Large repos (ardupilot, betaflight, firmware) take longer to clone — still synced |
| Owner expansion (other repos by same author) | Not every search hit is worth mirroring — scoring filters noise |
| Auto-commit when upstream changes | Licenses must be respected (GPL, etc.) |

This library keeps a **`catalog.json`** manifest: source repo, local path, last upstream commit, discovery method, relevance score.

## Layout

```
fpv-library/
  catalog.json          # manifest of all tracked projects
  STRUCTURE.md          # what each folder/file means (UA + EN)
  repos/                # auto-synced mirrors (discovered repos)
  ../OpenIPC/           # example: full git copies of a GitHub org
  manifests/            # release SHA256 manifests (Caddx firmware, ground config)
  ground-config/        # downloaded Caddx Ground Configuration binaries (gitignored)
  scripts/
    discover.py         # parse GitHub search + expand owners
    discover_themes.py  # multi-query themed discovery (GCS, fiber, WFB, …)
    sync.py             # full git mirror: clone, fetch, LFS, submodules
    discover_org.py     # register all repos from a GitHub org (e.g. OpenIPC)
    generate_repo_index.py  # write ../REPOS.md (full project list)
    register_legacy.py  # register hand-copied example folders at repo root
  THEMED.md             # curated highlights by category
  HOOKS.md              # auto-generated interesting / watch list
```

**Full project index (description, path, date, size):** [`../REPOS.md`](../REPOS.md)  
**Exhibition wiki (one card per folder on disk):** [`../wiki/Home.md`](../wiki/Home.md)  
**Daily mirror policy:** [`MIRROR.md`](MIRROR.md) · [`../docs/MIRROR_POLICY.md`](../docs/MIRROR_POLICY.md)  
**Repository layout:** [`../docs/STRUCTURE.md`](../docs/STRUCTURE.md) · [`STRUCTURE.md`](STRUCTURE.md)

## Usage

### Discover (GitHub search + owner crawl)

```bash
# Page 4 of Fpv search, expand each owner's other repos
python3 fpv-library/scripts/discover.py \
  --search Fpv \
  --page 4 \
  --min-score 2.0 \
  --expand-owners \
  --owner-limit 5

# Pages 1–5
python3 fpv-library/scripts/discover.py --search Fpv --pages 1-5 --expand-owners

# Themed batch: GCS, fiber, WFB, OpenIPC, DroneBridge, owner ecosystems
python3 fpv-library/scripts/discover_themes.py --pages 1-2 --min-score 2.5

# Full org library (e.g. all OpenIPC repos → OpenIPC/<repo>/)
python3 fpv-library/scripts/discover_org.py --org OpenIPC --verdict keep
python3 fpv-library/scripts/sync.py --owner OpenIPC --verdict keep
```

See [`THEMED.md`](THEMED.md) for curated project highlights.

### Daily mirror (update + backfill)

```bash
# Full daily cycle (same as CI)
python3 fpv-library/scripts/sync_daily.py

# Or manually:
python3 fpv-library/scripts/sync.py --all --verdict keep --update-only
python3 fpv-library/scripts/sync.py --all --verdict keep --new-only --max-per-run 25
```

### Sync upstream updates

```bash
python3 fpv-library/scripts/sync.py --all
python3 fpv-library/scripts/sync.py --source RotorHazard/RotorHazard
```

Each synced folder gets `.fpv-library.json` with upstream commit metadata.

### Register legacy examples

```bash
python3 fpv-library/scripts/register_legacy.py
```

## Automation

`.github/workflows/fpv-library-sync.yml` runs **daily** (06:00 UTC):

1. **Keyword discovery** — rotating batch from `keywords.txt`
2. **Themed discovery** — GCS / link / fiber queries + owner ecosystems
3. **Triage** — `keep` / `watch` / `skip`; write `HOOKS.md`
4. **Register** — root-level project folders → catalog
5. **Mirror** — `sync_daily.py`: update all existing + clone ~25 new `keep` repos
6. **Index** — regenerate root `REPOS.md`
7. **Commit** — push catalog + mirror updates

Manual run: Actions → **FPV Library Sync** → Run workflow (adjust `backfill_per_run`).

### Keyword discovery

```bash
# Today's rotating batch (12 keywords)
python3 fpv-library/scripts/discover_keywords.py --pages 1 --expand-owners

# All keywords (heavy — uses API quota)
python3 fpv-library/scripts/discover_keywords.py --no-rotate --pages 1-2 --expand-owners
```

Edit `keywords.txt` to add search terms.

### Blocklist

`blocklist.txt` — repos never added to catalog (Telegram bots, mail bots, games, etc.).

### Triage hooks

When a search hit looks like a "hook", triage assigns:

| Verdict | Meaning |
|---------|---------|
| `keep` | Useful — auto-synced |
| `watch` | Weak signal — listed in `HOOKS.md` for review |
| `skip` | Noise (coursework, dotfiles, unrelated) |

```bash
python3 fpv-library/scripts/triage_catalog.py --force   # re-classify all
cat fpv-library/HOOKS.md                                 # interesting + watch list
```

### Sync policies

```bash
python3 fpv-library/scripts/sync.py --all --verdict keep
```

## Relevance scoring

`scripts/fpv_lib/scoring.py` scores repos by keywords (fpv, betaflight, inav, osd, vtx, elrs, …), stars, and negative signals (shop sites, empty dumps). Default `--min-score 2.0` filters low-quality hits.

## Adding search queries

Edit discover invocations or extend the workflow to rotate queries:

- `Fpv`
- `betaflight`
- `inav drone`
- `openipc fpv`
- `expresslrs`
