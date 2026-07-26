/**
 * OSD Edit Panel
 *
 * Right-panel content for edit mode.
 * Shows position editor with alignment buttons and nudge controls.
 */

import { useOsdStore, DEFAULT_ELEMENT_POSITIONS, type OsdElementId, type OsdElementKey } from '../../stores/osd-store';
import { getElementSize } from '../../utils/osd/element-sizes';
import { getModuleOsdElement } from '../../modules/module-osd-registry';
import { getOsdRows, getOsdCols } from '../../utils/osd/font-renderer';

interface Props {
  selectedElement: OsdElementKey | null;
  onDone?: () => void;
}

export function OsdEditPanel({ selectedElement, onDone }: Props) {
  const elementPositions = useOsdStore((s) => s.elementPositions);
  const setElementPosition = useOsdStore((s) => s.setElementPosition);
  const toggleElement = useOsdStore((s) => s.toggleElement);
  const videoType = useOsdStore((s) => s.videoType);
  const supportedElements = useOsdStore((s) => s.supportedElements);
  const target = useOsdStore((s) => s.target);

  if (!selectedElement) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <p className="text-xs text-content-secondary text-center">
          Select an element to edit its position.
        </p>
      </div>
    );
  }

  const pos = elementPositions[selectedElement];
  if (!pos) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <p className="text-xs text-content-secondary text-center">
          Select an element to edit its position.
        </p>
      </div>
    );
  }
  // Module elements render ground-side, so the ArduPilot FC support gate never
  // applies to them.
  const isModule = getModuleOsdElement(selectedElement) != null;
  const unsupported =
    !isModule &&
    target === 'ardupilot' &&
    supportedElements != null &&
    !supportedElements.has(selectedElement as OsdElementId);
  const size = getElementSize(selectedElement);
  const rows = getOsdRows(videoType);
  const cols = getOsdCols(videoType);
  const maxX = cols - size.width;
  const maxY = rows - size.height;

  const setPos = (x: number, y: number) => {
    const clampedX = Math.max(0, Math.min(maxX, x));
    const clampedY = Math.max(0, Math.min(maxY, y));
    setElementPosition(selectedElement, { x: clampedX, y: clampedY });
  };

  const nudge = (dx: number, dy: number) => {
    setPos(pos.x + dx, pos.y + dy);
  };

  const centerH = () => setPos(Math.round((cols - size.width) / 2), pos.y);
  const centerV = () => setPos(pos.x, Math.round((rows - size.height) / 2));

  const handleReset = () => {
    const def =
      DEFAULT_ELEMENT_POSITIONS[selectedElement as OsdElementId] ??
      getModuleOsdElement(selectedElement)?.defaultPosition;
    if (def) setElementPosition(selectedElement, { x: def.x, y: def.y });
  };

  const formatName = (id: string) =>
    id.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-subtle">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium text-content">{formatName(selectedElement)}</h3>
          <div className="flex items-center gap-2">
            <button onClick={handleReset} className="text-[10px] text-blue-400 hover:text-blue-300">
              Reset
            </button>
            {onDone && (
              <button onClick={onDone} className="text-[10px] text-content-secondary hover:text-content">
                Done
              </button>
            )}
          </div>
        </div>
        <p className="text-[10px] text-content-secondary mt-0.5">
          {size.width}x{size.height} chars
        </p>
        <label className="flex items-center gap-2 mt-2 text-[11px] text-content cursor-pointer">
          <input
            type="checkbox"
            checked={pos.enabled}
            onChange={() => toggleElement(selectedElement)}
            className="w-3 h-3 rounded-sm bg-surface-raised border"
          />
          Show this element
        </label>
        {unsupported && (
          <p className="mt-2 text-[10px] text-amber-500">
            This board has no parameter for this element; it will not upload to the FC.
          </p>
        )}
      </div>

      <div className="p-3 space-y-3">
        {/* Position inputs */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] text-content-secondary mb-1">X Position</label>
            <input
              type="number"
              value={pos.x}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                if (!isNaN(v)) setPos(v, pos.y);
              }}
              min={0}
              max={maxX}
              className="w-full bg-surface-raised text-content text-xs rounded px-2 py-1 border border-subtle focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[10px] text-content-secondary mb-1">Y Position</label>
            <input
              type="number"
              value={pos.y}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                if (!isNaN(v)) setPos(pos.x, v);
              }}
              min={0}
              max={maxY}
              className="w-full bg-surface-raised text-content text-xs rounded px-2 py-1 border border-subtle focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Nudge arrows */}
        <div>
          <p className="text-[10px] text-content-secondary mb-1.5">Nudge</p>
          <div className="grid grid-cols-3 gap-1 w-24 mx-auto">
            <div />
            <NudgeBtn label="^" onClick={() => nudge(0, -1)} />
            <div />
            <NudgeBtn label="<" onClick={() => nudge(-1, 0)} />
            <div className="w-7 h-7" />
            <NudgeBtn label=">" onClick={() => nudge(1, 0)} />
            <div />
            <NudgeBtn label="v" onClick={() => nudge(0, 1)} />
            <div />
          </div>
        </div>

        {/* Alignment */}
        <div>
          <p className="text-[10px] text-content-secondary mb-1.5">Align</p>
          <div className="flex gap-1.5">
            <button
              onClick={centerH}
              className="flex-1 px-2 py-1 text-[10px] bg-surface-raised hover:bg-surface-raised text-content-secondary rounded border border-subtle"
            >
              Center H
            </button>
            <button
              onClick={centerV}
              className="flex-1 px-2 py-1 text-[10px] bg-surface-raised hover:bg-surface-raised text-content-secondary rounded border border-subtle"
            >
              Center V
            </button>
          </div>
          <div className="flex gap-1.5 mt-1.5">
            <button
              onClick={() => setPos(0, pos.y)}
              className="flex-1 px-2 py-1 text-[10px] bg-surface-raised hover:bg-surface-raised text-content-secondary rounded border border-subtle"
            >
              Left
            </button>
            <button
              onClick={() => setPos(maxX, pos.y)}
              className="flex-1 px-2 py-1 text-[10px] bg-surface-raised hover:bg-surface-raised text-content-secondary rounded border border-subtle"
            >
              Right
            </button>
          </div>
          <div className="flex gap-1.5 mt-1.5">
            <button
              onClick={() => setPos(pos.x, 0)}
              className="flex-1 px-2 py-1 text-[10px] bg-surface-raised hover:bg-surface-raised text-content-secondary rounded border border-subtle"
            >
              Top
            </button>
            <button
              onClick={() => setPos(pos.x, maxY)}
              className="flex-1 px-2 py-1 text-[10px] bg-surface-raised hover:bg-surface-raised text-content-secondary rounded border border-subtle"
            >
              Bottom
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NudgeBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-7 h-7 flex items-center justify-center bg-surface-raised hover:bg-surface-raised text-content-secondary text-xs rounded border border-subtle"
    >
      {label}
    </button>
  );
}
