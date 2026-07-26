/**
 * Loadout preset controls: pick the active loadout, save the current loadout as
 * a new named preset, rename the active preset, and delete it (the default is
 * permanent and its delete control is hidden). Shared by the cockpit Skill Bar
 * editor and the input config panel so the operator manages presets the same
 * way in both surfaces.
 *
 * @module fly/LoadoutPresetBar
 * @license GPL-3.0-only
 */

"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Pencil, Trash2, Check, X } from "lucide-react";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useSettingsStore } from "@/stores/settings-store";
import { DEFAULT_LOADOUT_ID } from "@/stores/settings/keybindings-slice";

export function LoadoutPresetBar() {
  const t = useTranslations("skillBindings");

  const loadouts = useSettingsStore((s) => s.loadouts);
  const activeLoadoutId = useSettingsStore((s) => s.activeLoadoutId);
  const setActiveLoadout = useSettingsStore((s) => s.setActiveLoadout);
  const createLoadout = useSettingsStore((s) => s.createLoadout);
  const deleteLoadout = useSettingsStore((s) => s.deleteLoadout);
  const renameLoadout = useSettingsStore((s) => s.renameLoadout);

  const active = loadouts[activeLoadoutId] ?? loadouts[DEFAULT_LOADOUT_ID];
  const isDefault = activeLoadoutId === DEFAULT_LOADOUT_ID;

  const options = useMemo(
    () =>
      Object.values(loadouts)
        .sort((a, b) => {
          // Default first, then alphabetical by name.
          if (a.id === DEFAULT_LOADOUT_ID) return -1;
          if (b.id === DEFAULT_LOADOUT_ID) return 1;
          return a.name.localeCompare(b.name);
        })
        .map((l) => ({
          value: l.id,
          label: l.id === DEFAULT_LOADOUT_ID ? t("defaultPreset") : l.name,
        })),
    [loadouts, t],
  );

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");

  const beginRename = () => {
    setNameDraft(active?.name ?? "");
    setEditingName(true);
  };
  const commitRename = () => {
    const next = nameDraft.trim();
    if (next.length > 0 && active) renameLoadout(active.id, next);
    setEditingName(false);
  };

  const handleCreate = () => {
    const id = createLoadout(t("newPresetName"), activeLoadoutId);
    setActiveLoadout(id);
    setNameDraft(t("newPresetName"));
    setEditingName(true);
  };

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="min-w-[180px]">
        {editingName ? (
          <div className="flex items-center gap-1">
            <input
              type="text"
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename();
                if (e.key === "Escape") setEditingName(false);
              }}
              aria-label={t("renameLabel")}
              autoFocus
              className="h-8 w-full border border-border-default bg-bg-tertiary px-2 text-xs text-text-primary focus:outline-none focus:border-accent-primary"
            />
            <Button
              variant="ghost"
              size="sm"
              icon={<Check size={12} />}
              onClick={commitRename}
              aria-label={t("renameConfirm")}
            />
            <Button
              variant="ghost"
              size="sm"
              icon={<X size={12} />}
              onClick={() => setEditingName(false)}
              aria-label={t("renameCancel")}
            />
          </div>
        ) : (
          <Select
            label={t("preset")}
            value={activeLoadoutId}
            onChange={setActiveLoadout}
            options={options}
          />
        )}
      </div>

      {!editingName && (
        <div className="flex items-center gap-1">
          <Button
            variant="secondary"
            size="sm"
            icon={<Plus size={12} />}
            onClick={handleCreate}
          >
            {t("savePreset")}
          </Button>
          {!isDefault && (
            <>
              <Button
                variant="ghost"
                size="sm"
                icon={<Pencil size={12} />}
                onClick={beginRename}
                aria-label={t("renamePreset")}
              />
              <Button
                variant="ghost"
                size="sm"
                icon={<Trash2 size={12} />}
                onClick={() => deleteLoadout(activeLoadoutId)}
                aria-label={t("deletePreset")}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}
