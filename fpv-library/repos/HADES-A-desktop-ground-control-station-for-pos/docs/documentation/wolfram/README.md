# Wolfram hero visuals (user-run handoff)

These three Wolfram Language scripts render the showpiece visuals where Wolfram beats
matplotlib: a lit 3D error surface, a true geographic survivor map, and a 3D calibration
bar field. They read the **real exported data files** (every number is genuine sim or
real-pipeline output, never invented), so the renders reflect the measured system.

**This is the one place in Phase 7 that the user runs the tool.** The build does not assume
Wolfram is installed. I generate the `.wl` code and the data; you run it locally and the PNGs
land in `../figures/`, where the README and in-app docs pick them up.

## Prerequisites

1. A local Wolfram install with `wolframscript` on your PATH (Wolfram 13+ recommended;
   `error_surface_3d.wl` uses scattered-data `Interpolation`, which older versions handle
   less gracefully - the script notes the `RBFInterpolation` fallback if needed).
2. The data files must exist first. Regenerate them from the repo:

   ```bash
   # from the repo root
   cd service
   # the four routine families (detection, localization strata, coverage, real-time)
   uv run hades-export-doc-data
   # the dense localization-error surface grid (real sim sweep; ~minutes)
   uv run python ../docs/documentation/wolfram/make_surface_data.py
   # the demo-mission contacts (real localizer output) for the geo map
   uv run python ../docs/documentation/wolfram/make_mission_contacts.py
   ```

   These write into `docs/documentation/data/`:
   - `localization_surface.csv` - dense (slant range x pitch) grid, median error per cell (sim)
   - `mission_contacts.csv` - the demo mission's real contacts (lat/lon/R95/class)
   - `coverage_matrix.csv` - the 8-row calibration matrix (sim, seed 0)

## Run

```bash
cd docs/documentation/wolfram
wolframscript -file error_surface_3d.wl          # -> ../figures/hero-loc-error-surface.png
wolframscript -file survivor_map_geo.wl          # -> ../figures/hero-survivor-map.png
wolframscript -file coverage_calibration_3d.wl   # -> ../figures/hero-coverage-3d.png
```

`survivor_map_geo.wl` fetches map tiles over the network for its basemap. That is a
documentation-build step, not the on-device mission loop, so it does not violate the
offline-at-runtime rule (same class as pre-downloading map tiles before a mission).

## What each renders

| Script | Output | Reads | Honesty tag |
| --- | --- | --- | --- |
| `error_surface_3d.wl` | `hero-loc-error-surface.png` | `localization_surface.csv` | (sim) - calibrated synthetic simulator; real-flight pending |
| `survivor_map_geo.wl` | `hero-survivor-map.png` | `mission_contacts.csv` | real Fuser output, scene synthetic, median err 1.1 m |
| `coverage_calibration_3d.wl` | `hero-coverage-3d.png` | `coverage_matrix.csv` | (sim) - matched ~95%, time-sync collapse is the headline |

## After running

The README (`README.md`) and the in-app docs page reference these three PNGs by their
`hero-*.png` names. Once you drop them into `../figures/`, both surfaces show them with no
further wiring. Until then, those slots show a "Wolfram hero visual (run the script)"
placeholder so the docs never display a broken image.
