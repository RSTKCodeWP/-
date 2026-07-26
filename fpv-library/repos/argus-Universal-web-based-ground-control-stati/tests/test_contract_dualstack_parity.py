"""Contract: for every semantic operation implemented on BOTH stacks, the
TypeScript WebSerial path and the Python backend path must emit MAVLink
frames that decode to identical fields.

Why this exists: the two stacks were previously kept in sync by two
hand-maintained expectation mirrors — transport.dispatch.test.ts asserted
"what the backend would send" and test_contract_pymavlink.py asserted "what
the operator asked for". Both can pass while the stacks drift (each mirror is
updated by a human who has to remember the other side). This harness removes
the human middle layer: the SAME inputs (tests/fixtures/parity_ops.json) are
run through the real production code of both stacks and the resulting frames
are machine-compared, with pymavlink as the decoding oracle. pymavlink parsing
also CRC-validates every frontend frame — stronger than the offset-peeking
decoder in transport.dispatch.test.ts.

How it works:
  1. `npx vitest run src/lib/transport.parity.test.ts` (once per module) drives
     transport.dispatch() / the upload state machines against a mocked serial
     port and dumps every emitted frame as hex, keyed by op id.
  2. Each op's inputs are replayed through backend commands.execute() on a
     FakeLink; upload handshakes are driven by feeding pymavlink-encoded
     MISSION_REQUEST_INT / MISSION_ACK frames to the real handlers.
  3. Frames are compared field-by-field (seq and GCS source ids are frame
     header, not message semantics — see test_gcs_identity_pinned).

Known intentional differences are NOT hidden: `pinned_divergence` ops assert
today's exact behavior on each side, so both a silent fix and a new drift
show up as a failing test that forces an explicit decision.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from test_contract_pymavlink import FakeLink, _decode_one, _encode_payload

from backend import commands
from backend.commands import send_heartbeat
from backend.config import cfg
from backend.mavlink_handlers import handle_mission_ack, handle_mission_request
from backend.param_manager import ParamManager

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "parity_ops.json").read_text(encoding="utf-8"))
OPS = {op["id"]: op for op in FIXTURE["ops"]}


# ─────────────────────────────────────────────────────────────────────────
# Frontend dump (vitest, once per module)
# ─────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def serial_dump(tmp_path_factory) -> dict[str, list[str]]:
    # Skip ONLY when the toolchain is genuinely absent (backend-only checkout).
    # A present-but-broken dump must FAIL, not skip: CI installs node_modules
    # before pytest (ci.yml), so a skip there would silently disable the whole
    # parity contract exactly when it has something to say. `node vitest.mjs`
    # instead of `npx vitest` keeps this hermetic (no network install) and
    # works on Windows checkouts, where the .bin shims aren't exec()able.
    vitest_mjs = ROOT / "node_modules" / "vitest" / "vitest.mjs"
    node = shutil.which("node")
    if node is None or not vitest_mjs.exists():
        pytest.skip("node/vitest not installed — cannot run the TS wire dump")
    out = tmp_path_factory.mktemp("parity") / "dump.json"
    env = {**os.environ, "PARITY_DUMP_PATH": str(out)}
    result = subprocess.run(
        [node, str(vitest_mjs), "run", "src/lib/transport.parity.test.ts"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=180, env=env,
    )
    if result.returncode != 0 or not out.exists():
        pytest.fail(f"vitest wire dump failed:\n{(result.stderr or result.stdout)[-1500:]}")
    return json.loads(out.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────
# Backend capture
# ─────────────────────────────────────────────────────────────────────────


def _drive_upload(link: FakeLink, mission_type: int) -> None:
    """Play the FC side of an upload: request every item, then ACK."""
    count_msg = _decode_one(link.captured[0])
    assert count_msg.get_msgId() == 44, f"upload did not start with MISSION_COUNT: {count_msg}"
    for seq in range(count_msg.count):
        req = mavlink.MAVLink_mission_request_int_message(
            target_system=255, target_component=1, seq=seq, mission_type=mission_type,
        )
        payload, pl = _encode_payload(req)
        handle_mission_request(payload, pl, link)
    ack = mavlink.MAVLink_mission_ack_message(
        target_system=255, target_component=1, type=0, mission_type=mission_type,
    )
    payload, pl = _encode_payload(ack)
    handle_mission_ack(payload, pl, link)


def _backend_frames(op: dict) -> list[bytes]:
    link = FakeLink()
    link.param_mgr = ParamManager(link)
    if op.get("plane"):
        link.is_plane = lambda: True
    kind = op["kind"]

    if kind == "boot_heartbeat":
        send_heartbeat(link)
    elif kind == "dispatch":
        result = commands.execute(op["op"], op.get("param"), link, op.get("data"))
        if op["expect"] == "parity":
            assert not (isinstance(result, dict) and result.get("ok") is False), (
                f"backend rejected parity op {op['id']}: {result}"
            )
        if op.get("flush_timer_ms"):
            # cmd_mission_start defers MAV_CMD_MISSION_START via threading.Timer
            # (cfg.MISSION_START_DELAY, patched short by the caller). Poll instead
            # of a blind sleep so a slow CI box doesn't race the timer thread.
            deadline = time.time() + 2.0
            while len(link.captured) < 2 and time.time() < deadline:
                time.sleep(0.01)
    elif kind == "log_list":
        commands.execute("log_list", None, link, {})
    elif kind == "log_download":
        entry = op["log_entry"]
        link.log_dl._log_list = [{"id": entry["id"], "size": entry["size"], "time_utc": 0}]
        commands.execute("log_download", None, link, {"id": entry["id"]})
    elif kind == "mission_download":
        commands.execute("mission_download", None, link, {})
    elif kind == "mission_upload":
        commands.execute(
            "mission_upload", None, link,
            {"waypoints": FIXTURE["golden_waypoints"], "takeoff_alt": FIXTURE["golden_takeoff_alt"]},
        )
        _drive_upload(link, mission_type=0)
    elif kind == "fence_upload":
        commands.execute("fence_upload", None, link, {"polygon": FIXTURE["fence_polygon"]})
        _drive_upload(link, mission_type=1)
    else:
        pytest.fail(f"unknown op kind: {kind}")
    return link.captured


@pytest.fixture(autouse=True)
def _short_mission_start_delay(monkeypatch):
    monkeypatch.setattr(cfg, "MISSION_START_DELAY", 0.02)


# ─────────────────────────────────────────────────────────────────────────
# Comparison
# ─────────────────────────────────────────────────────────────────────────


def _decode_fields(frame: bytes) -> dict:
    msg = _decode_one(frame)
    fields = {"_type": msg.get_type()}
    for name in msg.get_fieldnames():
        fields[name] = getattr(msg, name)
    return fields


def _assert_frame_equal(op_id: str, idx: int, be: dict, fe: dict) -> None:
    assert be["_type"] == fe["_type"], (
        f"{op_id}[{idx}]: backend sent {be['_type']}, serial sent {fe['_type']}"
    )
    for key, bv in be.items():
        fv = fe[key]
        if isinstance(bv, float) or isinstance(fv, float):
            if isinstance(bv, float) and isinstance(fv, float) and math.isnan(bv) and math.isnan(fv):
                continue
            assert bv == pytest.approx(fv, rel=1e-6, abs=1e-6), (
                f"{op_id}[{idx}] field '{key}': backend={bv} serial={fv}"
            )
        else:
            assert bv == fv, f"{op_id}[{idx}] field '{key}': backend={bv!r} serial={fv!r}"


def _ids(expect: str) -> list[str]:
    return [op["id"] for op in FIXTURE["ops"] if op["expect"] == expect]


class TestDualStackParity:
    @pytest.mark.parametrize("op_id", _ids("parity"))
    def test_parity(self, op_id: str, serial_dump: dict):
        op = OPS[op_id]
        be_frames = [_decode_fields(f) for f in _backend_frames(op)]
        fe_frames = [_decode_fields(bytes.fromhex(h)) for h in serial_dump[op_id]]
        assert len(be_frames) == len(fe_frames), (
            f"{op_id}: backend sent {len(be_frames)} frames "
            f"({[f['_type'] for f in be_frames]}), serial sent {len(fe_frames)} "
            f"({[f['_type'] for f in fe_frames]})"
        )
        for i, (be, fe) in enumerate(zip(be_frames, fe_frames, strict=True)):
            _assert_frame_equal(op_id, i, be, fe)

    @pytest.mark.parametrize("op_id", _ids("both_drop"))
    def test_both_drop(self, op_id: str, serial_dump: dict):
        op = OPS[op_id]
        # A typo'd op name would also produce zero frames on both sides —
        # reject it so both_drop can't pass vacuously. (The vitest dump makes
        # the same check against _serialDispatch via hasSerialHandler.)
        assert op["op"] in commands._DISPATCH, f"{op_id}: unknown backend command {op['op']!r}"
        assert _backend_frames(op) == [], f"{op_id}: backend sent frames for invalid input"
        assert serial_dump[op_id] == [], f"{op_id}: serial sent frames for invalid input"

    @pytest.mark.parametrize("op_id", _ids("pinned_divergence"))
    def test_pinned_divergence(self, op_id: str, serial_dump: dict):
        """These ops behave DIFFERENTLY on the two stacks today (validation
        policy divergence, found 2026-07-14 when this harness was built). The
        pin asserts the exact current behavior of BOTH sides: if either side
        changes — including a fix that aligns them — this fails and the op
        must be re-classified (usually to expect=parity or both_drop)."""
        op = OPS[op_id]
        be_n = len(_backend_frames(op))
        fe_n = len(serial_dump[op_id])
        assert be_n == op["backend_frames"], (
            f"{op_id}: backend now sends {be_n} frames (pinned {op['backend_frames']})"
        )
        assert fe_n == op["serial_frames"], (
            f"{op_id}: serial now sends {fe_n} frames (pinned {op['serial_frames']})"
        )

    def test_gcs_identity_pinned(self, serial_dump: dict):
        """GCS source ids differ by design: backend frames carry (sysid 255,
        compid 1) — bm() defaults in backend/pllink_proto.py:57 — while the
        WebSerial path stamps (255, 190 = MAV_COMP_ID_MISSIONPLANNER) in
        transport.ts sendSerialFrame. Both are valid GCS identities and both
        are field-proven against ArduPilot; accel-cal sender matching (see
        cmd_cal_accel_next) makes a silent identity change dangerous, so pin
        the values instead of forcing them equal."""
        be = _backend_frames(OPS["arm"])
        assert (be[0][5], be[0][6]) == (255, 1)
        fe = bytes.fromhex(serial_dump["arm"][0])
        assert (fe[5], fe[6]) == (255, 190)

    def test_fixture_dump_coverage(self, serial_dump: dict):
        missing = [op["id"] for op in FIXTURE["ops"] if op["id"] not in serial_dump]
        assert not missing, f"vitest dump lacks ops: {missing}"
