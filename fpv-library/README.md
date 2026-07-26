# FPV Library

Automated mirror and catalog of FPV / drone open-source projects from GitHub.

## Is continuous sync realistic?

**Yes, with limits.**

| What works well | What needs care |
|-----------------|-----------------|
| Daily `discover` + `sync` via GitHub Actions | GitHub API rate limits (~5k req/hr authenticated) |
| Tracking upstream commit SHA per repo | Very large repos (e.g. full flight stacks) bloat the mirror |
| Owner expansion (other repos by same author) | Not every search hit is worth mirroring — scoring filters noise |
| Auto-commit when upstream changes | Licenses must be respected (GPL, etc.) |

This library keeps a **`catalog.json`** manifest: source repo, local path, last upstream commit, discovery method, relevance score.

## Layout

```
fpv-library/
  catalog.json          # manifest of all tracked projects
  repos/                # auto-synced mirrors (discovered repos)
  scripts/
    discover.py         # parse GitHub search + expand owners
    sync.py             # pull upstream updates when commit changes
    register_legacy.py  # register hand-copied example folders at repo root
```

Legacy example copies (Steer, SkySweep32, wfb-ng, …) remain at the repository root and are listed in `catalog.json` with `"legacy": true`. New discoveries go under `fpv-library/repos/`.

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

`.github/workflows/fpv-library-sync.yml` runs daily:

1. **Discover** — search GitHub for `Fpv`, score results, optionally crawl owners
2. **Sync** — re-clone any repo whose default-branch SHA changed
3. **Commit** — push updates to this repository

Manual run: Actions → **FPV Library Sync** → Run workflow.

## Relevance scoring

`scripts/fpv_lib/scoring.py` scores repos by keywords (fpv, betaflight, inav, osd, vtx, elrs, …), stars, and negative signals (shop sites, empty dumps). Default `--min-score 2.0` filters low-quality hits.

## Adding search queries

Edit discover invocations or extend the workflow to rotate queries:

- `Fpv`
- `betaflight`
- `inav drone`
- `openipc fpv`
- `expresslrs`
