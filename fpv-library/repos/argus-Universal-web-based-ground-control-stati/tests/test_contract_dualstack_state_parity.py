"""Contract: an FC frame must land in app.drone with the same values on both
transports — the decode-direction twin of test_contract_dualstack_parity.py.

Path under test on each side (full production code, no reimplementation):
  backend:  handle_<msg>() on a real DroneLink → get_state() — the exact dict
            the ws push delivers, which updateState() Object.assigns onto
            app.drone (stores.svelte.ts:59)
  serial:   parseFrames → dispatchFrame → buildSerialHandlers → app.drone
            (dumped by src/lib/serialHandlers.parity.test.ts)

The frames in tests/fixtures/parity_frames.json are canonical input vectors
generated once with pymavlink (the oracle encoder); this test re-validates
each hex still parses to the named message before use. Probes include the
divergence-prone spots: negative yaw (backend normalizes to 0..360),
southern/western-hemisphere signs, NED vz sign flip, and the UINT16_MAX / -1
"value unknown" sentinels.

Tolerances exist only to absorb get_state()'s display rounding (round(x, n))
— the serial path delivers unrounded values by design. A divergence larger
than the rounding quantum is a real drift.

Found and fixed while building this (2026-07-14): serial yaw was signed
(-90 vs 270 for west), VFR_HUD airspeed/climb/throttle never reached the
serial-mode PFD, and serial kept 18 RC channels vs the backend's 16.
STATUSTEXT is intentionally untested here (backend applies filtering+locale).
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink

from backend import mavlink_dispatch
from backend.drone_link import DroneLink

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "parity_frames.json").read_text(encoding="utf-8"))
FRAMES = {f["id"]: f for f in FIXTURE["frames"]}

# Absolute tolerances sized to get_state()'s rounding quantum (half step + slack).
_TOL = {
    "roll": 0.06, "pitch": 0.06, "yaw": 0.06,
    "lat": 6e-8, "lon": 6e-8, "home_lat": 6e-8, "home_lon": 6e-8,
    "alt_msl": 0.06, "alt_rel": 0.06, "vz": 0.06,
    "hdg": 0.51,
    "voltage": 0.006, "current": 0.006,
    "airspeed": 0.06, "climb": 0.06,
    "vibe": 0.06,
}


@pytest.fixture(scope="module")
def state_dump(tmp_path_factory) -> dict[str, dict]:
    # Same skip/fail split as test_contract_dualstack_parity.serial_dump:
    # skip only for a genuinely toolchain-less checkout, fail on breakage.
    vitest_mjs = ROOT / "node_modules" / "vitest" / "vitest.mjs"
    node = shutil.which("node")
    if node is None or not vitest_mjs.exists():
        pytest.skip("node/vitest not installed — cannot run the TS state dump")
    out = tmp_path_factory.mktemp("state_parity") / "dump.json"
    env = {**os.environ, "PARITY_STATE_DUMP_PATH": str(out)}
    result = subprocess.run(
        [node, str(vitest_mjs), "run", "src/lib/serialHandlers.parity.test.ts"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=180, env=env,
    )
    if result.returncode != 0 or not out.exists():
        pytest.fail(f"vitest state dump failed:\n{(result.stderr or result.stdout)[-1500:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def _backend_state(spec: dict) -> dict:
    frame = bytes.fromhex(spec["hex"])
    mid = frame[7] | (frame[8] << 8) | (frame[9] << 16)
    pl = frame[1]
    # Exact trimmed payload, like production _process — NOT zero-padded. Four
    # fixture frames arrive MAVLink2-trimmed; padding here would hide a
    # handler that forgot its _pad() call.
    payload = frame[10 : 10 + pl]
    link = DroneLink()  # constructing it registers the production dispatch table
    link.locale = "en"  # get_state "mode" is localized; TS dump runs en
    link._raw_sysid = 1  # heartbeat handler copies the frame's sysid from here
    # Resolve through the REAL registry, not a hand-copied handler map that
    # could go stale against init_handlers().
    handler = mavlink_dispatch._handlers.get(mid)
    assert handler is not None, f"{spec['id']}: msg id {mid} not in production dispatch registry"
    handler(payload, pl, link)
    return link.get_state()


def _assert_value(op_id: str, key: str, bv, tv, tol=None) -> None:
    if tol is None:
        tol = _TOL.get(key)
    if isinstance(bv, list) or isinstance(tv, list):
        assert isinstance(bv, list) and isinstance(tv, list) and len(bv) == len(tv), (
            f"{op_id}.{key}: backend={bv!r} serial={tv!r}"
        )
        for i, (b, s) in enumerate(zip(bv, tv, strict=True)):
            # Elements inherit the list key's tolerance (vibe rounds to 0.1).
            _assert_value(op_id, f"{key}[{i}]", b, s, tol)
    elif tol is not None:
        assert not (isinstance(bv, float) and math.isnan(bv)), f"{op_id}.{key}: backend NaN"
        assert bv == pytest.approx(tv, abs=tol), (
            f"{op_id}.{key}: backend(ws)={bv} serial={tv} (tol {tol})"
        )
    else:
        assert bv == tv, f"{op_id}.{key}: backend(ws)={bv!r} serial={tv!r}"


class TestDualStackStateParity:
    @pytest.mark.parametrize("frame_id", list(FRAMES))
    def test_fixture_frame_is_valid_mavlink(self, frame_id: str):
        """Regeneration guard: every checked-in hex must still parse (via the
        pymavlink oracle) to the message name it claims."""
        spec = FRAMES[frame_id]
        parser = mavlink.MAVLink(None)
        parser.robust_parsing = True
        msgs = parser.parse_buffer(bytes.fromhex(spec["hex"]))
        assert msgs and msgs[0].get_type() == spec["msg"], (
            f"{frame_id}: fixture hex no longer decodes as {spec['msg']}"
        )

    @pytest.mark.parametrize("frame_id", list(FRAMES))
    def test_state_parity(self, frame_id: str, state_dump: dict):
        spec = FRAMES[frame_id]
        be = _backend_state(spec)
        ts = state_dump[frame_id]
        # The vibe key's tolerance applies element-wise; strip get_state's
        # extra keys — only the fields the serial path also surfaces count.
        for key in spec["compare"]:
            assert key in be, f"{frame_id}: get_state() has no key {key!r}"
            assert key in ts, f"{frame_id}: serial dump has no key {key!r}"
            _assert_value(frame_id, key, be[key], ts[key])

    def test_dump_covers_fixture(self, state_dump: dict):
        missing = [f["id"] for f in FIXTURE["frames"] if f["id"] not in state_dump]
        assert not missing, f"state dump lacks frames: {missing}"
