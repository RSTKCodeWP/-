"""Generate a small FPV racing-gate seed photo bundle for Label Studio."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import urllib.parse
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FPV_GATE_SEED_PHOTO_MANIFEST_SCHEMA = "fpv_labelstudio_seed_photo_manifest.v1"
DEFAULT_DATASET_ID = "fpv_racing_gate_seed_20260601"
DEFAULT_OUTPUT_DIR = Path("labeled/imports/fpv_racing_gate_seed_20260601")
DEFAULT_LABEL_CONFIG = Path("labeled/configs/fpv_racing_gate.xml")
DEFAULT_IMAGE_NAME = "fpv_gate_seed_0001.png"
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SeedPhotoBundle:
    output_dir: Path
    image_path: Path
    tasks_path: Path
    manifest_path: Path
    readme_path: Path
    manifest: dict[str, Any]


def write_fpv_gate_seed_photo_bundle(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    dataset_id: str = DEFAULT_DATASET_ID,
    label_config_path: Path = DEFAULT_LABEL_CONFIG,
    root: Path = ROOT,
    created_at: str | None = None,
) -> SeedPhotoBundle:
    """Write one synthetic local test photo plus an importable Label Studio task."""

    root = root.resolve()
    out_dir = _resolve(output_dir, root)
    images_dir = out_dir / "images"
    image_path = images_dir / DEFAULT_IMAGE_NAME
    tasks_path = out_dir / "tasks.json"
    manifest_path = out_dir / "manifest.json"
    readme_path = out_dir / "README.md"
    label_config = _resolve(label_config_path, root)

    images_dir.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(_render_seed_png(IMAGE_WIDTH, IMAGE_HEIGHT))
    image_sha256 = _sha256_file(image_path)
    image_rel = _rel(image_path, root)
    label_config_rel = _rel(label_config, root)
    local_url = _local_file_url(image_path, root)

    task = {
        "data": {
            "image": local_url,
            "image_path": image_rel,
            "dataset_id": dataset_id,
            "bucket": "rgb_day",
            "modality": "rgb_day",
            "stage": "fpv_gate_seed_photo",
            "source_type": "simulator",
            "source_note": "synthetic_local_test_photo_for_manual_labeling",
            "target_hint": "sports_racing_gate",
            "width": str(IMAGE_WIDTH),
            "height": str(IMAGE_HEIGHT),
            "sha256": image_sha256,
            "label_config": label_config_rel,
            "manual_review_candidate": True,
            "low_quality_candidate": False,
            "quality_flags": "",
            "notes": "Unlabeled seed image. Mark the racing gate bbox and gate_center manually.",
        },
        "meta": {
            "annotation_status": "unlabeled_seed_for_manual_review",
            "training_status": "not_accepted_until_labeled_and_reviewed",
            "label_studio_api_import_performed": False,
        },
    }
    _write_json(tasks_path, [task])

    manifest = _manifest(
        created_at=created_at or _utc_now(),
        dataset_id=dataset_id,
        output_dir=out_dir,
        image_path=image_path,
        image_sha256=image_sha256,
        local_url=local_url,
        label_config=label_config,
        tasks_path=tasks_path,
        readme_path=readme_path,
        root=root,
    )
    _write_json(manifest_path, manifest)
    readme_path.write_text(_readme(manifest), encoding="utf-8")

    return SeedPhotoBundle(
        output_dir=out_dir,
        image_path=image_path,
        tasks_path=tasks_path,
        manifest_path=manifest_path,
        readme_path=readme_path,
        manifest=manifest,
    )


def _manifest(
    *,
    created_at: str,
    dataset_id: str,
    output_dir: Path,
    image_path: Path,
    image_sha256: str,
    local_url: str,
    label_config: Path,
    tasks_path: Path,
    readme_path: Path,
    root: Path,
) -> dict[str, Any]:
    return {
        "schema": FPV_GATE_SEED_PHOTO_MANIFEST_SCHEMA,
        "status": "PASS",
        "generated_at": created_at,
        "dataset_id": dataset_id,
        "source_type": "synthetic_local_test_photo",
        "label_config": _rel(label_config, root),
        "output_dir": _rel(output_dir, root),
        "image_count": 1,
        "task_count": 1,
        "training_launched": False,
        "images": [
            {
                "image_id": "fpv_gate_seed_0001",
                "path": _rel(image_path, root),
                "local_files_url": local_url,
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "size_bytes": image_path.stat().st_size,
                "sha256": image_sha256,
                "labels_expected": ["racing_gate", "gate_center"],
            }
        ],
        "tasks": [
            {
                "task_id": "fpv_gate_seed_0001",
                "path": _rel(tasks_path, root),
                "import_required": True,
                "import_performed": False,
            }
        ],
        "label_studio": {
            "tasks_path": _rel(tasks_path, root),
            "task_import_required": True,
            "api_called": False,
            "database_modified": False,
            "sqlite_path": "labeled/.labelstudio/label_studio.sqlite3",
            "local_files_document_root": _rel(root, root),
            "local_files_serving_required": True,
        },
        "readme_path": _rel(readme_path, root),
        "safety_boundary": {
            "sports_fpv_gate_only": True,
            "does_not_touch_open_label_studio": True,
            "does_not_modify_label_studio_sqlite": True,
            "does_not_call_label_studio_api": True,
            "does_not_launch_training": True,
            "does_not_open_camera_gpio_uart": True,
            "hardware_test_authorized": False,
        },
    }


def _render_seed_png(width: int, height: int) -> bytes:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(_pixel(x, y, width, height))
    return _png_from_raw_rgb(width, height, bytes(raw))


def _pixel(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    r, g, b = _base_pixel(x, y, width, height)

    center_x = int(width * 0.515)
    center_y = int(height * 0.44)
    dx = float(x - center_x)
    dy = float(y - center_y)
    outer_rx = 230.0
    outer_ry = 166.0
    inner_rx = 176.0
    inner_ry = 122.0
    outer = (dx / outer_rx) ** 2 + (dy / outer_ry) ** 2
    inner = (dx / inner_rx) ** 2 + (dy / inner_ry) ** 2

    if outer <= 1.0 and inner >= 1.0:
        highlight = max(0, 30 - int(abs(dx + dy * 0.2) / 8.0))
        return _clamp_rgb(10 + highlight, 205 + highlight, 85 + highlight // 2)
    if 0.985 < outer <= 1.055:
        return _clamp_rgb(5, 130, 45)

    left_leg = center_x - int(outer_rx * 0.78)
    right_leg = center_x + int(outer_rx * 0.78)
    leg_top = center_y + int(outer_ry * 0.6)
    if leg_top <= y <= height - 66 and (abs(x - left_leg) <= 7 or abs(x - right_leg) <= 7):
        return _clamp_rgb(25, 165, 70)

    if abs(y - int(height * 0.78)) <= 2 and int(width * 0.12) <= x <= int(width * 0.9):
        return _clamp_rgb(190, 185, 160)

    return r, g, b


def _base_pixel(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    horizon = int(height * 0.72)
    if y < horizon:
        t = y / max(1, horizon)
        r = 96 + int(64 * t)
        g = 158 + int(48 * t)
        b = 220 + int(18 * t)
    else:
        t = (y - horizon) / max(1, height - horizon)
        r = 70 + int(32 * t)
        g = 82 + int(36 * t)
        b = 76 + int(24 * t)

    lane_center = width // 2
    lane_width = 110 + int((y / max(1, height)) * 310)
    if y > horizon and abs(x - lane_center) < lane_width:
        tarmac = 88 + int((y - horizon) / max(1, height - horizon) * 28)
        r, g, b = tarmac, tarmac + 3, tarmac + 1

    cloud = int(9 * math.sin(x * 0.018) + 7 * math.sin((x + y) * 0.011))
    grain = ((x * 37 + y * 17 + (x * y) % 97) % 13) - 6
    vignette = int(18 * ((x - width / 2) ** 2 / (width * width) + (y - height / 2) ** 2 / (height * height)))
    return _clamp_rgb(r + cloud + grain - vignette, g + cloud + grain - vignette, b + cloud + grain - vignette)


def _png_from_raw_rgb(width: int, height: int, raw_scanlines: bytes) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"".join(
        (
            signature,
            _png_chunk(b"IHDR", header),
            _png_chunk(b"IDAT", zlib.compress(raw_scanlines, level=6)),
            _png_chunk(b"IEND", b""),
        )
    )


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc & 0xFFFFFFFF)


def _clamp_rgb(r: int, g: int, b: int) -> tuple[int, int, int]:
    return (_clamp(r), _clamp(g), _clamp(b))


def _clamp(value: int) -> int:
    return max(0, min(255, value))


def _local_file_url(image_path: Path, root: Path) -> str:
    image_rel = image_path.resolve().relative_to(root.resolve()).as_posix()
    return "/data/local-files/?d=" + urllib.parse.quote(image_rel, safe="/._-")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _readme(manifest: dict[str, Any]) -> str:
    task_path = str(manifest["label_studio"]["tasks_path"])
    config_path = str(manifest["label_config"])
    image_path = str(manifest["images"][0]["path"])
    return "\n".join(
        [
            "# FPV Racing Gate Seed Photo",
            "",
            "This folder contains one synthetic local test photo for manual Label Studio labeling.",
            "",
            f"- Image: `{image_path}`",
            f"- Label config: `{config_path}`",
            f"- Import file: `{task_path}`",
            "- Import performed: `false`",
            "- Training launched: `false`",
            "- Label Studio API called: `false`",
            "- Label Studio SQLite modified: `false`",
            "",
            "Use the task file only when you are ready to import it into the FPV racing gate project.",
            "The expected manual labels are `racing_gate` bbox and `gate_center` keypoint.",
            "",
        ]
    )
