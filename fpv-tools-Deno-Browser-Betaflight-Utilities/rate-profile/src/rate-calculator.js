/**
 * Calculate the actual rate based on Betaflight's Actual Rates algorithm
 * @param {number} rcCommand - RC stick input from -1 to 1
 * @param {number} center - Center sensitivity (0-255)
 * @param {number} maxRate - Maximum rate in deg/s (200-2000)
 * @param {number} expo - Expo value (0-100)
 * @returns {number} Rate in degrees per second
 */
export function calculateActualRate(rcCommand, center, maxRate, expo) {
  const rcCommandAbs = Math.abs(rcCommand);

  // Apply expo curve
  let expof;
  if (expo > 0) {
    const expoPower = 3;
    expof = (expo / 100.0) * Math.pow(rcCommandAbs, expoPower) + rcCommandAbs * (1 - expo / 100.0);
  } else {
    expof = rcCommandAbs;
  }

  // Calculate center sensitivity (controls the slope at center stick)
  const centerSensitivity = center * 10; // center is 0-255, multiply by 10 for deg/s

  // Calculate the rate
  const rate = rcCommandAbs * centerSensitivity + expof * (maxRate - centerSensitivity);

  return rcCommand >= 0 ? rate : -rate;
}

/**
 * Normalize a throttle limit type to one of OFF/SCALE/CLIP.
 * Anything unrecognized (including null/undefined) becomes OFF.
 * @param {unknown} value
 * @returns {'OFF'|'SCALE'|'CLIP'}
 */
export function normalizeLimitType(value) {
  const t = String(value ?? "").trim().toUpperCase();
  return t === "SCALE" || t === "CLIP" ? t : "OFF";
}

/**
 * Normalize a throttle limit percent. Non-finite values fall back to 100;
 * valid numbers are clamped to Betaflight's 25..100 range to match both the
 * UI slider bounds and the firmware's documented limits.
 * @param {unknown} value
 * @returns {number}
 */
export function normalizeLimitPercent(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 100;
  return Math.min(100, Math.max(25, n));
}

/**
 * Calculate throttle output with mid point and expo
 * @param {number} input - Throttle stick input from 0 to 1
 * @param {number} midPoint - Mid point value (0-100)
 * @param {number} expo - Expo value (0-100)
 * @param {string} [limitType='OFF'] - Throttle limit mode: 'OFF', 'SCALE', or 'CLIP'
 * @param {number} [limitPercent=100] - Throttle limit percentage (25-100)
 * @returns {number} Throttle output from 0 to 1
 */
export function calculateThrottle(input, midPoint, expo, limitType = "OFF", limitPercent = 100) {
  const mid = midPoint / 100;
  const expoNorm = expo / 100;

  // Apply expo to the entire stick range
  const expof = input * (1 - expoNorm) + Math.pow(input, 3) * expoNorm;

  // Scale the expo curve to pass through the mid point at 50% stick
  let throttle;
  if (expof < 0.5) {
    // Scale 0-0.5 input to 0-mid output
    throttle = expof * 2 * mid;
  } else {
    // Scale 0.5-1.0 input to mid-1.0 output
    throttle = mid + (expof - 0.5) * 2 * (1 - mid);
  }

  const type = normalizeLimitType(limitType);
  const limit = normalizeLimitPercent(limitPercent) / 100;
  if (type === "SCALE") {
    throttle = throttle * limit;
  } else if (type === "CLIP") {
    throttle = Math.min(throttle, limit);
  }

  return throttle;
}
