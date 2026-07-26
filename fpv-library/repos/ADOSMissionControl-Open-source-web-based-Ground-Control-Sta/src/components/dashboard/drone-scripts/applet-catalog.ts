/**
 * @module drone-scripts/applet-catalog
 * @description A small, curated set of first-party ArduPilot Lua starter
 * scripts offered in the Scripts tab. Each entry bundles the `.lua` body and
 * any SCR_USER* parameters it reads, so a one-click "Add to drone" uploads the
 * script and provisions its tunables. These are minimal, self-contained
 * examples written against the stable ArduPilot Lua binding surface
 * (`gcs:send_text`, `battery:*`, `rc:*`, `arming:*`) — intended to be uploaded,
 * run, and adapted, not shipped as production applets.
 * @license GPL-3.0-only
 */

export interface AppletParam {
  /** SCR_USER* parameter name the script reads. */
  name: string;
  /** Value written when the applet is added. */
  value: number;
  /** Human note explaining what the value controls. */
  note: string;
}

export interface AppletCatalogEntry {
  id: string;
  /** Display name. */
  name: string;
  /** FC-side filename (written into APM/scripts/). */
  filename: string;
  /** One-line description of what the script does. */
  description: string;
  /** The `.lua` source uploaded to the FC. */
  body: string;
  /** SCR_USER* tunables set when the applet is added, if any. */
  params?: AppletParam[];
}

const HELLO = `-- ADOS starter script: prints a heartbeat line once a second.
-- Upload smoke test — confirms the scripting VM is running.
function update()
  gcs:send_text(6, "ADOS: scripting is alive")
  return update, 1000
end

return update, 1000
`;

const BATTERY = `-- ADOS starter script: announces pack voltage, warns below SCR_USER1 volts.
local WARN_V = param:get('SCR_USER1') or 14.0

function update()
  local v = battery:voltage(0)
  if v then
    if v < WARN_V then
      gcs:send_text(4, string.format("ADOS: LOW BATTERY %.2fV", v))
    else
      gcs:send_text(6, string.format("ADOS: battery %.2fV", v))
    end
  end
  return update, 5000
end

return update, 5000
`;

const RC_WATCH = `-- ADOS starter script: reports when the watched RC channel (SCR_USER2) goes high.
local CH = math.floor(param:get('SCR_USER2') or 7)
local last = false

function update()
  local pwm = rc:get_pwm(CH)
  if pwm then
    local high = pwm > 1700
    if high ~= last then
      last = high
      gcs:send_text(6, string.format("ADOS: RC%d %s", CH, high and "HIGH" or "low"))
    end
  end
  return update, 200
end

return update, 200
`;

const ARM_GREETER = `-- ADOS starter script: announces when the vehicle arms or disarms.
local was_armed = false

function update()
  local now = arming:is_armed()
  if now ~= was_armed then
    was_armed = now
    gcs:send_text(6, now and "ADOS: armed" or "ADOS: disarmed")
  end
  return update, 500
end

return update, 500
`;

export const APPLET_CATALOG: AppletCatalogEntry[] = [
  {
    id: "hello-world",
    name: "Hello World",
    filename: "ados_hello_world.lua",
    description:
      "Prints a heartbeat message once a second. The simplest way to confirm scripting is enabled and running.",
    body: HELLO,
  },
  {
    id: "battery-announce",
    name: "Battery Announcer",
    filename: "ados_battery_announce.lua",
    description:
      "Announces pack voltage every 5 s and raises a warning below a configurable threshold.",
    body: BATTERY,
    params: [
      { name: "SCR_USER1", value: 14.0, note: "Low-battery warning voltage (V)" },
    ],
  },
  {
    id: "rc-watch",
    name: "RC Channel Watch",
    filename: "ados_rc_watch.lua",
    description:
      "Reports when a chosen RC channel crosses high/low. Useful for wiring up a switch to a custom action.",
    body: RC_WATCH,
    params: [
      { name: "SCR_USER2", value: 7, note: "RC channel number to watch" },
    ],
  },
  {
    id: "arm-greeter",
    name: "Arm/Disarm Greeter",
    filename: "ados_arm_greeter.lua",
    description:
      "Sends a message the moment the vehicle arms or disarms. A template for arm-triggered behaviors.",
    body: ARM_GREETER,
  },
];
