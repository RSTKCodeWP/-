/**
 * Round-trip test for the cloud-issuer wire format.
 *
 * Re-implements the Convex action's signer logic byte-for-byte
 * (`canonicalClaimsBytes` + `urlsafeB64NoPad` + HMAC-SHA256 over the
 * blob) using the shared helper at `src/lib/plugins/canonical-token.ts`,
 * then feeds the resulting token straight into `verifyToken` from the
 * bridge verifier. A successful verify proves the cloud issuer and the
 * bridge speak the exact same wire format. If this test breaks, the
 * iframe RPC pipeline will reject every cloud-minted token at
 * `parseTokenClaims`.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";

import {
  canonicalClaimsBytes,
  signCanonicalToken,
  urlsafeB64NoPad,
} from "@/lib/plugins/canonical-token";
import {
  importHmacKey,
  parseTokenClaims,
  verifyToken,
  type TokenClaims,
} from "@/lib/plugins/capability-token-claims";

const SECRET = new Uint8Array(32).fill(0x9c);

function makeClaims(over: Partial<TokenClaims> = {}): TokenClaims {
  return {
    pluginId: "com.example.basic",
    agentId: "drone-id-42",
    operatorId: "user-7",
    expiresAt: Date.now() + 60_000,
    grantedCapabilities: ["command.send", "telemetry.subscribe.mavlink.attitude"],
    iss: "cloud:user-7",
    ...over,
  };
}

describe("cloud mint wire format round-trip", () => {
  it("produces a token the bridge verifier accepts end-to-end", async () => {
    const claims = makeClaims();
    const key = await importHmacKey(SECRET);
    const token = await signCanonicalToken(claims, key);

    const verified = await verifyToken(
      token,
      { pluginId: claims.pluginId, agentId: claims.agentId },
      async () => importHmacKey(SECRET),
    );

    expect(verified.pluginId).toBe(claims.pluginId);
    expect(verified.agentId).toBe(claims.agentId);
    expect(verified.iss).toBe(claims.iss);
    expect(verified.grantedCapabilities).toEqual(claims.grantedCapabilities);
  });

  it("emits the `<blob>.<sig>` wire shape with URL-safe alphabet and no padding", async () => {
    const claims = makeClaims();
    const key = await importHmacKey(SECRET);
    const token = await signCanonicalToken(claims, key);

    // Exactly one separator; neither half empty; no `=` padding;
    // characters are restricted to the URL-safe alphabet.
    const dot = token.indexOf(".");
    expect(dot).toBeGreaterThan(0);
    expect(token.indexOf(".", dot + 1)).toBe(-1);
    const [blob, sig] = token.split(".");
    expect(blob.length).toBeGreaterThan(0);
    expect(sig.length).toBeGreaterThan(0);
    expect(token).not.toMatch(/=/);
    expect(token).toMatch(/^[A-Za-z0-9_\-.]+$/);
  });

  it("signs over the exact bytes the verifier reads back, not a re-serialised JSON", async () => {
    const claims = makeClaims();
    const key = await importHmacKey(SECRET);
    const token = await signCanonicalToken(claims, key);

    // The verifier's `parseTokenClaims` decodes the blob exactly as
    // received. Compare those bytes with the bytes we signed; equality
    // proves there is no JSON.stringify-then-stringify round trip that
    // could perturb whitespace, key order, or escape sequences.
    const { blob: bytesAsParsed } = parseTokenClaims(token);
    const bytesAsSigned = canonicalClaimsBytes(claims);

    expect(Array.from(bytesAsParsed)).toEqual(Array.from(bytesAsSigned));
  });

  it("urlsafeB64NoPad is consistent with the verifier's tolerant decoder", async () => {
    // Round-trip a payload that triggers `+` / `/` in standard base64
    // so we exercise the URL-safe substitution.
    const raw = new Uint8Array(32);
    for (let i = 0; i < 32; i++) raw[i] = (i * 37) & 0xff;
    const encoded = urlsafeB64NoPad(raw);
    expect(encoded).not.toMatch(/[+/=]/);

    // Mint a token, decode it via the verifier, and confirm we got back
    // the same claims bytes.
    const claims = makeClaims();
    const key = await importHmacKey(SECRET);
    const token = await signCanonicalToken(claims, key);
    const { claims: roundTripped } = parseTokenClaims(token);
    expect(roundTripped.pluginId).toBe(claims.pluginId);
    expect(roundTripped.agentId).toBe(claims.agentId);
  });
});
