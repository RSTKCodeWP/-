"""The optional AI-firewall discriminator gates engage-permission ONLY (never LOS/centroid)."""
import numpy as np

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import ft640_intrinsics


def _hot_frame():
    """A clean centred hot blob the tracker locks (boresight, inside the default basket)."""
    yy, xx = np.mgrid[0:512, 0:640]
    f = 4096.0 + 8000.0 * np.exp(-(((xx - 320) ** 2 + (yy - 256) ** 2) / (2 * 4.0 ** 2)))
    return np.clip(f, 0, 65535).astype(np.uint16)


def _run(disc):
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), discriminator=disc)
    out = None
    for i in range(12):                       # a few frames to pass stable_frame_count -> LOCKED
        out = pipe.step(now=i / 60.0, frame_u16=_hot_frame(), gyro_omega_xyz=(0, 0, 0), dt=1 / 60.0)
    return out


def test_discriminator_can_withdraw_engage_permission():
    permit = _run(lambda frame, centroid: True)
    deny = _run(lambda frame, centroid: False)
    assert "LOCK" in permit.tracking_state and "LOCK" in deny.tracking_state
    assert permit.engage_permitted is True
    assert deny.engage_permitted is False     # AI-firewall: discriminator withdrew permission


def test_discriminator_never_touches_the_lock():
    # DENY must not change WHERE the seeker looks -- only whether engage is permitted (Inv 2).
    permit = _run(lambda frame, centroid: True)
    deny = _run(lambda frame, centroid: False)
    assert permit.centroid_px is not None and deny.centroid_px is not None
    assert permit.centroid_px == deny.centroid_px


def test_no_discriminator_keeps_default_behaviour():
    out = _run(None)                          # default: engage-permission follows the IMM alarm only
    assert "LOCK" in out.tracking_state
    assert isinstance(out.engage_permitted, bool)
