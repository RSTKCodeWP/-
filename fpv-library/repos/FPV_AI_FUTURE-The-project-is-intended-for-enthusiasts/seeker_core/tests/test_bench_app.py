"""Bench-app tests — the runnable real-time loop drives the assembled head end to end (in sim)."""
from __future__ import annotations

from seeker_core.adapters import RecordActuatorSink, SimCameraSource
from seeker_core.bench_app import SimImu, run
from seeker_core.contracts import ActuatorChannel, OperatorButton, OperatorCommand


def _none():
    return OperatorCommand(OperatorButton.NONE, None, 0)


def _commit():
    return OperatorCommand(OperatorButton.COMMIT, b"sig", 0)


def test_bench_app_sim_runs_head_and_tracks():
    sink = RecordActuatorSink()
    n, last = run(SimCameraSource(), SimImu(), sink, _none, ticks=60)
    assert n == 60 and last is not None and last.track.locked
    assert last.actuators.by_channel(ActuatorChannel.GIMBAL_AZ) is not None            # gimbal aiming
    assert last.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE).value == 0.0   # no commit -> neutral
    assert len(sink.frames) == 60


def test_bench_app_sim_commit_steers():
    n, last = run(SimCameraSource(), SimImu(), None, _commit, ticks=60)
    assert last is not None and last.authority.committed
    assert last.actuators.by_channel(ActuatorChannel.AIRFRAME_THROTTLE).value > 0.0
