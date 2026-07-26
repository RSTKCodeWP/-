/**
 * @module MissionEditor
 * @description Mission setup form in the right panel — mission name input
 * and drone assignment dropdown.
 * @license GPL-3.0-only
 */
"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { FleetDrone } from "@/lib/types";

interface MissionEditorProps {
  drones: FleetDrone[];
  missionName: string;
  selectedDroneId: string;
  onNameChange: (name: string) => void;
  onDroneChange: (droneId: string) => void;
}

export function MissionEditor({
  drones,
  missionName,
  selectedDroneId,
  onNameChange,
  onDroneChange,
}: MissionEditorProps) {
  const t = useTranslations("planner");
  const availableDrones = drones.filter(
    (d) => d.status === "idle" || d.status === "online"
  );

  const droneOptions = [
    { value: "", label: t("selectDrone") },
    ...availableDrones.map((d) => ({
      value: d.id,
      label: `${d.name} (${Math.round(d.battery?.remaining ?? 0)}%)`,
    })),
  ];

  return (
    <div className="flex flex-col gap-2 px-3 py-2">
      <Input
        label={t("missionName")}
        placeholder={t("missionNamePlaceholder")}
        value={missionName}
        onChange={(e) => onNameChange(e.target.value)}
      />
      <Select
        label={t("assignDrone")}
        options={droneOptions}
        value={selectedDroneId}
        onChange={onDroneChange}
      />
    </div>
  );
}
