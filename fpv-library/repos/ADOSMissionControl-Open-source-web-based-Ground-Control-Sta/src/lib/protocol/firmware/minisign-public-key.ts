/**
 * Vendored minisign public key for the lite agent's release artifacts and
 * the Blake2b-prehashed Ed25519 verifier the Flash Tool uses before it
 * touches the device's eMMC.
 *
 * The public key is duplicated from the release-artifact verifier in
 * scripts/install-lite.sh. The two MUST stay in sync — rotation is a code
 * change in both places, never a runtime knob.
 *
 * @module protocol/firmware/minisign-public-key
 */
import { blake2b } from "@noble/hashes/blake2";

/**
 * Base64-encoded minisign public key for the lite-agent release pipeline.
 * Format: 2-byte algorithm marker ("Ed") + 8-byte key id + 32-byte Ed25519
 * public key, all base64-encoded.
 */
export const LITE_AGENT_MINISIGN_PUBLIC_KEY =
  "RWR+yLdssguv/iqfINd5cFsiC5+cUKLGvFggEfBS0O94KLWcjAvIczE7";

/** Short fingerprint shown alongside release notes for operator verification. */
export const LITE_AGENT_MINISIGN_PUBLIC_KEY_FINGERPRINT = "FEAF0BB26CB7C87E";

const SIGALG_LEGACY = "Ed";
const SIGALG_PREHASHED = "ED";

function base64Decode(input: string): Uint8Array {
  const cleaned = input.replace(/\s+/g, "");
  const binary = atob(cleaned);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function asciiTwo(bytes: Uint8Array, offset: number): string {
  return (
    String.fromCharCode(bytes[offset]) + String.fromCharCode(bytes[offset + 1])
  );
}

interface ParsedKey {
  algorithm: string;
  keyId: Uint8Array;
  rawKey: Uint8Array;
}

interface ParsedSignature {
  algorithm: string;
  keyId: Uint8Array;
  signature: Uint8Array;
}

function parsePublicKey(b64: string): ParsedKey {
  const bytes = base64Decode(b64);
  if (bytes.byteLength !== 42) {
    throw new Error(
      `minisign public key has unexpected length ${bytes.byteLength} (expected 42).`,
    );
  }
  return {
    algorithm: asciiTwo(bytes, 0),
    keyId: bytes.slice(2, 10),
    rawKey: bytes.slice(10, 42),
  };
}

function parseSignature(b64: string): ParsedSignature {
  const bytes = base64Decode(b64);
  if (bytes.byteLength !== 74) {
    throw new Error(
      `minisign signature has unexpected length ${bytes.byteLength} (expected 74).`,
    );
  }
  return {
    algorithm: asciiTwo(bytes, 0),
    keyId: bytes.slice(2, 10),
    signature: bytes.slice(10, 74),
  };
}

function constantTimeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.byteLength !== b.byteLength) return false;
  let diff = 0;
  for (let i = 0; i < a.byteLength; i++) {
    diff |= a[i] ^ b[i];
  }
  return diff === 0;
}

let importedKey: CryptoKey | null = null;

async function getEd25519Key(rawKey: Uint8Array): Promise<CryptoKey> {
  if (importedKey) return importedKey;
  const buf = new ArrayBuffer(rawKey.byteLength);
  new Uint8Array(buf).set(rawKey);
  importedKey = await crypto.subtle.importKey(
    "raw",
    buf,
    { name: "Ed25519" },
    false,
    ["verify"],
  );
  return importedKey;
}

/**
 * Verify a minisign signature over the given image bytes against the
 * vendored lite-agent public key. Returns true on success, throws with a
 * specific reason otherwise (caller surfaces the message to the user).
 *
 * Handles both signature algorithms minisign emits:
 *   - "Ed"  (legacy)     — Ed25519 over the raw message bytes
 *   - "ED"  (prehashed)  — Ed25519 over Blake2b-512(message)
 *
 * The browser must support Web Crypto Ed25519. We already gate the Flash
 * Tool to Chromium-family browsers for WebUSB; Ed25519 in subtle.verify
 * is in the same support tier.
 */
export async function verifyLiteAgentImageSignature(
  image: Uint8Array,
  signatureBase64: string,
): Promise<true> {
  if (!signatureBase64) {
    throw new Error("Manifest is missing a minisign signature for this image.");
  }

  const subtle = globalThis.crypto?.subtle;
  if (!subtle || typeof subtle.verify !== "function") {
    throw new Error(
      "Web Crypto subtle.verify is unavailable. Open Mission Control in Chrome or Edge.",
    );
  }

  const pubkey = parsePublicKey(LITE_AGENT_MINISIGN_PUBLIC_KEY);
  const sig = parseSignature(signatureBase64);

  if (!constantTimeEqual(pubkey.keyId, sig.keyId)) {
    throw new Error(
      "Signature key id does not match the vendored lite-agent public key.",
    );
  }

  let signedBytes: Uint8Array;
  if (sig.algorithm === SIGALG_PREHASHED) {
    signedBytes = blake2b(image, { dkLen: 64 });
  } else if (sig.algorithm === SIGALG_LEGACY) {
    signedBytes = image;
  } else {
    throw new Error(
      `Unknown minisign signature algorithm "${sig.algorithm}" (expected "Ed" or "ED").`,
    );
  }

  const sigBuf = new ArrayBuffer(sig.signature.byteLength);
  new Uint8Array(sigBuf).set(sig.signature);
  const dataBuf = new ArrayBuffer(signedBytes.byteLength);
  new Uint8Array(dataBuf).set(signedBytes);

  const key = await getEd25519Key(pubkey.rawKey);
  let ok: boolean;
  try {
    ok = await subtle.verify({ name: "Ed25519" }, key, sigBuf, dataBuf);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    throw new Error(
      `Ed25519 verification failed in the browser crypto layer: ${msg}.`,
    );
  }
  if (!ok) {
    throw new Error(
      "Image signature did not verify against the lite-agent public key. Refusing to flash.",
    );
  }
  return true;
}
