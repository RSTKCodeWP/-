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
    discover_themes.py  # multi-query themed discovery (GCS, fiber, WFB, …)
    sync.py             # pull upstream updates when commit changes
    register_legacy.py  # register hand-copied example folders at repo root
  THEMED.md             # curated highlights by category
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

# Themed batch: GCS, fiber, WFB, OpenIPC, DroneBridge, owner ecosystems
python3 fpv-library/scripts/discover_themes.py --pages 1-2 --min-score 2.5
```

See [`THEMED.md`](THEMED.md) for curated project highlights.

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

`.github/workflows/fpv-library-sync.yml` runs **daily**:

1. **Keyword discovery** — rotating batch from `keywords.txt` (FPV, betaflight, OpenIPC, ELRS, GCS, fiber, …)
2. **Themed discovery** — GCS / link / fiber queries + owner ecosystems
3. **Triage** — classify each repo: `keep` / `watch` / `skip`; write `HOOKS.md`
4. **Sync** — pull upstream for `verdict=keep` repos (skip >150 MB)
5. **Commit** — push catalog + mirror updates

Manual run: Actions → **FPV Library Sync** → Run workflow.

### Keyword discovery

```bash
# Today's rotating batch (12 keywords)
python3 fpv-library/scripts/discover_keywords.py --pages 1 --expand-owners

# All keywords (heavy — uses API quota)
python3 fpv-library/scripts/discover_keywords.py --no-rotate --pages 1-2 --expand-owners
```

Edit `keywords.txt` to add search terms.

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
python3 fpv-library/scripts/sync.py --all --verdict keep --max-size-mb 150
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
