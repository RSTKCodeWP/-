"use client";

import { useState, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useFirmwareCapabilities } from "@/hooks/use-firmware-capabilities";
import { useDroneManager } from "@/stores/drone-manager";
import { useFcKeyboardShortcuts } from "@/hooks/use-fc-keyboard-shortcuts";
import { useFcPanelActionsStore } from "@/stores/fc-panel-actions-store";
import { useSettingsStore } from "@/stores/settings-store";
import { FcDisconnectedPlaceholder } from "@/components/fc/shared/FcDisconnectedPlaceholder";
import { FlashCommitBanner } from "@/components/fc/shared/FlashCommitBanner";
import { RebootRequiredBanner } from "@/components/indicators/RebootRequiredBanner";
import { useParamSafetyStore } from "@/stores/param-safety-store";
import { Puzzle } from "lucide-react";
import { PluginSlot } from "@/components/plugins/PluginSlot";
import { PluginHostProvider } from "@/components/plugins/PluginHostProvider";
import { useFleetPluginContributions } from "@/hooks/use-fleet-plugin-contributions";
import { FC_NAV_ITEMS, type FcNavItem } from "./fc-nav-items";
import { FcPanelRouter } from "./FcPanelRouter";

/** Prefix for a plugin-contributed FC tab's active-panel id, so the panel
 * switch can tell a plugin tab from a built-in FC panel. */
const FC_PLUGIN_PREFIX = "plugin:";

interface DroneConfigureTabProps {
  droneId: string;
  droneName: string;
  isConnected: boolean;
  /** The agent reports an FC on a serial port but the GCS has not finished
   * establishing the live MAVLink session yet. Shows a transient "linking"
   * state instead of the hard "connect a flight controller" placeholder. */
  fcLinking?: boolean;
  /** True when this node is backed by a companion agent (an SBC). Selects the
   * "companion online, no autopilot" empty state over the "connect an FC over
   * USB" one when no FC is present. */
  agentBacked?: boolean;
}

