/**
 * @module CustomOsdElementsPanel
 * @description iNav custom OSD elements editor.
 * Shows up to 8 custom text OSD elements. Each element has a visibility
 * toggle and a free-text field (max 16 ASCII characters).
 * @license GPL-3.0-only
 */

"use client";

import { useCallback, useState } from "react";
import { useDroneManager } from "@/stores/drone-manager";
import { useArmedLock } from "@/hooks/use-armed-lock";
import { PanelHeader } from "../shared/PanelHeader";
import { Type } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────

interface OsdElement {
  index: number;
  visible: boolean;
  text: string;
}

const ELEMENT_COUNT = 8;
const MAX_TEXT_LEN = 16;

function defaultElement(index: number): OsdElement {
  return { index, visible: false, text: "" };
}

// ── Component ─────────────────────────────────────────────────

export function CustomOsdElementsPanel() {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const connected = !!getSelectedProtocol();

  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingIdx, setSavingIdx] = useState<number | null>(null);
  const [elements, setElements] = useState<OsdElement[]>(
    Array.from({ length: ELEMENT_COUNT }, (_, i) => defaultElement(i)),
  );

  const { isArmed, lockMessage } = useArmedLock();

  // iNav does not provide a GET command that returns custom OSD element text
  // back to the configurator. The FC stores elements write-only. Users configure
  // elements in this table and save each row; the FC applies on next render.
  // "Reset" clears the local table so the user can start fresh without rebooting.
  const handleReset = useCallback(() => {
    setElements(Array.from({ length: ELEMENT_COUNT }, (_, i) => defaultElement(i)));
    setHasLoaded(false);
    setError(null);
  }, []);

  const handleRead = useCallback(async () => {
    const protocol = getSelectedProtocol();
    if (!protocol) { setError("Not connected"); return; }
    setLoading(true); setError(null);
    setHasLoaded(true);
    setLoading(false);
  }, [getSelectedProtocol]);

  function updateElement(idx: number, key: keyof OsdElement, value: unknown) {
    setElements((prev) =>
      prev.map((el, i) => (i === idx ? { ...el, [key]: value } : el)),
    );
  }

  const handleSave = useCallback(async (idx: number) => {
    const protocol = getSelectedProtocol();
    if (!protocol?.setCustomOsdElement) { setError("Custom OSD elements not available on this firmware"); return; }
    setSavingIdx(idx); setError(null);
    try {
      const result = await protocol.setCustomOsdElement(elements[idx]);
      if (!result.success) setError(result.message);
    } catch (err) {
      setError(String(err));
    } finally {
      setSavingIdx(null);
    }
  }, [getSelectedProtocol, elements]);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <p className="text-[11px] text-text-tertiary border border-border-default rounded px-3 py-2 bg-bg-secondary">
          iNav does not support reading custom OSD elements back from the flight controller.
          Start from a blank table and write each row to persist.
        </p>
        <PanelHeader
          title="Custom OSD"
          subtitle={`Up to ${ELEMENT_COUNT} custom text OSD elements. Max ${MAX_TEXT_LEN} ASCII characters each.`}
          icon={<Type size={16} />}
          loading={loading}
          loadProgress={null}
          hasLoaded={hasLoaded}
          onRead={handleRead}
          connected={connected}
          error={error}
        >
          {hasLoaded && (
            <button
              onClick={handleReset}
              className="text-[11px] px-3 py-1 border border-border-default text-text-secondary rounded hover:bg-bg-tertiary"
            >
              Reset
            </button>
          )}
        </PanelHeader>

        {hasLoaded && (
          <div className="border border-border-default rounded overflow-hidden">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-border-default bg-bg-secondary">
                  <th className="px-3 py-2 text-left text-text-tertiary font-medium w-8">#</th>
                  <th className="px-3 py-2 text-left text-text-tertiary font-medium w-20">Visible</th>
                  <th className="px-3 py-2 text-left text-text-tertiary font-medium">Text</th>
                  <th className="px-3 py-2 text-left text-text-tertiary font-medium w-20"></th>
                </tr>
              </thead>
              <tbody>
                {elements.map((el, idx) => (
                  <tr key={idx} className="border-b border-border-default last:border-0">
                    <td className="px-3 py-2 font-mono text-text-tertiary">{idx}</td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => updateElement(idx, "visible", !el.visible)}
                        className={`px-2 py-0.5 rounded border text-[10px] ${
                          el.visible
                            ? "border-accent-primary bg-accent-primary/20 text-accent-primary"
                            : "border-border-default text-text-secondary"
                        }`}
                      >
                        {el.visible ? "On" : "Off"}
                      </button>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        maxLength={MAX_TEXT_LEN}
                        value={el.text}
                        onChange={(e) => updateElement(idx, "text", e.target.value.slice(0, MAX_TEXT_LEN))}
                        placeholder={`Element ${idx} text`}
                        className="w-full bg-bg-tertiary border border-border-default rounded px-2 py-1 font-mono text-text-primary placeholder:text-text-tertiary"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => handleSave(idx)}
                        disabled={savingIdx === idx || isArmed}
                        title={isArmed ? lockMessage : undefined}
                        className="text-[10px] px-2 py-1 border border-accent-primary text-accent-primary rounded hover:bg-accent-primary/10 disabled:opacity-50"
                      >
                        {savingIdx === idx ? "..." : "Save"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
