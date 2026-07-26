"""Localization: geometry, frame-gating, projection (DESIGN.md §3, Tasks 3.3-3.5, P4).

The ray→ground math (`geometry.ray_to_ground`) lives here ONCE and is imported by both
the Projector (Task 3.5) and the Fuse step (Phase 4) — never re-implemented (the
single-source-of-truth discipline that prevents the coordinate-convention divergence the
design fears). Frame-gating (Task 3.3) decides which frames are clean enough to feed the
fused estimate; the Projector (Task 3.5) turns each detection into a gated ground point.
"""
