/**
 * Browser-side capability token issuer + verifier.
 *
 * Two token formats coexist in this area of the code:
 *
 *   1. v1 pipe-separated string token (this file). Local, in-process.
 *      Mirrors the legacy Python `CapabilityTokenIssuer` on the agent
 *      side. Plugin code never sees the raw token; the host attaches it
 *      to RPC envelopes.
 *
 *   2. JSON-claim base64 token (`./capability-token-claims.ts`). Carried
 *      on cross-process postMessage RPCs, signed by one of three issuers
 *      (cloud operator / agent pairing / local dev). Use that module's
 *      `verifyToken` from the bridge.
 *
 * Wire format for the v1 token (pipe-separated so dotted plugin ids
 * round-trip):
 *   v1|<plugin_id>|<session>|<issued>|<exp>|<hex_caps>|<sig>
 */

const DEFAULT_TTL_MS = 10 * 60 * 1000; // 10 min, matches the agent

export interface CapabilityTokenStruct {
  pluginId: string;
  sessionId: string;
  grantedCaps: ReadonlyArray<string>;
  issuedAt: number;
  expiresAt: number;
  signature: string;
}

export class TokenError extends Error {}

export class CapabilityTokenIssuer {
  private secret: Uint8Array;
  private cryptoKey: Promise<CryptoKey>;

  constructor(secret?: Uint8Array) {
    this.secret = secret ?? randomBytes(32);
    this.cryptoKey = crypto.subtle.importKey(
      "raw",
      this.secret as BufferSource,
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign", "verify"],
    );
  }

  async mint(opts: {
    pluginId: string;
    grantedCaps: ReadonlyArray<string>;
    ttlMs?: number;
  }): Promise<CapabilityTokenStruct> {
    const issuedAt = Date.now();
    const expiresAt = issuedAt + (opts.ttlMs ?? DEFAULT_TTL_MS);
    const sessionId = bytesToHex(randomBytes(8));
    const sig = await this.sign(
      opts.pluginId,
      sessionId,
      issuedAt,
      expiresAt,
      opts.grantedCaps,
    );
    return {
      pluginId: opts.pluginId,
      sessionId,
      grantedCaps: [...opts.grantedCaps].sort(),
      issuedAt,
      expiresAt,
      signature: sig,
    };
  }

  async verify(token: CapabilityTokenStruct): Promise<void> {
    if (token.expiresAt <= Date.now()) {
      throw new TokenError("capability token expired");
    }
    const expected = await this.sign(
      token.pluginId,
      token.sessionId,
      token.issuedAt,
      token.expiresAt,
      token.grantedCaps,
    );
    if (!constantTimeEqual(expected, token.signature)) {
      throw new TokenError("capability token HMAC mismatch");
    }
  }

  private async sign(
    pluginId: string,
    sessionId: string,
    issuedAt: number,
    expiresAt: number,
    caps: ReadonlyArray<string>,
  ): Promise<string> {
    const sorted = [...caps].sort();
    const payload = [
      pluginId,
      sessionId,
      String(issuedAt),
      String(expiresAt),
      sorted.join(","),
    ].join("|");
    const buf = new TextEncoder().encode(payload);
    const key = await this.cryptoKey;
    const sigBytes = await crypto.subtle.sign("HMAC", key, buf as BufferSource);
    return bytesToHex(new Uint8Array(sigBytes));
  }
}

export function encodeToken(t: CapabilityTokenStruct): string {
  const sorted = [...t.grantedCaps].sort().join(",");
  const capsHex = bytesToHex(new TextEncoder().encode(sorted));
  return [
    "v1",
    t.pluginId,
    t.sessionId,
    String(t.issuedAt),
    String(t.expiresAt),
    capsHex,
    t.signature,
  ].join("|");
}

export function decodeToken(encoded: string): CapabilityTokenStruct {
  const parts = encoded.split("|");
  if (parts.length !== 7 || parts[0] !== "v1") {
    throw new TokenError("malformed capability token");
  }
  const issuedAt = Number(parts[3]);
  const expiresAt = Number(parts[4]);
  if (!Number.isFinite(issuedAt) || !Number.isFinite(expiresAt)) {
    throw new TokenError("token timestamp not numeric");
  }
  let capsBlob: string;
  try {
    capsBlob = new TextDecoder().decode(hexToBytes(parts[5]));
  } catch {
    throw new TokenError("token caps blob not hex");
  }
  const grantedCaps = capsBlob
    ? capsBlob.split(",").filter((c) => c.length > 0)
    : [];
  return {
    pluginId: parts[1],
    sessionId: parts[2],
    grantedCaps,
    issuedAt,
    expiresAt,
    signature: parts[6],
  };
}

// Re-export the JSON-claim verifier surface so callers can keep
// importing from a single module if they prefer.
export {
  HKDF_SALT_TOKEN_V1,
  TokenInvalid,
  classifyIssuer,
  deriveAgentTokenSecret,
  importHmacKey,
  importHmacKeyFromBase64,
  parseTokenClaims,
  verifyToken,
} from "./capability-token-claims";
export type {
  ExpectedClaims,
  IssuerKind,
  SecretResolver,
  TokenClaims,
} from "./capability-token-claims";

// ----------------------------------------------------------------------
// Internal helpers
// ----------------------------------------------------------------------

function randomBytes(n: number): Uint8Array {
  const out = new Uint8Array(n);
  crypto.getRandomValues(out);
  return out;
}

function bytesToHex(b: Uint8Array): string {
  let s = "";
  for (let i = 0; i < b.length; i++) {
    s += b[i].toString(16).padStart(2, "0");
  }
  return s;
}

function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) throw new Error("odd hex length");
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    const byte = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    if (Number.isNaN(byte)) throw new Error("non-hex char");
    out[i] = byte;
  }
  return out;
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) {
    mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return mismatch === 0;
}
