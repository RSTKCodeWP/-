"""Unit tests for nav quality gate (warmup, hold, FPS watchdog)."""

import time

from aerostab.quality_gate import GateInputs, GateState, flight_ok, step_gate


def _inp(**kwargs) -> GateInputs:
    defaults = dict(
        tracking_ok=True,
        nav_ready=True,
        armed=False,
        hold_last_on_drop=True,
        warmup_s=2.0,
        now=10.0,
        nav_valid_since=0.0,
        fps=20.0,
        camera_ok=True,
    )
    defaults.update(kwargs)
    return GateInputs(**defaults)


def test_warmup_blocks_nav_valid():
    g = GateState(nav_valid=False, holding=False, nav_valid_since=0.0, zero_fps_since=0.0)
    g = step_gate(g, _inp(now=1.0, nav_valid_since=0.0))
    assert g.nav_valid_since == 1.0
    assert not g.nav_valid
    g = step_gate(g, _inp(now=2.5, nav_valid_since=g.nav_valid_since))
    assert not g.nav_valid
    g = step_gate(g, _inp(now=3.1, nav_valid_since=g.nav_valid_since))
    assert g.nav_valid


def test_drop_while_armed_enters_hold():
    g = GateState(nav_valid=True, holding=False, nav_valid_since=5.0, zero_fps_since=0.0)
    g = step_gate(g, _inp(tracking_ok=False, armed=True, now=6.0, nav_valid_since=5.0))
    assert g.holding
    assert not g.nav_valid


def test_drop_while_disarmed_no_hold():
    g = GateState(nav_valid=True, holding=False, nav_valid_since=5.0, zero_fps_since=0.0)
    g = step_gate(g, _inp(tracking_ok=False, armed=False, now=6.0))
    assert not g.holding


def test_fps_watchdog_hold():
    g = GateState(nav_valid=True, holding=False, nav_valid_since=5.0, zero_fps_since=0.0)
    g = step_gate(g, _inp(armed=True, fps=0.0, now=10.0))
    assert g.zero_fps_since == 10.0
    g = step_gate(g, _inp(armed=True, fps=0.0, now=11.5))
    assert g.holding
    assert not g.nav_valid


def test_camera_fail_hold_while_armed():
    g = GateState(nav_valid=True, holding=False, nav_valid_since=5.0, zero_fps_since=0.0)
    g = step_gate(g, _inp(camera_ok=False, armed=True, now=6.0))
    assert g.holding
    assert not g.nav_valid


def test_flight_ok_preflight_vs_armed():
    assert flight_ok(health_ready=True, nav_valid=True, armed=False, holding=False)
    assert not flight_ok(health_ready=False, nav_valid=True, armed=False, holding=False)
    assert flight_ok(health_ready=True, nav_valid=True, armed=True, holding=False)
    assert not flight_ok(health_ready=True, nav_valid=True, armed=True, holding=True)
