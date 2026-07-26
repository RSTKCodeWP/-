/**
 * Offline Ed25519 license key + bundle signature verification.
 * Embeds the Hangar public key so no file system dependency is needed.
 */

import { verify, createPublicKey, createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import type { LicensePayload } from '../../shared/module-types.js';

/**
 * Ed25519 public key in SPKI PEM format - the production Hangar signing key.
 * Rotating it invalidates every issued license.
 */
const PUBLIC_KEY_PEM = `-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA+JX7ieaqUzi1WMTzPrWb3vAeUJOj8cbmFaYuZT5rnZ0=
-----END PUBLIC KEY-----`;

let cachedPublicKey: ReturnType<typeof createPublicKey> | null = null;

function getPublicKey() {
  if (!cachedPublicKey) {
    cachedPublicKey = createPublicKey(PUBLIC_KEY_PEM);
  }
  return cachedPublicKey;
}

/**
 * Verify a license key's Ed25519 signature and decode the payload.
 * Format: ARDUDECK.{base64url(payload)}.{base64url(signature)}
 * (dot separator: base64url alphabet contains `-` and `_` so they cannot split the key)
 */
export function verifyLicenseKey(
  key: string,
): { valid: boolean; payload?: LicensePayload; error?: string } {
  const parts = key.split('.');
  if (parts.length !== 3 || parts[0] !== 'ARDUDECK') {
    return { valid: false, error: 'Invalid key format' };
  }

  const payloadB64 = parts[1]!;
  const sigB64 = parts[2]!;

  try {
    const publicKey = getPublicKey();
    const signature = Buffer.from(sigB64, 'base64url');
    const isValid = verify(null, Buffer.from(payloadB64, 'utf-8'), publicKey, signature);

    if (!isValid) {
      return { valid: false, error: 'Invalid signature' };
    }

    const payloadJson = Buffer.from(payloadB64, 'base64url').toString('utf-8');
    const payload = JSON.parse(payloadJson) as LicensePayload;

    // Check expiration if present
    if (payload.expiresAt) {
      const expiresAt = new Date(payload.expiresAt);
      if (expiresAt < new Date()) {
        return { valid: false, payload, error: 'License has expired' };
      }
    }

    return { valid: true, payload };
  } catch (err) {
    return { valid: false, error: `Verification failed: ${err}` };
  }
}

/**
 * Verify the Ed25519 signature of a downloaded module bundle (ZIP).
 * The signature signs the SHA256 hash of the file.
 */
export function verifyBundleSignature(
  bundlePath: string,
  signature: string,
): boolean {
  try {
    const publicKey = getPublicKey();
    const bundleData = readFileSync(bundlePath);
    const hash = createHash('sha256').update(bundleData).digest();
    const sigBuf = Buffer.from(signature, 'base64url');
    return verify(null, hash, publicKey, sigBuf);
  } catch {
    return false;
  }
}
