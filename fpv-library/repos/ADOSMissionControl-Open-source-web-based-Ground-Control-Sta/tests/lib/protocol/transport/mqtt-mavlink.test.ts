import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Regression net for the MQTT subscribe contract on both production
 * MQTT clients (the MAVLink transport and the cloud-status bridge).
 *
 * Both must:
 *   - Resubscribe inside the on('connect') handler so subscriptions
 *     survive a broker reconnect (mqtt.js fires 'connect' on every
 *     successful (re)connect; with `clean: true` the broker discards
 *     prior subscriptions).
 *   - Pass an error callback to subscribe() so an ACL deny or other
 *     failure surfaces instead of silently leaving the transport
 *     waiting for frames that never arrive.
 */
function read(path: string): string {
  return readFileSync(resolve(__dirname, path), "utf-8");
}

describe("MqttMavlinkTransport", () => {
  const src = read("../../../../src/lib/protocol/transport/mqtt-mavlink.ts");

  it("subscribes inside the on('connect') handler", () => {
    const idx = src.indexOf("on(\"connect\"");
    expect(idx).toBeGreaterThan(-1);
    const block = src.slice(idx, idx + 600);
    expect(block).toContain("subscribe(");
  });

  it("passes an error callback to subscribe", () => {
    const idx = src.indexOf("subscribe(");
    expect(idx).toBeGreaterThan(-1);
    const block = src.slice(idx, idx + 400);
    expect(block).toMatch(/err: Error \| null/);
  });

  it("emits the error rather than swallowing it", () => {
    const idx = src.indexOf("subscribe(");
    const block = src.slice(idx, idx + 400);
    expect(block).toMatch(/this\.emit\("error"/);
  });
});

describe("MqttBridge", () => {
  const src = read("../../../../src/components/command/MqttBridge.tsx");

  it("subscribes inside the on('connect') handler", () => {
    const idx = src.indexOf('on("connect"');
    expect(idx).toBeGreaterThan(-1);
    const block = src.slice(idx, idx + 800);
    expect(block).toContain("subscribe(");
  });

  it("passes a subscribe error callback", () => {
    expect(src).toMatch(/onSubErr[\s\S]*err: Error \| null/);
  });

  it("logs subscribe failures with diagnostic context", () => {
    expect(src).toContain("[MqttBridge] subscribe failed");
  });
});
