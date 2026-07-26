"use client";

/**
 * @module drone-detail/cameras/AddIpCameraDialog
 * @description Modal to add a network (RTSP / HTTP) camera as a new declared
 * leg. Collects a name, stream URL, mount orientation, and purposes; the leg id
 * is slugged from the name (unique against the existing roster) and the leg is
 * appended as a secondary stream (the operator can promote it to primary from
 * the editor). Submit hands the built leg up; the tab persists the list.
 * @license GPL-3.0-only
 */

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Select, type SelectOption } from "@/components/ui/select";
import {
  CAMERA_ORIENTATIONS,
  CAMERA_PURPOSES,
  type CameraLegInput,
} from "@/lib/agent/feature-types";
import { slugCameraId } from "@/lib/agent/camera-roster";
import { cn } from "@/lib/utils";

const INPUT_CLASS =
  "w-full rounded-md border border-border-default bg-bg-tertiary px-2 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent-primary focus:outline-none";

const URL_RE = /^(rtsp|http):\/\//i;

export function AddIpCameraDialog({
  takenIds,
  saving,
  onClose,
  onAdd,
}: {
  takenIds: ReadonlyArray<string>;
  saving: boolean;
  onClose: () => void;
  onAdd: (leg: CameraLegInput) => void;
}) {
  const t = useTranslations("cameras");

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [orientation, setOrientation] = useState("");
  const [purpose, setPurpose] = useState<string[]>(["feed"]);
  const [touched, setTouched] = useState(false);

  const orientationOptions = useMemo<SelectOption[]>(
    () => [
      { value: "", label: t("orientation.none") },
      ...CAMERA_ORIENTATIONS.map((o) => ({
        value: o,
        label: t(`orientation.${o}`),
      })),
    ],
    [t],
  );

  const nameError = name.trim() === "";
  const urlError = !URL_RE.test(url.trim());

  const togglePurpose = (p: string) =>
    setPurpose((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
    );

  const handleAdd = () => {
    setTouched(true);
    if (nameError || urlError) return;
    const leg: CameraLegInput = {
      id: slugCameraId(name, takenIds),
      source: url.trim(),
      name: name.trim(),
      role: null,
      orientation: orientation === "" ? null : orientation,
      purpose,
      enabled: true,
    };
    onAdd(leg);
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t("addDialog.title")}
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            {t("addDialog.cancel")}
          </Button>
          <Button variant="primary" onClick={handleAdd} disabled={saving}>
            {t("addDialog.add")}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <label className="block space-y-1">
          <span className="text-xs text-text-secondary">
            {t("addDialog.name")}
          </span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("addDialog.namePlaceholder")}
            className={INPUT_CLASS}
          />
          {touched && nameError ? (
            <span className="text-[11px] text-status-error">
              {t("addDialog.nameError")}
            </span>
          ) : null}
        </label>

        <label className="block space-y-1">
          <span className="text-xs text-text-secondary">
            {t("addDialog.url")}
          </span>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={t("addDialog.urlPlaceholder")}
            className={INPUT_CLASS}
          />
          <span className="text-[11px] text-text-tertiary">
            {t("addDialog.urlHint")}
          </span>
          {touched && urlError ? (
            <span className="block text-[11px] text-status-error">
              {t("addDialog.urlError")}
            </span>
          ) : null}
        </label>

        <div className="space-y-1">
          <span className="text-xs text-text-secondary">
            {t("addDialog.orientation")}
          </span>
          <Select
            options={orientationOptions}
            value={orientation}
            onChange={setOrientation}
          />
        </div>

        <div className="space-y-1.5">
          <span className="text-xs text-text-secondary">
            {t("addDialog.purpose")}
          </span>
          <div className="flex flex-wrap gap-1.5">
            {CAMERA_PURPOSES.map((p) => {
              const on = purpose.includes(p);
              return (
                <button
                  key={p}
                  type="button"
                  aria-pressed={on}
                  onClick={() => togglePurpose(p)}
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-xs transition-colors",
                    on
                      ? "border-accent-primary bg-accent-primary/10 text-accent-primary"
                      : "border-border-default bg-bg-secondary text-text-secondary hover:border-border-strong",
                  )}
                >
                  {t(`purpose.${p}`)}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </Modal>
  );
}
