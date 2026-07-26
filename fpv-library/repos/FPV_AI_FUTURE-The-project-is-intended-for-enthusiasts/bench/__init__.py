"""Block-3 seeker test/observation bench.

A browser-based engineer's instrument panel for the thermal seeker: live annotated
thermal view, full telemetry HUD, and live calibration controls.  It drives the
REAL ``SeekerGuidancePipeline`` (read-only — it never commands a flight controller),
so what you see is exactly what the seeker computes.

Run on the Pi:
    PYTHONPATH=fpv python -m fpv_ai.bench --device /dev/video0
then open ``http://<pi>:8080`` in a browser on the same network.
"""

from fpv_ai.bench.observer import ObserverConfig, SeekerObserver

__all__ = ["SeekerObserver", "ObserverConfig"]
