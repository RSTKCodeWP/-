const KEY_MAP: [string, string][] = [
  ['pllink_v3_settings', 'argus_settings'],
  ['pllink_v3_waypoints', 'argus_waypoints'],
  ['pllink_port_history', 'argus_port_history'],
  ['pllink_last_port', 'argus_last_port'],
  ['pllink_last_baud', 'argus_last_baud'],
  ['pllink_profiles', 'argus_profiles'],
  ['pllink_locale', 'argus_locale'],
  ['pllink_units', 'argus_units'],
  ['pllink_flights', 'argus_flights'],
  ['pllink_gamepad_map', 'argus_gamepad_map'],
  ['pllink_v3_airspace', 'argus_airspace'],
  ['pllink_ntrip', 'argus_ntrip'],
  ['pllink_ortho_overlays', 'argus_ortho_overlays'],
  ['pllink_annotations', 'argus_annotations'],
  ['pllink_scripts', 'argus_scripts'],
  ['pllink_schedules', 'argus_schedules'],
  ['pllink_dashboard_widgets', 'argus_dashboard_widgets'],
  ['pllink_preflight_config', 'argus_preflight_config'],
  ['pllink_pilot_name', 'argus_pilot_name'],
  ['pllink_v3_role', 'argus_role'],
  ['pllink_video_url', 'argus_video_url'],
];

const DYNAMIC_PREFIXES: [string, string][] = [
  ['pllink_ai_annotations_', 'argus_ai_annotations_'],
  ['pllink_mission_', 'argus_mission_'],
];

export function migrateLocalStorage(): void {
  try {
    for (const [oldKey, newKey] of KEY_MAP) {
      const val = localStorage.getItem(oldKey);
      if (val !== null && localStorage.getItem(newKey) === null) {
        localStorage.setItem(newKey, val);
        localStorage.removeItem(oldKey);
      }
    }
    const toMigrate: [string, string][] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key) continue;
      for (const [oldPfx, newPfx] of DYNAMIC_PREFIXES) {
        if (key.startsWith(oldPfx)) {
          toMigrate.push([key, newPfx + key.slice(oldPfx.length)]);
        }
      }
    }
    for (const [oldKey, newKey] of toMigrate) {
      const val = localStorage.getItem(oldKey);
      if (val !== null && localStorage.getItem(newKey) === null) {
        localStorage.setItem(newKey, val);
        localStorage.removeItem(oldKey);
      }
    }
  } catch {}
}
