"""False-confirmed-per-km² — the mission-meaningful FP budget (Task 3.7, design line 96).

A SAR coordinator's real question is "how many empty coordinates will I be dispatched to
per km² I search," not a per-minute rate: search effort scales with ground area covered,
not wall-clock. So the metric is `confirmed_false_positives / km²_swept`, distinct from
the per-frame flicker false-confirm rate (Task 3.6).

**Swept area is the UNION of the per-frame camera ground footprints** — overlapping frames
(the drone lingering / passing back over) must not double-count, or a slow careful sweep
would look like it covered more ground than it did and deflate the rate. Each footprint is
the image-corner quad projected to the ground (via the shared `geometry.ray_to_ground`,
done by the caller); here we work in a local ENU-meters frame. We rasterise the footprints
onto a fixed ground grid and count covered cells — a simple, deterministic union that needs
no polygon-clipping dependency. `cell_m` trades accuracy for cost; the metric reports it.
"""

from __future__ import annotations

from dataclasses import dataclass

_KM2_PER_M2 = 1e-6


@dataclass(frozen=True)
class FootprintQuad:
    """One frame's camera ground footprint: 4 corners in local ENU meters.

    Corners must trace the boundary in order (CW or CCW — either winding direction is
    fine), forming a SIMPLE (non-self-intersecting) quad. The ray-cast point-in-polygon
    test in `swept_area_km2` assumes boundary order; a crossed/bow-tie corner order would
    silently mis-measure the covered area. A real camera footprint (4 image corners
    projected to the ground) is always a simple quad, so this holds for the metric's
    intended input.
    """

    corners: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.corners) != 4:
            raise ValueError(f"FootprintQuad needs exactly 4 corners, got {len(self.corners)}")


def _point_in_quad(px: float, py: float, quad: FootprintQuad) -> bool:
    """Ray-cast point-in-polygon for a 4-corner quad (handles convex and concave)."""
    corners = quad.corners
    inside = False
    n = len(corners)
    j = n - 1
    for i in range(n):
        xi, yi = corners[i]
        xj, yj = corners[j]
        # Does a horizontal ray from (px, py) cross edge (i, j)?
        if (yi > py) != (yj > py):
            x_cross = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def swept_area_km2(footprints: list[FootprintQuad], cell_m: float = 5.0) -> float:
    """Union area (km²) swept by the footprints, via grid rasterisation.

    Returns 0.0 for no footprints (no ground swept). `cell_m` is the grid resolution in
    meters; smaller is more accurate and slower. A cell counts as swept if its center lies
    inside ANY footprint — the union, so overlap never double-counts.
    """
    if not footprints:
        return 0.0

    # Bounding box over all corners → the grid extent.
    xs = [x for fp in footprints for (x, _y) in fp.corners]
    ys = [y for fp in footprints for (_x, y) in fp.corners]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    cell_area_m2 = cell_m * cell_m
    nx = max(1, int((max_x - min_x) / cell_m) + 1)
    ny = max(1, int((max_y - min_y) / cell_m) + 1)

    covered = 0
    for iy in range(ny):
        cy = min_y + (iy + 0.5) * cell_m  # cell center
        for ix in range(nx):
            cx = min_x + (ix + 0.5) * cell_m
            if any(_point_in_quad(cx, cy, fp) for fp in footprints):
                covered += 1

    return covered * cell_area_m2 * _KM2_PER_M2


def false_confirms_per_km2(
    n_false_confirms: int, footprints: list[FootprintQuad], cell_m: float = 5.0
) -> float:
    """Confirmed false positives per km² swept.

    Returns `nan` when nothing was swept (the rate is undefined — never a ZeroDivisionError
    and never a misleading 0.0, which would read as "perfectly clean"). 0 false confirms
    over a real sweep is a true 0.0.
    """
    area = swept_area_km2(footprints, cell_m=cell_m)
    if area <= 0.0:
        return float("nan")
    return n_false_confirms / area
