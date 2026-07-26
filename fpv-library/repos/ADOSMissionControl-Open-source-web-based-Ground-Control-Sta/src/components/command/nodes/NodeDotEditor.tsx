"use client";

/**
 * @module nodes/NodeDotEditor
 * @description The "Configure dots" editor: pick which verified signals map to a
 * node's feature dots, in order, from the profile's capability-gated allowlist.
 * Each slot is a portal `Select` (never a native <select>), so an impossible
 * signal for the profile is simply not offered. Persists an ordered, deduped
 * `FeatureDot[]` to the node-personalization overlay.
 * @license GPL-3.0-only
 */

import { useMemo, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { SelectOption } from "@/components/ui/select-types";
import type { EffProfile } from "@/lib/nodes/node-profile";
import {
  allowedSignals,
  defaultDots,
  SIGNAL_META,
  type FeatureDot,
  type SignalKey,
} from "@/lib/nodes/node-feature-dots";
import { useNodePersonalizationStore } from "@/stores/node-personalization-store";

/** The max dot slots the expanded row can show. */
const MAX_SLOTS = 4;
/** Sentinel for an empty slot. */
const NONE = "";

interface NodeDotEditorProps {
  deviceId: string;
  effProfile: EffProfile;
  open: boolean;
  onClose: () => void;
}

export function NodeDotEditor({
  deviceId,
  effProfile,
  open,
  onClose,
}: NodeDotEditorProps) {
  const setDots = useNodePersonalizationStore((s) => s.setDots);
  const stored = useNodePersonalizationStore((s) => s.byNode[deviceId]?.dots);
  const allowed = useMemo(() => allowedSignals(effProfile), [effProfile]);

  // Seed the slots from the stored overlay, else the profile starter set.
  const initialSlots = useMemo<string[]>(() => {
    const source =
      stored && stored.length > 0 ? stored : defaultDots(effProfile);
    const seeded = source
      .map((d) => d.signal)
      .filter((s) => allowed.includes(s))
      .slice(0, MAX_SLOTS);
    return [...seeded, ...Array(MAX_SLOTS - seeded.length).fill(NONE)];
    // Re-seed only when the dialog is (re)opened for a node, not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId, effProfile, open]);

  const [slots, setSlots] = useState<string[]>(initialSlots);

  // Reset the working slots whenever the seed changes (a different node/open).
  const seedKey = initialSlots.join("|");
  const [lastSeed, setLastSeed] = useState(seedKey);
  if (seedKey !== lastSeed) {
    setLastSeed(seedKey);
    setSlots(initialSlots);
  }

  const options: SelectOption[] = useMemo(
    () => [
      { value: NONE, label: "None" } /* i18n */,
      ...allowed.map((s) => ({ value: s, label: SIGNAL_META[s].label })),
    ],
    [allowed],
  );

  function setSlot(index: number, value: string) {
    setSlots((prev) => prev.map((v, i) => (i === index ? value : v)));
  }

  function save() {
    // Collapse to an ordered, deduped, allowlist-safe FeatureDot[].
    const seen = new Set<string>();
    const dots: FeatureDot[] = [];
    for (const raw of slots) {
      if (!raw || seen.has(raw)) continue;
      const signal = raw as SignalKey;
      if (!allowed.includes(signal)) continue;
      seen.add(raw);
      dots.push({ signal });
    }
    setDots(deviceId, dots.length > 0 ? dots : undefined);
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Configure dots" /* i18n */
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel {/* i18n */}
          </Button>
          <Button variant="primary" onClick={save}>
            Save {/* i18n */}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-text-tertiary">
          {/* i18n */}
          Pin up to {MAX_SLOTS} verified signals as dots on this node. A signal
          with no reading shows a hollow ring, never a fake status.
        </p>
        {slots.map((value, index) => (
          <Select
            key={index}
            label={`Dot ${index + 1}` /* i18n */}
            options={options}
            value={value}
            onChange={(v) => setSlot(index, v)}
            placeholder="None" /* i18n */
          />
        ))}
      </div>
    </Modal>
  );
}
