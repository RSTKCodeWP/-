"""Grid-based camera mask (StabX-style ROI exclusion)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np


class CameraMask:
    def __init__(self, cols: int = 16, rows: int = 12):
        self.cols = cols
        self.rows = rows
        self.cells: List[bool] = [False] * (cols * rows)

    def clear(self) -> None:
        self.cells = [False] * (self.cols * self.rows)

    def set_cell(self, col: int, row: int, masked: bool) -> None:
        if 0 <= col < self.cols and 0 <= row < self.rows:
            self.cells[row * self.cols + col] = masked

    def toggle_cell(self, col: int, row: int) -> None:
        i = row * self.cols + col
        if 0 <= i < len(self.cells):
            self.cells[i] = not self.cells[i]

    def to_list(self) -> List[List[bool]]:
        return [
            self.cells[r * self.cols : (r + 1) * self.cols] for r in range(self.rows)
        ]

    def from_list(self, grid: List[List[bool]]) -> None:
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 16
        self.cells = [bool(c) for row in grid for c in row]

    def build_opencv_mask(self, width: int, height: int) -> np.ndarray:
        mask = np.ones((height, width), dtype=np.uint8) * 255
        cw, ch = width / self.cols, height / self.rows
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r * self.cols + c]:
                    x0, y0 = int(c * cw), int(r * ch)
                    x1, y1 = int((c + 1) * cw), int((r + 1) * ch)
                    mask[y0:y1, x0:x1] = 0
        return mask

    def masked_fraction_in_roi(
        self, roi_x: int, roi_y: int, roi_w: int, roi_h: int, frame_w: int, frame_h: int
    ) -> float:
        """Fraction of analysis ROI covered by mask (0..1)."""
        cw, ch = frame_w / self.cols, frame_h / self.rows
        total = 0
        masked = 0
        for r in range(self.rows):
            for c in range(self.cols):
                cx = int((c + 0.5) * cw)
                cy = int((r + 0.5) * ch)
                if roi_x <= cx < roi_x + roi_w and roi_y <= cy < roi_y + roi_h:
                    total += 1
                    if self.cells[r * self.cols + c]:
                        masked += 1
        return masked / total if total else 0.0

    def draw_overlay(self, bgr: np.ndarray, alpha: float = 0.45) -> np.ndarray:
        h, w = bgr.shape[:2]
        overlay = bgr.copy()
        cw, ch = w / self.cols, h / self.rows
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r * self.cols + c]:
                    x0, y0 = int(c * cw), int(r * ch)
                    x1, y1 = int((c + 1) * cw), int((r + 1) * ch)
                    cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 0, 220), -1)
        return cv2.addWeighted(overlay, alpha, bgr, 1 - alpha, 0)

    def draw_grid(self, bgr: np.ndarray) -> np.ndarray:
        out = bgr.copy()
        h, w = out.shape[:2]
        cw, ch = w / self.cols, h / self.rows
        for c in range(1, self.cols):
            x = int(c * cw)
            cv2.line(out, (x, 0), (x, h), (80, 80, 80), 1)
        for r in range(1, self.rows):
            y = int(r * ch)
            cv2.line(out, (0, y), (w, y), (80, 80, 80), 1)
        return out

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cols": self.cols, "rows": self.rows, "cells": self.cells}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> CameraMask:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        m = cls(data.get("cols", 16), data.get("rows", 12))
        cells = data.get("cells", [])
        if len(cells) == m.cols * m.rows:
            m.cells = [bool(x) for x in cells]
        return m
