from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class FPSMeter:
    """Simple FPS and latency tracker for video inference."""

    latencies_ms: list[float] = field(default_factory=list)
    frame_count: int = 0
    start_time: float = field(default_factory=time.perf_counter)

    def add_latency(self, latency_ms: float) -> None:
        self.latencies_ms.append(float(latency_ms))
        self.frame_count += 1

    @property
    def elapsed_s(self) -> float:
        return max(time.perf_counter() - self.start_time, 1e-9)

    @property
    def average_fps(self) -> float:
        return self.frame_count / self.elapsed_s

    @property
    def mean_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return statistics.fmean(self.latencies_ms)

    def percentile_latency_ms(self, percentile: float) -> float:
        """Compute a percentile latency with nearest-rank approximation."""
        if not self.latencies_ms:
            return 0.0
        if percentile <= 0:
            return min(self.latencies_ms)
        if percentile >= 100:
            return max(self.latencies_ms)
        sorted_values = sorted(self.latencies_ms)
        index = round((percentile / 100) * (len(sorted_values) - 1))
        return sorted_values[index]

    def summary(self) -> dict[str, float | int]:
        return {
            "frames_measured": self.frame_count,
            "elapsed_s": round(self.elapsed_s, 4),
            "average_fps": round(self.average_fps, 3),
            "mean_latency_ms": round(self.mean_latency_ms, 3),
            "p50_latency_ms": round(self.percentile_latency_ms(50), 3),
            "p95_latency_ms": round(self.percentile_latency_ms(95), 3),
        }
