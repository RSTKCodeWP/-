import { describe, it, expect } from "vitest";

import {
  CapabilityTokenIssuer,
  TokenError,
  decodeToken,
  encodeToken,
} from "@/lib/plugins/capability-token";

describe("capability token", () => {
  it("mints a token whose signature verifies", async () => {
    const issuer = new CapabilityTokenIssuer();
    const token = await issuer.mint({
      pluginId: "com.example.basic",
      grantedCaps: ["event.publish", "event.subscribe"],
    });
    expect(token.pluginId).toBe("com.example.basic");
    expect(token.grantedCaps).toEqual(["event.publish", "event.subscribe"]);
    await issuer.verify(token);
  });

  it("rejects a token whose caps were tampered with", async () => {
    const issuer = new CapabilityTokenIssuer();
    const token = await issuer.mint({
      pluginId: "com.example.basic",
      grantedCaps: ["event.publish"],
    });
    const tampered = { ...token, grantedCaps: ["event.publish", "command.send"] };
    await expect(issuer.verify(tampered)).rejects.toBeInstanceOf(TokenError);
  });

  it("rejects an expired token", async () => {
    const issuer = new CapabilityTokenIssuer();
    const token = await issuer.mint({
      pluginId: "com.example.basic",
      grantedCaps: ["event.publish"],
      ttlMs: 1,
    });
    await new Promise((r) => setTimeout(r, 5));
    await expect(issuer.verify(token)).rejects.toBeInstanceOf(TokenError);
  });

  it("does not validate tokens minted by a different issuer", async () => {
    const a = new CapabilityTokenIssuer();
    const b = new CapabilityTokenIssuer();
    const token = await a.mint({
      pluginId: "com.example.basic",
      grantedCaps: ["event.publish"],
    });
    await expect(b.verify(token)).rejects.toBeInstanceOf(TokenError);
  });

  it("string-encodes a token whose dotted plugin id round-trips", async () => {
    const issuer = new CapabilityTokenIssuer();
    const token = await issuer.mint({
      pluginId: "com.example.deeply.nested.id",
      grantedCaps: ["event.publish", "event.subscribe"],
    });
    const encoded = encodeToken(token);
    const decoded = decodeToken(encoded);
    expect(decoded).toEqual(token);
    await issuer.verify(decoded);
  });

  it("rejects a malformed token string", () => {
    expect(() => decodeToken("not|a|valid|token")).toThrow(TokenError);
    expect(() =>
      decodeToken("v1|id|s|notanumber|999|deadbeef|deadbeef"),
    ).toThrow(TokenError);
  });
});
