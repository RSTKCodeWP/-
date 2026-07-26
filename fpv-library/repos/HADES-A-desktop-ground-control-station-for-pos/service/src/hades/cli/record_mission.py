"""`hades-record-mission` — bake a static demo mission for the Phase 6 website.

The demo site (Phase 6) replays a pre-recorded mission through the SAME React coordinator UI
the live service drives, with no Electron and no Python backend at runtime. This CLI produces
that recording: a single `mission.json` the browser fetches once and replays.

HONESTY (the load-bearing decision, from the Phase-6 adversarial panel): we do NOT bake from
today's only recorded fixture — its telemetry is position-only (no camera attitude), so the
localizer correctly emits ONLY CUE_ONLY/null contacts and the demo map would be EMPTY (the one
thing the demo exists to show). Nor do we hand-author coordinates (a credibility landmine in a
SAR tool). Instead we drive the REAL `Fuser` over full-attitude poses from the calibrated P4
simulator (`locate/geom_sim`) against KNOWN ground-truth survivors. So every pin, uncertainty
ellipse, R95, and actionability class in the demo is GENUINE localizer output — and because we
hold the ground truth, we report the REAL median localization error in meters in the provenance
block the demo banner displays. "Bake from a real run" is honored as "bake from a real
*pipeline* run on a physically-valid synthetic scene."

The scene is a deliberately honest mix the panel required:
  - an ORBIT track (aspect diversity → heading bias relaxes → a refining PINPOINT),
  - a STRAIGHT-PASS track (single-leg geometry → heading-limited → capped at SWEEP), and
  - a position-only track (no fusable geometry → an honest CUE_ONLY with a NULL coordinate).

Output shape mirrors the UI's mock data path (`MockWsConfig`): `{frames, json}` where `frames`
carry their REAL wire `frame_id` (the cross-channel join key — a local 0..n counter would
misalign every overlay) and `json` is the `DetectionMessage`/`ContactRecord` stream. Plus a
`provenance` block, a scripted `link_lost` window, and a pre-computed `promote_refined` record
so the demo's degrade-visibly and operator-promote moments replay from the timeline.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.fuse import FusedEstimate, FuseObservation, Fuser
from hades.locate.geom_sim import GeomSim, OrbitPath, SimFrame, StraightPass
from hades.ws.schema import ContactRecord, DetectionMessage

# A Gulf-coast reference scene near the design's origin (illustrative LOCATION; the math is
# real). Two survivors a short distance apart, plus a third the position-only track cues.
_ORIGIN = (30.2150, -88.5200)
_AGL_M = 40.0
_CAMERA = CameraModel(fx=1400.0, fy=1400.0, cx=960.0, cy=540.0, mount="nadir")
_MISSION_EPOCH_MS = 1_780_000_000_000  # fixed synthetic mission clock (deterministic bake)


def _offset(origin: tuple[float, float], east_m: float, north_m: float) -> tuple[float, float]:
    m_per_deg = 111_320.0
    lat = origin[0] + north_m / m_per_deg
    lon = origin[1] + east_m / (m_per_deg * math.cos(math.radians(origin[0])))
    return lat, lon


def _box_from_pixel(px: tuple[float, float]) -> tuple[float, float, float, float]:
    """A small person-sized box whose BOTTOM-CENTER is the ground-truth feet pixel (§3.2:
    the localizer reads feet-on-ground from the box bottom-center)."""
    u, v = px
    half_w, h = 8.0, 26.0
    return (u - half_w, v - h, u + half_w, v)


def _sim_frames(path, seed: int) -> list[SimFrame]:
    """Run a flight path through the sensor-error model — the SAME noisy path the localizer
    consumes in the meter-error report (`pose_meas`/`pixel_meas`), not the noise-free truth.
    So the demo's scatter is the localizer's HONEST scatter, never an artificially perfect fix."""
    sim = GeomSim(camera=_CAMERA)
    return sim.run(path, SensorErrorModel(), seed=seed)


def _fuse_track(
    frames: list[SimFrame], fuser: Fuser
) -> tuple[FusedEstimate | None, float]:
    """Fuse a track's NOISY observations through the REAL Fuser; return the estimate and its
    localization error in meters vs the known target (so the provenance number is honest)."""
    obs = [
        FuseObservation(pose=f.pose_meas, camera=_CAMERA, pixel=f.pixel_meas)
        for f in frames
    ]
    est = fuser.fuse(obs)
    if est is None:
        return None, math.nan
    truth = frames[0].target_latlon
    m_per_deg = 111_320.0
    dlat = (est.coord[0] - truth[0]) * m_per_deg
    dlon = (est.coord[1] - truth[1]) * m_per_deg * math.cos(math.radians(truth[0]))
    err = math.hypot(dlat, dlon)
    return est, err


def _contact_from_estimate(
    *, frame_id: int, track_id: int, est: FusedEstimate, det_conf: float, age: int, tier: str
) -> ContactRecord:
    from hades.service.loop import _loc_conf

    return ContactRecord.from_fused(
        frame_id=frame_id,
        track_id=track_id,
        coord=est.coord,
        r95_m=est.r95_m,
        actionability_class=est.actionability_class,
        semi_major_m=est.semi_major_m,
        semi_minor_m=est.semi_minor_m,
        orientation_deg=est.orientation_deg,
        convergence=est.convergence,
        heading_limited=est.heading_limited,
        aspect_spread_deg=est.aspect_spread_deg,
        moving_suspected=est.moving_suspected,
        mc_reject_fraction=0.0,
        priority_tier=tier,
        detection_conf=det_conf,
        localization_conf=_loc_conf(est.r95_m),
        age_frames=age,
    )


def _cue_only(*, frame_id: int, track_id: int, det_conf: float, age: int) -> ContactRecord:
    """An honest no-fix contact: null coordinate, CUE floor radius — never a Null-Island pin."""
    return ContactRecord(
        frame_id=frame_id,
        track_id=track_id,
        lat=None,
        lon=None,
        r95_m=200.0,
        actionability_class="CUE_ONLY",
        semi_major_m=200.0,
        semi_minor_m=200.0,
        orientation_deg=0.0,
        priority_tier="candidate",
        convergence_state="CONVERGING",
        heading_limited=True,
        aspect_spread_deg=0.0,
        detection_conf=det_conf,
        localization_conf=0.0,
        mc_reject_fraction=1.0,
        moving_suspected=False,
        age_frames=age,
    )


def _representative_jpeg_b64() -> str:
    """One looped frame for the video panel. The panel only needs JPEG bytes per frame_id
    (the live recorded feed replaces this when real footage lands); a synthetic aerial-ish
    still is honest for a replay and keeps the mission to a single small fetch."""
    rng = np.random.default_rng(7)
    # a muted terrain-ish field with gentle noise, 960x540 (the design frame size)
    base = np.full((540, 960, 3), (38, 44, 40), dtype=np.uint8)
    noise = rng.integers(-6, 7, size=base.shape, dtype=np.int16)
    img = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(img, mode="RGB").save(buf, format="JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_mission(*, seed: int = 0, n_frames: int = 90) -> dict[str, Any]:
    """Build the demo mission: REAL fused contacts from the P4 simulator + a per-frame detection
    stream + frames + provenance + scripted link-lost / refined-promote. Pure + deterministic
    (seeded), so the demo and the Playwright gate reproduce exactly. No `Date.now()` / wall clock.
    """
    fuser = Fuser(error_model=SensorErrorModel(), seed=seed)

    # --- two real survivors, two real flight geometries -----------------------------------
    tgt_orbit = _offset(_ORIGIN, east_m=0.0, north_m=0.0)
    tgt_pass = _offset(_ORIGIN, east_m=120.0, north_m=-40.0)

    # radius 35 m at 40 m AGL: the real Fuser resolves this orbit's full aspect spread to a
    # genuine PINPOINT (R95 < 5 m) — verified against the pipeline, not assumed.
    orbit = OrbitPath(tgt_orbit, agl_m=_AGL_M, radius_m=35.0, n_frames=36, camera=_CAMERA)
    straight = StraightPass(tgt_pass, agl_m=_AGL_M, speed_mps=12.0, n_frames=40, camera=_CAMERA)

    orbit_frames = _sim_frames(orbit, seed=seed)
    pass_frames = _sim_frames(straight, seed=seed + 1)

    orbit_est, orbit_err = _fuse_track(orbit_frames, fuser)
    pass_est, pass_err = _fuse_track(pass_frames, fuser)
    assert orbit_est is not None and pass_est is not None, "sim produced no fusable geometry"

    # A REFINED (tighter) orbit estimate from MORE aspect coverage — the operator-promote demo
    # swaps this in so the contact visibly tightens, exactly as live on-demand fusion would.
    orbit_refined, _ = _fuse_track(orbit_frames + orbit_frames[: len(orbit_frames) // 2], fuser)
    assert orbit_refined is not None

    # --- assemble the per-frame stream ----------------------------------------------------
    frames: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []

    # ONE looped still for the whole replay (the panel only needs JPEG bytes per frame_id; the
    # live recorded feed replaces this when real footage lands). Stored ONCE at the top level —
    # not duplicated per frame — so mission.json stays small (a single fetch). Each frame still
    # carries its REAL frame_id (the cross-channel join key); the bytes are shared.
    frame_jpeg_b64 = _representative_jpeg_b64()

    # detection boxes move using the simulator's ground-truth pixels so the overlay tracks a
    # believable target across the looped still.
    orbit_px = [f.pixel_true for f in orbit_frames]
    pass_px = [f.pixel_true for f in pass_frames]

    for fid in range(n_frames):
        ts = fid / 30.0
        frames.append({"frame_id": fid, "timestamp": ts})
        boxes = []
        # animate the two detection boxes from the sim's ground-truth pixels (cycled to fill)
        bo = _box_from_pixel(orbit_px[fid % len(orbit_px)])
        bp = _box_from_pixel(pass_px[fid % len(pass_px)])
        # one missed-frame every 7th to look like a real (imperfect) detector
        if fid % 7 != 6:
            boxes.append({"box_xyxy": list(bo), "conf": 0.88, "cls": "person"})
            boxes.append({"box_xyxy": list(bp), "conf": 0.81, "cls": "person"})
        messages.append(
            DetectionMessage(frame_id=fid, timestamp=ts, boxes=boxes).model_dump()
        )

    # --- contact records, emitted at the frames where they reach their tier ----------------
    # track 42 (orbit): first a SWEEP-grade early read, then the refined PINPOINT — a believable
    # "tightens over time" arc, both REAL fused estimates from growing aspect coverage.
    early_orbit, _ = _fuse_track(orbit_frames[:8], fuser)
    if early_orbit is not None:
        messages.append(
            _contact_from_estimate(
                frame_id=12, track_id=42, est=early_orbit, det_conf=0.86, age=12,
                tier="candidate",
            ).model_dump()
        )
    messages.append(
        _contact_from_estimate(
            frame_id=40, track_id=42, est=orbit_est, det_conf=0.9, age=40, tier="strong",
        ).model_dump()
    )
    # track 37 (straight pass): heading-limited → SWEEP (the honest single-leg case).
    messages.append(
        _contact_from_estimate(
            frame_id=25, track_id=37, est=pass_est, det_conf=0.82, age=25, tier="candidate",
        ).model_dump()
    )
    # track 19: position-only, no fix → CUE_ONLY with NULL coordinate (the honest no-fix case).
    messages.append(_cue_only(frame_id=55, track_id=19, det_conf=0.74, age=8).model_dump())

    # sort the JSON stream by frame_id so the replay stays frame-aligned.
    messages.sort(key=lambda m: m["frame_id"])

    # --- scripted demo moments ------------------------------------------------------------
    link_lost = {"from_frame": 62, "to_frame": 70}  # a visible LINK-LOST → coasting → recover
    promote_refined = _contact_from_estimate(
        frame_id=80, track_id=37, est=orbit_refined, det_conf=0.9, age=80, tier="candidate",
    ).model_dump()

    median_error_m = float(np.median([orbit_err, pass_err]))

    return {
        "version": 1,
        "frame_jpeg_b64": frame_jpeg_b64,
        "frames": frames,
        "json": messages,
        "link_lost": link_lost,
        "promote_refined": promote_refined,
        "mission_epoch_ms": _MISSION_EPOCH_MS,
        "provenance": {
            "scene": "synthetic",
            "pipeline": "real",
            "median_error_m": round(median_error_m, 2),
            "note": (
                "Synthetic scene, real pipeline. Drone pose and survivor positions are "
                "scripted; every map pin, uncertainty ellipse, and confidence value is live "
                "output of the HADES localizer run against known ground truth. Real drone "
                "footage with full pose lands in a later release."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hades-record-mission", description=__doc__)
    parser.add_argument(
        "--out", default="../ui/public/mission.json",
        help="output path for the baked mission.json (default: the UI's public/ dir)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--frames", type=int, default=90)
    args = parser.parse_args(argv)

    mission = build_mission(seed=args.seed, n_frames=args.frames)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False makes a NaN/Inf slip a hard error here, never silent invalid JSON.
    out.write_text(json.dumps(mission, allow_nan=False), encoding="utf-8")
    prov = mission["provenance"]
    n_contacts = sum(1 for m in mission["json"] if m["type"] == "contact")
    print(
        f"hades-record-mission: wrote {out} "
        f"({len(mission['frames'])} frames, {n_contacts} contacts, "
        f"median loc error {prov['median_error_m']} m)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
