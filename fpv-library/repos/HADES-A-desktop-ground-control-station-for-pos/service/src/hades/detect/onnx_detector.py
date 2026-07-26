"""ONNX Runtime (CPU) detector — the deterministic, ANE-free backend (Task 2.4).

Same `Detector` contract as `CoreMLDetector`, same shared `decode_yolo` postprocess.
The difference is the input seam: an exported ONNX YOLO takes a **float32 NCHW `[0,1]`**
tensor named `images` (the `/255` is NOT baked in, unlike the Core ML image input), and
ORT returns `output0` as `(1, 84, 8400)` float32 — the same layout the decode expects,
no transpose. This backend is what runs on CI (onnxruntime is a `dev` dep; no torch).

onnxruntime is imported lazily so importing this module never requires the runtime —
parity with `coreml_detector` and so pure consumers of the interface stay light.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .detector import Detection, Detector
from .postprocess import decode_yolo
from .preprocess import letterbox, to_nchw_float


class OnnxDetector(Detector):
    """Runs an exported YOLO `.onnx` on the CPU via ONNX Runtime."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        imgsz: int = 640,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.7,
    ):
        self.model_path = Path(model_path)
        self.imgsz = imgsz
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

        import onnxruntime as ort

        self._session = ort.InferenceSession(
            str(self.model_path), providers=["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name
        # Decode reads the (1, 84, 8400) detection head; pick it by shape so a model
        # with auxiliary outputs (e.g. a scalar reduce in the seam test) can't confuse us.
        self._output_name = _detection_output_name(self._session)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        lb = letterbox(frame, imgsz=self.imgsz)
        tensor = to_nchw_float(lb.image)  # float32 NCHW [0,1] — ONNX expects this
        outputs = self._session.run([self._output_name], {self._input_name: tensor})
        raw = np.asarray(outputs[0], dtype=np.float32)
        return decode_yolo(
            raw,
            lb,
            conf_threshold=self.conf_threshold,
            iou_threshold=self.iou_threshold,
        )


def _detection_output_name(session) -> str:
    """Pick the YOLO detection head output: rank-3 with a leading batch dim of 1.

    A real export has exactly one such output (`output0`). Selecting by shape rather
    than position keeps us robust to extra outputs.
    """
    for o in session.get_outputs():
        shape = o.shape
        if len(shape) == 3 and (shape[0] in (1, "batch", None)):
            return o.name
    # Fall back to the first output if shapes are fully dynamic/unnamed.
    return session.get_outputs()[0].name
