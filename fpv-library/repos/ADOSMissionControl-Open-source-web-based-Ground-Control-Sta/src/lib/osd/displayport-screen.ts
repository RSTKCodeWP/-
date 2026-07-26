/**
 * DisplayPort screen model. Applies decoded MSP_DISPLAYPORT ops to a character
 * grid so a GCS can render the OSD the flight controller is painting.
 *
 * @module lib/osd/displayport-screen
 */

import { DP_RESOLUTIONS, type DisplayPortOp } from "@/lib/protocol/msp/decoders/config/displayport";

/** Non-ASCII cells are custom font glyphs we cannot render — shown as a dot. */
function sanitize(code: string): string {
  const c = code.charCodeAt(0);
  return c >= 0x20 && c <= 0x7e ? code : "·";
}

export class DisplayPortScreen {
  cols: number;
  rows: number;
  /** grid[row][col] — one printable character per cell. */
  grid: string[][];

  constructor(cols = 30, rows = 16) {
    this.cols = cols;
    this.rows = rows;
    this.grid = this.blank();
  }

  private blank(): string[][] {
    return Array.from({ length: this.rows }, () => Array.from({ length: this.cols }, () => " "));
  }

  resize(cols: number, rows: number): void {
    if (cols === this.cols && rows === this.rows) return;
    this.cols = cols;
    this.rows = rows;
    this.grid = this.blank();
  }

  clear(): void {
    this.grid = this.blank();
  }

  private writeString(row: number, col: number, text: string): void {
    if (row < 0 || row >= this.rows) return;
    for (let i = 0; i < text.length; i++) {
      const c = col + i;
      if (c < 0 || c >= this.cols) continue;
      this.grid[row][c] = sanitize(text[i]);
    }
  }

  /** Apply a decoded op; returns true when a DRAW_SCREEN completes a frame. */
  applyOp(op: DisplayPortOp): boolean {
    switch (op.kind) {
      case "clear":
        this.clear();
        return false;
      case "writeString":
        this.writeString(op.row, op.col, op.text);
        return false;
      case "options": {
        const r = DP_RESOLUTIONS[op.resolution];
        if (r) this.resize(r.cols, r.rows);
        return false;
      }
      case "draw":
        return true;
      // heartbeat / release / sys / unknown do not mutate the character grid
      default:
        return false;
    }
  }

  /** One string per row. */
  toLines(): string[] {
    return this.grid.map((r) => r.join(""));
  }
}
