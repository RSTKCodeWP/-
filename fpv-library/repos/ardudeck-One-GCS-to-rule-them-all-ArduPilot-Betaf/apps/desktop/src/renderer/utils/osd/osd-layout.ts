/**
 * Anchor-preserving remap of an OSD element position from one character grid to
 * another (e.g. analog 30x16 -> HD 50x18). An element at the right/bottom edge
 * stays at the right/bottom edge; interior elements keep their relative place.
 * Pure + tested so the reflow-on-format-change and auto-arrange behave the same.
 */

export interface GridPos {
  x: number;
  y: number;
}

export function remapToCanvas(
  pos: GridPos,
  size: { width: number; height: number },
  oldCols: number,
  oldRows: number,
  newCols: number,
  newRows: number,
): GridPos {
  const maxOldX = Math.max(1, oldCols - size.width);
  const maxOldY = Math.max(1, oldRows - size.height);
  const maxNewX = Math.max(0, newCols - size.width);
  const maxNewY = Math.max(0, newRows - size.height);
  return {
    x: Math.max(0, Math.min(maxNewX, Math.round((pos.x / maxOldX) * maxNewX))),
    y: Math.max(0, Math.min(maxNewY, Math.round((pos.y / maxOldY) * maxNewY))),
  };
}