export function DroneConfigureTab({ droneId, droneName, isConnected, fcLinking = false, agentBacked = false }: DroneConfigureTabProps) {
  const t = useTranslations("fcNav");
  const lastActivePanel = useSettingsStore((s) => s.lastActivePanel);
  const setLastActivePanelSetting = useSettingsStore((s) => s.setLastActivePanel);
  const [activePanel, setActivePanel] = useState(lastActivePanel || "outputs");
  const { supports, firmwareType } = useFirmwareCapabilities();
  const getSelectedDrone = useDroneManager((s) => s.getSelectedDrone);
  const vehicleClass = getSelectedDrone()?.vehicleInfo?.vehicleClass;
  const vehicleType = getSelectedDrone()?.vehicleInfo?.vehicleType;

  const sectionLabels: Record<string, string> = {
    Flight: t("flightSection"),
    Safety: t("safetySection"),
    Sensors: t("sensorsSection"),
    Tuning: t("tuningSection"),
    Display: t("displaySection"),
    System: t("systemSection"),
    Security: "Security",
    Debug: t("debugSection"),
    Programming: "Programming",
  };

  const navLabels: Record<string, string> = {
    outputs: t("outputs"),
    receiver: t("receiver"),
    modes: t("flightModes"),
    "aux-modes": t("auxModes"),
    "bf-motors": t("motorsEsc"),
    frame: t("frameSetup"),
    failsafe: t("failsafe"),
    geofence: t("geofence"),
    health: t("healthCheck"),
    sensors: t("sensors"),
    power: t("power"),
    "gps-config": t("gpsConfig"),
    gimbal: t("gimbal"),
    camera: t("camera"),
    pid: t("pidTuning"),
    "rate-profiles": t("rateProfiles"),
    adjustments: t("adjustments"),
    "sensor-graphs": t("sensorGraphs"),
    osd: t("osdEditor"),
    led: t("ledStrip"),
    vtx: t("vtx"),
    ports: t("ports"),
    radio: t("radioConfig"),
    "bf-config": t("configuration"),
    firmware: t("firmwarePanel"),
    cli: t("cli"),
    mavlink: t("mavlinkInspector"),
    blackbox: t("blackbox"),
    debug: t("debugPanel"),
    diagnostics: t("diagnostics"),
    logs: t("logAnalysis"),
    can: "DroneCAN",
    signing: "MAVLink Signing",
    safehome: "Safehome",
    geozone: "Geozones",
    "inav-nav-config": "Navigation Config",
    "inav-mission": "iNav Mission",
    "inav-mixer-profile": "Mixer Profiles",
    "inav-output-mapping": "Output Mapping",
    "inav-servos": "Servos (iNav)",
    "inav-failsafe": "Failsafe (iNav)",
    "inav-battery-profile": "Battery Profiles",
    "inav-temp-sensors": "Temp Sensors",
    "inav-control-profile": "Control Profiles",
    "inav-mc-braking": "MC Braking",
    "inav-rate-dynamics": "Rate Dynamics",
    "inav-ez-tune": "EZ Tune",
    "inav-fw-approach": "FW Approach",
    "inav-osd": "OSD (iNav)",
    "inav-custom-osd": "Custom OSD",
    "inav-logic-conditions": "Logic Conditions",
    "inav-global-variables": "Global Variables",
    "inav-programming-pid": "Programming PIDs",
    "inav-nav-pid": "Nav PID",
  };

  useEffect(() => {
    setLastActivePanelSetting(activePanel);
  }, [activePanel, setLastActivePanelSetting]);

  const saveToRam = useFcPanelActionsStore((s) => s.saveToRam);
  const refresh = useFcPanelActionsStore((s) => s.refresh);
  useFcKeyboardShortcuts(saveToRam ?? undefined, refresh ?? undefined);

  const rebootRequiredParams = useParamSafetyStore((s) => s.rebootRequiredParams);
  const rebootParamsList = useMemo(() => Array.from(rebootRequiredParams), [rebootRequiredParams]);

  const visibleItems = useMemo(
    () =>
      FC_NAV_ITEMS.filter(
        (item) =>
          (!item.requiredCapability || supports(item.requiredCapability)) &&
          (!item.vehicleClasses ||
            (vehicleClass != null && item.vehicleClasses.includes(vehicleClass))) &&
          (item.requiredVehicleType == null ||
            vehicleType === item.requiredVehicleType) &&
          (!item.excludeFirmware ||
            firmwareType == null ||
            !item.excludeFirmware.includes(firmwareType)),
      ),
    [supports, vehicleClass, vehicleType, firmwareType],
  );

  const sections = useMemo(() => {
    const map = new Map<string, FcNavItem[]>();
    for (const item of visibleItems) {
      const s = item.section ?? "Other";
      if (!map.has(s)) map.set(s, []);
      map.get(s)!.push(item);
    }
    return map;
  }, [visibleItems]);

  // Fleet `fc.tab` contributions: a GCS-level plugin can add a tab to the FC
  // Configure nav for any drone. Each renders its sandboxed iframe in the
  // panel area instead of a built-in FC panel. Inert when none contribute.
  const fcPluginTabs = useFleetPluginContributions("fc.tab");
  const isPluginPanel = activePanel.startsWith(FC_PLUGIN_PREFIX);
  const activePluginPanelId = isPluginPanel
    ? activePanel.slice(FC_PLUGIN_PREFIX.length)
    : null;

  const firmwareLabel = firmwareType
    ? ({
        "ardupilot-copter": "ArduCopter",
        "ardupilot-plane": "ArduPlane",
        "ardupilot-rover": "ArduRover",
        "ardupilot-sub": "ArduSub",
        px4: "PX4",
        betaflight: "Betaflight",
        inav: "iNav",
        unknown: "Unknown",
      } as Record<string, string>)[firmwareType] ?? firmwareType
    : null;

  useEffect(() => {
    // Reset to the first built-in only when the active panel is neither a
    // visible built-in NOR a live plugin tab. A plugin tab's active id is
    // `plugin:<panelId>` — it's never in the built-in nav (`visibleItems`), so
    // without the plugin check this effect would instantly reset the selection
    // and a plugin (e.g. the demo FC tab) would just flicker and never open.
    // A *stale* plugin id (its contribution is gone) still falls through to the
    // reset so the panel never renders an empty plugin slot.
    const isBuiltinVisible = visibleItems.some((i) => i.id === activePanel);
    const isLivePluginTab = fcPluginTabs.some(
      (c) => `${FC_PLUGIN_PREFIX}${c.panelId}` === activePanel,
    );
    if (!isBuiltinVisible && !isLivePluginTab && visibleItems.length > 0) {
      setActivePanel(visibleItems[0].id);
    }
  }, [visibleItems, activePanel, fcPluginTabs]);

  return (
    <div className="flex-1 flex min-h-0 overflow-hidden">
      <nav className="w-[200px] border-r border-border-default bg-bg-secondary flex-shrink-0 overflow-y-auto">
        <div className="px-3 py-3 border-b border-border-default">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            {t("flightController")}
          </h2>
          {firmwareLabel && (
            <span className="mt-1 inline-block text-[10px] font-medium px-1.5 py-0.5 rounded bg-accent-primary/15 text-accent-primary">
              {firmwareLabel}
            </span>
          )}
          {firmwareType === "px4" && (
            <span className="mt-1 block text-[10px] text-text-tertiary">
              Some panels (OSD, LED) are not available for PX4.
            </span>
          )}
          {firmwareType === "betaflight" && (
            <span className="mt-1 block text-[10px] text-text-tertiary">
              Betaflight firmware. Some panels differ from ArduPilot.
            </span>
          )}
        </div>
        <div className="flex flex-col py-1">
          {[...sections.entries()].map(([section, items]) => (
            <div key={section}>
              <div className="px-3 pt-3 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                  {sectionLabels[section] ?? section}
                </span>
              </div>
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => isConnected && setActivePanel(item.id)}
                  disabled={!isConnected}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 text-xs text-left transition-colors cursor-pointer w-full",
                    !isConnected && "opacity-40 cursor-not-allowed",
                    isConnected && activePanel === item.id
                      ? "text-accent-primary bg-accent-primary/10 border-l-2 border-l-accent-primary"
                      : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary border-l-2 border-l-transparent",
                    !isConnected && "hover:bg-transparent hover:text-text-secondary",
                  )}
                >
                  {item.icon}
                  {(firmwareType && item.labelOverride?.[firmwareType]) ?? navLabels[item.id] ?? item.label}
                </button>
              ))}
            </div>
          ))}

          {/* Plugin-contributed FC tabs (fleet fc.tab slot). Appended below the
              built-in sections; one nav button per contribution. */}
          {fcPluginTabs.length > 0 && (
            <div>
              <div className="px-3 pt-3 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                  {t("extensionsSection")}
                </span>
              </div>
              {fcPluginTabs.map((c) => {
                const panelId = `${FC_PLUGIN_PREFIX}${c.panelId}`;
                return (
                  <button
                    key={panelId}
                    onClick={() => isConnected && setActivePanel(panelId)}
                    disabled={!isConnected}
                    className={cn(
                      "flex items-center gap-2 px-3 py-1.5 text-xs text-left transition-colors cursor-pointer w-full",
                      !isConnected && "opacity-40 cursor-not-allowed",
                      isConnected && activePanel === panelId
                        ? "text-accent-primary bg-accent-primary/10 border-l-2 border-l-accent-primary"
                        : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary border-l-2 border-l-transparent",
                      !isConnected && "hover:bg-transparent hover:text-text-secondary",
                    )}
                  >
                    <Puzzle size={14} />
                    {c.title ?? c.panelId}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </nav>

      <div className="flex-1 min-w-0 min-h-0 overflow-hidden flex flex-col">
        {!isConnected ? (
          fcLinking ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-6">
              <div className="h-6 w-6 rounded-full border-2 border-accent-primary/30 border-t-accent-primary animate-spin" />
              <p className="text-sm text-text-primary">{t("linkingTitle")}</p>
              <p className="text-xs text-text-tertiary max-w-sm">
                {t("linkingHint")}
              </p>
            </div>
          ) : (
            <FcDisconnectedPlaceholder droneName={droneName} agentBacked={agentBacked} />
          )
        ) : isPluginPanel ? (
          // Render the active plugin FC tab's sandboxed iframe. The slot host
          // mounts a fleet-scoped provider over the single active contribution.
          <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
            <FcPluginPanel
              activePanelId={activePluginPanelId}
              fallback={<FcPanelRouter activePanel={activePanel} firmwareType={firmwareType} />}
            />
          </div>
        ) : (
          <>
            <FlashCommitBanner />
            <RebootRequiredBanner rebootParams={rebootParamsList} />
            <FcPanelRouter activePanel={activePanel} firmwareType={firmwareType} />
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Renders the active plugin-contributed FC tab's iframe. Filters the fleet
 * `fc.tab` contributions to the active panel and mounts a fleet-scoped
 * provider + slot over the single match. Falls back when the active id no
 * longer resolves to a contribution (e.g. the plugin was removed).
 */
function FcPluginPanel({
  activePanelId,
  fallback,
}: {
  activePanelId: string | null;
  fallback: React.ReactNode;
}) {
  const contributions = useFleetPluginContributions("fc.tab");
  const active = useMemo(
    () => contributions.filter((c) => c.panelId === activePanelId),
    [contributions, activePanelId],
  );
  if (active.length === 0) return <>{fallback}</>;
  return (
    <PluginHostProvider deviceId={null} contributions={active}>
      <PluginSlot
        name="fc.tab"
        contributions={active}
        className="flex-1 min-h-0 flex flex-col"
        iframeClassName="flex-1 w-full border-0"
      />
    </PluginHostProvider>
  );
}
