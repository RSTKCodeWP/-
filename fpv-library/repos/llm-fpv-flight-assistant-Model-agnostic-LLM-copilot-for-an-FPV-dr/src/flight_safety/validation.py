from dataclasses import dataclass
from flight_safety.config import Limits
from flight_safety.geofence import inside_geofence
from flight_safety.models import (
    Command, Telemetry, GotoCommand, OrbitCommand, ArmTakeoffCommand,
)

# Verbs that bypass all gating because they are recovery/safety actions
# (return_to_launch, land, handback, loiter) OR hand control to the human
# (takeover), who then assumes responsibility. They must remain available even
# with low battery or degraded health.
_SAFETY_VERBS = {"return_to_launch", "land", "handback", "loiter", "takeover"}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None = None


def validate_command(
    cmd: Command,
    tlm: Telemetry,
    limits: Limits,
    geofence: list[tuple[float, float]],
) -> ValidationResult:
    """Deterministically decide whether a command may execute. Returns ok + reason."""
    verb = cmd.verb

    # Safety/recovery verbs bypass battery/geofence gating.
    if verb in _SAFETY_VERBS:
        return ValidationResult(True)

    # Health preconditions for any active command.
    if not tlm.gps_ok:
        return ValidationResult(False, "Rejected: GPS health not OK.")
    if not tlm.ekf_ok:
        return ValidationResult(False, "Rejected: EKF/estimator health not OK.")
    if tlm.battery_pct < limits.min_battery_pct:
        return ValidationResult(
            False,
            f"Rejected: battery {tlm.battery_pct:.0%} below minimum "
            f"{limits.min_battery_pct:.0%}.",
        )

    if isinstance(cmd, ArmTakeoffCommand):
        if tlm.armed and tlm.alt_m > 1.0:
            return ValidationResult(False, "Rejected: already armed and airborne.")
        # Lower bound is exclusive (alt must be strictly ABOVE the floor; the
        # default floor of 0 means "must be airborne"); upper bound is inclusive.
        if not (limits.min_alt_m < cmd.alt <= limits.max_alt_m):
            return ValidationResult(False, f"Rejected: takeoff alt {cmd.alt} m out of limits.")
        return ValidationResult(True)

    if isinstance(cmd, GotoCommand):
        if not (limits.min_alt_m < cmd.alt <= limits.max_alt_m):
            return ValidationResult(False, f"Rejected: alt {cmd.alt} m out of limits.")
        if not inside_geofence(cmd.lat, cmd.lon, geofence):
            return ValidationResult(False, "Rejected: target outside geofence.")
        return ValidationResult(True)

    if isinstance(cmd, OrbitCommand):
        if not (limits.min_alt_m < cmd.alt <= limits.max_alt_m):
            return ValidationResult(False, f"Rejected: alt {cmd.alt} m out of limits.")
        center = cmd.center if cmd.center is not None else (tlm.lat, tlm.lon)
        if not inside_geofence(center[0], center[1], geofence):
            return ValidationResult(False, "Rejected: orbit center outside geofence.")
        return ValidationResult(True)

    return ValidationResult(False, f"Rejected: unsupported verb '{verb}'.")
