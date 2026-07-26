"""seeker_core detector stage — the proven fpv.seeker.detect plugged in as the core's Detector.

Physics port (not a rewrite): the real thermal detector — white top-hat, adaptive threshold, connected
components, intensity-weighted sub-pixel centroid — the SAME one verified in fpv/ and reproduced
bit-exact by the FPGA front-end — produces the Detections the gimbal + tracker consume. It carries the
adaptive ThresholdState between frames. Runs on FT640 8-bit frames (radiometric=False); cam-temp / FFC
default to ambient / READY when the sensor gives no metadata.
"""
from __future__ import annotations

from fpv.seeker.detect import ThresholdState, detect_frame

from seeker_core.contracts import Blob, Detections, Frame


class RealDetector:
    """Adapts fpv.seeker.detect.detect_frame to the core Detector Protocol (Frame -> Detections)."""

    def __init__(self, *, min_snr: float = 2.0, min_area_px: int = 2,
                 region_bands: int = 4, graduated_k: bool = True,
                 cam_temp_c: float = 25.0, ffc_state: str = "READY") -> None:
        self._ts = ThresholdState()
        self._fid = 0
        self._cam_temp_c = cam_temp_c
        self._ffc = ffc_state
        self._kw = dict(min_snr=min_snr, min_area_px=min_area_px,
                        region_bands=region_bands, graduated_k=graduated_k)

    def detect(self, frame: Frame) -> Detections:
        blobs, self._ts = detect_frame(
            frame.pixels, cam_temp_c=self._cam_temp_c, ffc_state=self._ffc,
            threshold_state=self._ts, frame_id=self._fid,
            t_capture_ns=frame.provenance.t_capture_ns, **self._kw)
        self._fid += 1
        out = tuple(Blob(centroid_px=(float(b.centroid_px[0]), float(b.centroid_px[1])),
                         area_px=int(b.area_px), snr=float(b.snr),
                         bbox=tuple(int(v) for v in b.bbox)) for b in blobs)
        return Detections(blobs=out, provenance=frame.provenance)
