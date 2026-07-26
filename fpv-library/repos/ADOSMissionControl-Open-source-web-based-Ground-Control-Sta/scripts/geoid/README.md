# EGM96 geoid grid — bundled asset

Generates `public/geoid/egm96-1deg.i16.gz`, the bundled geoid-undulation grid the
GCS uses to convert MSL/AMSL altitudes to WGS-84 ellipsoidal height for Cesium
placement (`src/lib/terrain/geoid.ts`).

## Source data (public domain)

`WW15MGH.GRD` — the NGA/NASA EGM96 world-wide 15-arc-minute gridded geoid heights.
This dataset is a US Government work and is in the **public domain**.

Download the interpolation package (a ZIP containing `WW15MGH.GRD` plus the
FORTRAN interpolator and its official test vectors) from NGA:

```
https://earth-info.nga.mil/php/download.php?file=egm-96interpolation
```

EGM96 landing page (background + the same file set):
`https://earth-info.nga.mil/index.php?dir=wgs84&action=egm96-geoid-heights`

Unzip it and keep `WW15MGH.GRD` (~9.7 MB ASCII).

## Regenerate

```
node scripts/geoid/generate.mjs path/to/WW15MGH.GRD
```

If `WW15MGH.GRD` sits next to this script or at the repo root, the path argument
can be omitted. The script rewrites `public/geoid/egm96-1deg.i16.gz`.

## Format

- **Source:** `WW15MGH.GRD`, 721 rows x 1441 cols at 0.25 deg, ASCII metres,
  ordered NORTH (+90 deg) -> SOUTH (-90 deg), WEST (0 deg) -> EAST (360 deg).
- **Output:** `egm96-1deg.i16.gz` — gzip of a raw **Int16, little-endian,
  centimetre** array.
  - Grid: **361 columns** (longitude 0..360 deg inclusive) x **181 rows**
    (latitude +90..-90 deg inclusive), **1 deg** resolution.
  - **Row-major, corner origin at (+90 deg, 0 deg):** index `row * 361 + col`,
    where `row` runs 0 (+90 deg) .. 180 (-90 deg) and `col` runs 0 (0 deg) ..
    360 (360 deg). Column 360 duplicates column 0 (longitude wrap).
  - Value = round(undulation_metres * 100), clamped to Int16 range.
  - Uncompressed size = 361 * 181 * 2 = 130,682 bytes.

The subsample keeps every 4th source cell (0.25 deg -> 1 deg). Bilinear
interpolation of the 1 deg output matches the six official `WW15MGH.GRD` test
points (`input.dat` / `outintpt.dat`) within ~0.5 m — enough to place a path
correctly on terrain, and it pins the sign (`h = MSL + N`, not `- N`).
