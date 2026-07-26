"""`hades-make-showcase` - the qualitative showcase frames (Task 7.4).

Renders genuine model output on real HERIDAL held-out aerial SAR frames:
  1. `showcase-boxes.png` - fine-tuned detections drawn on a real frame, plus a zoomed crop
     (survivors are a handful of pixels in a 4000px aerial image, so the crop makes the win
     legible).
  2. `showcase-before-after.png` - stock YOLO11s vs the HADES SAR fine-tune on the SAME frame,
     side by side. This is the P2.5 win made visible: the stock COCO model barely fires on
     tiny aerial people; the fine-tune lights them up.

Every box is a real detection from a real exported model run on real footage - nothing is
drawn by hand or synthesized. The frames come from the leakage-guarded HERIDAL test split.

Needs the `dev` group (onnxruntime) and the exported ONNX models on disk.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from hades.detect.detector import Detection

# Survivor-urgency orange (docs/DESIGN-SYSTEM.md --st-warning) for the fine-tune boxes;
# a muted slate for the stock model so the before/after reads at a glance.
BOX_FT = (232, 83, 31)
BOX_STOCK = (126, 120, 168)
TEXT_HI = (230, 237, 243)
PANEL_BG = (11, 14, 20)


def _label_count(jpg: Path, labels_dir: Path) -> int:
    base = jpg.stem
    lbl = labels_dir / f"{base}.txt"
    if lbl.exists():
        return sum(1 for _ in lbl.open())
    return 0


def pick_showcase_frame(heridal_dir: Path) -> tuple[Path, int]:
    """Pick the person-richest real HERIDAL frame (the most compelling showcase)."""
    frames = [Path(p) for p in glob.glob(str(heridal_dir / "*.JPG"))]
    if not frames:
        frames = [Path(p) for p in glob.glob(str(heridal_dir / "*.jpg"))]
    if not frames:
        raise FileNotFoundError(f"no HERIDAL frames under {heridal_dir}")
    labels_dir = heridal_dir.parent / "labels"
    best = max(frames, key=lambda f: _label_count(f, labels_dir))
    return best, _label_count(best, labels_dir)


def draw_boxes(frame: np.ndarray, detections: list[Detection], *,
               color: tuple[int, int, int] = BOX_FT, width: int = 6,
               label: bool = True) -> np.ndarray:
    """Draw detection boxes onto a copy of the frame; return the annotated RGB array."""
    img = Image.fromarray(frame).convert("RGB")
    draw = ImageDraw.Draw(img)
    for d in detections:
        x0, y0, x1, y1 = d.box_xyxy
        draw.rectangle((x0, y0, x1, y1), outline=color, width=width)
        if label:
            draw.text((x0 + 2, max(0, y0 - 14)), f"{d.conf:.2f}", fill=color)
    return np.array(img)


def _zoom_crop(frame: np.ndarray, detections: list[Detection], *, size: int = 700) -> np.ndarray:
    """Crop a square window around the densest cluster of detections, then upscale."""
    if not detections:
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
    else:
        xs = [(d.box_xyxy[0] + d.box_xyxy[2]) / 2 for d in detections]
        ys = [(d.box_xyxy[1] + d.box_xyxy[3]) / 2 for d in detections]
        cx, cy = int(np.median(xs)), int(np.median(ys))
    h, w = frame.shape[:2]
    half = size // 2
    x0 = max(0, min(cx - half, w - size))
    y0 = max(0, min(cy - half, h - size))
    crop = frame[y0:y0 + size, x0:x0 + size]
    return np.array(Image.fromarray(crop).resize((size, size), Image.NEAREST))


def _hstack(left: np.ndarray, right: np.ndarray, gap: int = 16) -> np.ndarray:
    """Place two equal-height images side by side on the panel background."""
    h = max(left.shape[0], right.shape[0])
    w = left.shape[1] + gap + right.shape[1]
    canvas = np.full((h, w, 3), PANEL_BG, dtype=np.uint8)
    canvas[: left.shape[0], : left.shape[1]] = left
    canvas[: right.shape[0], left.shape[1] + gap :] = right
    return canvas


def make_showcase(*, out_dir: Path, heridal_dir: Path, ft_model: Path,
                  stock_model: Path | None = None) -> list[Path]:
    """Render the showcase frames from real footage + real model output."""
    from hades.detect.onnx_detector import OnnxDetector

    out_dir.mkdir(parents=True, exist_ok=True)
    frame_path, n_gt = pick_showcase_frame(heridal_dir)
    frame = np.array(Image.open(frame_path).convert("RGB"))

    ft = OnnxDetector(str(ft_model), imgsz=_model_imgsz(ft_model), conf_threshold=0.25)
    ft_dets = ft.detect(frame)

    written: list[Path] = []

    # 1. Boxes on the full frame + a zoomed crop, stacked.
    full = draw_boxes(frame, ft_dets, color=BOX_FT, width=8)
    full_small = np.array(Image.fromarray(full).resize((700, 525), Image.LANCZOS))
    crop = _zoom_crop(draw_boxes(frame, ft_dets, color=BOX_FT, width=4), ft_dets, size=525)
    boxes_panel = _hstack(full_small, crop)
    p1 = out_dir / "showcase-boxes.png"
    Image.fromarray(boxes_panel).save(p1)
    written.append(p1)

    # 2. Stock vs fine-tuned on the same frame (the P2.5 win).
    stock_path = stock_model or _default_stock_model(ft_model)
    if stock_path and Path(stock_path).exists():
        # The stock COCO export is baked at 640; run it at its native size (the fine-tune
        # ships at 960). Each model at its own shipped resolution is the honest comparison.
        stock = OnnxDetector(str(stock_path), imgsz=_model_imgsz(stock_path), conf_threshold=0.25)
        stock_dets = stock.detect(frame)
        left = _zoom_crop(draw_boxes(frame, stock_dets, color=BOX_STOCK, width=4),
                          ft_dets, size=525)
        right = _zoom_crop(draw_boxes(frame, ft_dets, color=BOX_FT, width=4), ft_dets, size=525)
        ba = _hstack(left, right)
        p2 = out_dir / "showcase-before-after.png"
        Image.fromarray(ba).save(p2)
        written.append(p2)

    return written


def _model_imgsz(onnx_path: Path, default: int = 640) -> int:
    """Read the square input side baked into an exported ONNX (so we feed the right size)."""
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    shape = session.get_inputs()[0].shape  # [1, 3, H, W]
    side = shape[2]
    return int(side) if isinstance(side, int) else default


def _default_stock_model(ft_model: Path) -> Path | None:
    """The stock YOLO11s ONNX lives in service/models next to the package."""
    candidate = Path(__file__).resolve().parents[3] / "models" / "yolo11s_640.onnx"
    return candidate if candidate.exists() else None


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(prog="hades-make-showcase", description=__doc__)
    parser.add_argument("--heridal", type=Path,
                        default=repo / "artifacts" / "heridal_holdout_test" / "images")
    parser.add_argument("--ft-model", type=Path,
                        default=repo / "artifacts" / "armA_heridal_sard" / "models"
                        / "yolo11s_960.onnx")
    parser.add_argument("--stock-model", type=Path, default=None)
    parser.add_argument("--out", type=Path,
                        default=repo / "docs" / "documentation" / "figures" / "showcase")
    args = parser.parse_args(argv)

    written = make_showcase(out_dir=args.out, heridal_dir=args.heridal,
                            ft_model=args.ft_model, stock_model=args.stock_model)
    print(f"rendered {len(written)} showcase frames to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
