"""A3: SpeedPolicy coupled to the lateral-g budget (hold a g-reserve)."""

from __future__ import annotations

from fpv.fpv_ai.control.speed import SpeedMode, SpeedPolicy


def test_g_budget_is_a_noop_when_omitted():
    pol = SpeedPolicy.default()
    base = pol.resolve_speed_mps(SpeedMode.ADAPTIVE_SPEED)
    same = pol.resolve_speed_mps(SpeedMode.ADAPTIVE_SPEED, required_g=None, achievable_g=None)
    assert same == base                                   # backward compatible


def test_demand_inside_reserve_does_not_slow():
    pol = SpeedPolicy.default()
    base = pol.resolve_speed_mps(SpeedMode.ADAPTIVE_SPEED)
    # required_g 0.3 well under (1-0.2)*0.84 = 0.672 -> no scaling
    keep = pol.resolve_speed_mps(SpeedMode.ADAPTIVE_SPEED, required_g=0.3, achievable_g=0.84)
    assert keep == base


def test_demand_into_reserve_slows_to_hold_reserve():
    pol = SpeedPolicy.default()
    base = pol.resolve_speed_mps(SpeedMode.ADAPTIVE_SPEED)        # 3.0
    reduced = pol.resolve_speed_mps(SpeedMode.ADAPTIVE_SPEED, required_g=0.8, achievable_g=0.84)
    assert reduced < base
    # the demand scales ~linearly with speed; after slowing, the implied demand sits at the
    # reserve boundary (1-0.2)*achievable, never above it.
    g_cap = (1.0 - 0.2) * 0.84
    implied_required_g = 0.8 * (reduced / base)
    assert implied_required_g <= g_cap + 1e-3


def test_higher_demand_slows_more():
    pol = SpeedPolicy.default()
    mild = pol.resolve_speed_mps(SpeedMode.FIXED_SPEED, required_g=0.75, achievable_g=0.84)
    hard = pol.resolve_speed_mps(SpeedMode.FIXED_SPEED, required_g=1.50, achievable_g=0.84)
    assert hard < mild < pol.resolve_speed_mps(SpeedMode.FIXED_SPEED)


def test_reserve_never_throttles_below_floor():
    pol = SpeedPolicy.default()
    # an absurd demand must not collapse speed below the profile minimum
    s = pol.resolve_speed_mps(SpeedMode.ADAPTIVE_SPEED, required_g=100.0, achievable_g=0.84)
    assert s >= pol.profile(SpeedMode.ADAPTIVE_SPEED).min_mps
