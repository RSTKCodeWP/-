/**
 * Radio link preflight: plain-language checks that the vehicle is configured
 * to work over a MAVLink radio link (ELRS MAVLink mode, mLRS, etc.), with
 * machine-applicable fixes. Evaluated against the downloaded parameter set -
 * pure and unit-testable, no store or IPC dependencies.
 */

export interface PreflightFixParam {
  param: string;
  value: number;
}

export interface PreflightCheck {
  id: 'rc-over-mavlink' | 'rssi-source' | 'firmware-version';
  /** Plain-language check name - no parameter names. */
  title: string;
  /** One sentence: what this means for the user. */
  detail: string;
  status: 'pass' | 'fail' | 'unknown';
  /** Parameter writes that make the check pass, when auto-fixable. */
  fix: PreflightFixParam[] | null;
}

const RC_PROTOCOLS_ALL_BIT = 1;
const RC_PROTOCOLS_MAVLINK_RC_BIT = 65536; // bit 16, ArduPilot 4.6+ (MAVLINK_RADIO enum 15, +1 offset)

/** Parse "ArduRover V4.6.3 (3fc7011a)" style banners. */
export function parseArduPilotVersion(banner: string): { major: number; minor: number } | null {
  const m = banner.match(/Ardu\w+\s+V(\d+)\.(\d+)/i);
  if (!m) return null;
  return { major: parseInt(m[1]!, 10), minor: parseInt(m[2]!, 10) };
}

export function evaluateRadioPreflight(
  getParam: (name: string) => number | undefined,
  firmwareBanner: string | null,
): PreflightCheck[] {
  const checks: PreflightCheck[] = [];

  const rcProtocols = getParam('RC_PROTOCOLS');
  if (rcProtocols === undefined) {
    checks.push({
      id: 'rc-over-mavlink',
      title: 'Stick control over the radio link',
      detail: 'Waiting for parameters to finish loading.',
      status: 'unknown',
      fix: null,
    });
  } else if ((rcProtocols & RC_PROTOCOLS_ALL_BIT) !== 0 || (rcProtocols & RC_PROTOCOLS_MAVLINK_RC_BIT) !== 0) {
    checks.push({
      id: 'rc-over-mavlink',
      title: 'Stick control over the radio link',
      detail: 'The vehicle accepts RC delivered through the MAVLink radio.',
      status: 'pass',
      fix: null,
    });
  } else {
    checks.push({
      id: 'rc-over-mavlink',
      title: 'Stick control over the radio link',
      detail:
        'The vehicle is set to ignore RC arriving over the radio link, so your sticks would do nothing (radio failsafe). The fix keeps your existing receiver protocols enabled.',
      status: 'fail',
      fix: [{ param: 'RC_PROTOCOLS', value: rcProtocols | RC_PROTOCOLS_MAVLINK_RC_BIT }],
    });
  }

  const rssiType = getParam('RSSI_TYPE');
  if (rssiType === undefined) {
    checks.push({
      id: 'rssi-source',
      title: 'Link signal strength readout',
      detail: 'Waiting for parameters to finish loading.',
      status: 'unknown',
      fix: null,
    });
  } else if (rssiType === 5) {
    checks.push({
      id: 'rssi-source',
      title: 'Link signal strength readout',
      detail: 'The vehicle reports radio signal strength from the link itself.',
      status: 'pass',
      fix: null,
    });
  } else {
    checks.push({
      id: 'rssi-source',
      title: 'Link signal strength readout',
      detail: 'Signal strength is not taken from the radio link, so RSSI will read empty or wrong.',
      status: 'fail',
      fix: [{ param: 'RSSI_TYPE', value: 5 }],
    });
  }

  const version = firmwareBanner ? parseArduPilotVersion(firmwareBanner) : null;
  if (!version) {
    checks.push({
      id: 'firmware-version',
      title: 'Firmware supports RC over the radio',
      detail: 'Could not determine the firmware version yet.',
      status: 'unknown',
      fix: null,
    });
  } else if (version.major > 4 || (version.major === 4 && version.minor >= 6)) {
    checks.push({
      id: 'firmware-version',
      title: 'Firmware supports RC over the radio',
      detail: `ArduPilot ${version.major}.${version.minor} supports stick control through a MAVLink radio.`,
      status: 'pass',
      fix: null,
    });
  } else {
    checks.push({
      id: 'firmware-version',
      title: 'Firmware supports RC over the radio',
      detail: `ArduPilot ${version.major}.${version.minor} is too old for stick control over MAVLink - update the flight controller to 4.6 or newer. Telemetry still works.`,
      status: 'fail',
      fix: null,
    });
  }

  return checks;
}
