"""Core ML (ANE) detector — the on-device inference backend (Task 2.3).

Thin wrapper: letterbox the frame (preprocess), run the `.mlpackage` on the ANE,
decode + NMS the raw output (postprocess). The model's image input has the `/255`
normalization baked in, so it eats the letterboxed **uint8** canvas directly (verified
from the `.mlpackage` spec). Stateless per the `Detector` contract.

coremltools is lazy-imported (it's in the optional `bench` group), so this module
imports on a machine without the ML deps — only `detect()` needs them. The matching
test is marked `ane` and excluded on CI; CI exercises the same decode via the ONNX
backend (Task 2.4).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .detector import Detection, Detector
from .postprocess import decode_yolo
from .preprocess import letterbox


class CoreMLDetector(Detector):
    """Runs the exported YOLO `.mlpackage` on the Apple Neural Engine."""

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

        # Lazy import keeps the module loadable without the `bench` group.
        from coremltools import ComputeUnit
        from coremltools.models import MLModel

        self._model = MLModel(str(self.model_path), compute_units=ComputeUnit.ALL)
        spec = self._model.get_spec()
        self._input_name = spec.description.input[0].name
        self._output_name = spec.description.output[0].name

    def detect(self, frame: np.ndarray) -> list[Detection]:
        lb = letterbox(frame, imgsz=self.imgsz)
        out = self._model.predict({self._input_name: Image.fromarray(lb.image)})
        raw = np.asarray(out[self._output_name], dtype=np.float32)
        return decode_yolo(
            raw,
            lb,
            conf_threshold=self.conf_threshold,
            iou_threshold=self.iou_threshold,
        )
