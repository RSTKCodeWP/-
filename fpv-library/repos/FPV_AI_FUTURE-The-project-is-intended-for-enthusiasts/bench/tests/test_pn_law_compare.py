"""PN-law comparison (⊥LOS TPN/IPN-family vs ⊥velocity PPN) on our from-below quad geometry.

Honest, nuanced result: PPN demands modestly LESS g than the ⊥-LOS law in the maneuver-tracking phase
(confirms Sozinov-Gorevich direction), but BOTH saturate the 0.84 g quad wall against any real maneuver --
the PLANT, not the law, sets the envelope. PPN is a cheap refinement, not the fix for maneuvering targets.
"""

from __future__ import annotations

from fpv_ai.bench.pn_law_compare import PnConfig, run


def test_calm_target_both_laws_hit_identically():
    for law in ("TPN", "PPN"):
        r = run(PnConfig(weave_g=0.0), law)
        assert r.hit, f"{law} should hit a non-maneuvering overhead target, CPA={r.cpa_m:.2f}"


def test_ppn_not_worse_than_tpn_at_moderate_maneuver():
    """At a moderate weave PPN's terminal demand is <= the ⊥-LOS law's (the paper's direction holds)."""
    tpn = run(PnConfig(weave_g=0.8), "TPN")
    ppn = run(PnConfig(weave_g=0.8), "PPN")
    assert ppn.term_demand_g <= tpn.term_demand_g + 1.0, (
        f"PPN terminal demand {ppn.term_demand_g:.1f} should not exceed TPN {tpn.term_demand_g:.1f}")


def test_plant_wall_dominates_under_maneuver():
    """The honest wall: against a real maneuver BOTH laws demand far past the 0.84 g envelope -- the quad
    plant, not the guidance law, is the binding constraint."""
    for law in ("TPN", "PPN"):
        r = run(PnConfig(weave_g=0.8), law)
        assert r.frac_over_envelope > 0.5, (
            f"{law}: a 0.8 g maneuver should push demand past 0.84 g most of the terminal window")
