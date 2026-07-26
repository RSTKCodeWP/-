"""The fine-tune training config (Tasks 2.5.2 + 2.5.3).

One frozen config object, shared byte-identically by both ablation arms — so the ONLY thing
that differs between `{HERIDAL+SARD}` and `{VisDrone-pretrain → HERIDAL+SARD}` is the
pretrain `weights`. Everything that could otherwise confound the A/B (seed, determinism,
a fixed batch instead of non-deterministic AutoBatch, image size, epochs) is pinned here.

**Augmentation (Task 2.5.2) is Ultralytics built-ins, not a custom transform.** A hand-rolled
transform would fight the stochastic mosaic/mixup pipeline and the plan's
"deterministic-under-seed" requirement is a category error inside it. The one augmentation
knob this config controls is **scale-jitter (`scale`)**, which flows into
`YOLO.train(**cfg.to_ultralytics())`. Motion-blur is applied by Ultralytics' own
Albumentations integration with a small default probability when albumentations is installed
— it is NOT a `train()` hyperparameter, so this config does not (and cannot) tune it; we do
not claim a blur knob that doesn't exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Ultralytics requires the input to be a multiple of the max stride (32) for YOLO11.
_STRIDE = 32


@dataclass(frozen=True)
class TrainConfig:
    """Resolved hyperparameters for one fine-tune run. `weights` is the only per-arm field."""

    weights: str
    imgsz: int = 960
    epochs: int = 100
    batch: int = 64  # FIXED int — never -1 (AutoBatch probes VRAM, non-deterministic / unfair)
    seed: int = 0
    deterministic: bool = True
    patience: int = 0  # 0 = no early-stop, so both arms train the SAME number of epochs
    lr0: float = 0.01
    # --- augmentation (Ultralytics built-in; Task 2.5.2) ---
    # `scale` is the scale-jitter knob (±this fraction of object scale → tiny-target
    # robustness); it flows to YOLO.train() via to_ultralytics(). Motion-blur is NOT a
    # train() hyperparameter — Ultralytics auto-applies an Albumentations blur with a small
    # default probability when albumentations is installed (no per-run knob), so it is not
    # carried here. (An earlier `blur_p` field was a no-op — it never reached the trainer —
    # and has been removed rather than imply a control that doesn't exist.)
    scale: float = 0.5
    workers: int = 8
    data: str = field(default="")  # path to the generated dataset.yaml; set at submit time

    def __post_init__(self) -> None:
        if self.imgsz <= 0 or self.imgsz % _STRIDE != 0:
            raise ValueError(f"imgsz must be a positive multiple of {_STRIDE}, got {self.imgsz}")
        if self.epochs <= 0:
            raise ValueError(f"epochs must be positive, got {self.epochs}")
        if self.batch == -1:
            raise ValueError("batch must be a fixed int (not -1/AutoBatch) for a fair ablation")

    def to_ultralytics(self) -> dict:
        """The kwargs handed to `YOLO.train()`. Excludes `weights` (that's `YOLO(weights)`).

        Every field here is a real Ultralytics `train()` argument (`scale` is the
        augmentation knob that actually reaches the trainer). `project`/`name`/`resume` are
        supplied per-arm by the caller, not here, so this dict is identical across arms.
        """
        d = {
            "data": self.data,
            "imgsz": self.imgsz,
            "epochs": self.epochs,
            "batch": self.batch,
            "seed": self.seed,
            "deterministic": self.deterministic,
            "patience": self.patience,
            "lr0": self.lr0,
            "scale": self.scale,
            "workers": self.workers,
        }
        return d
