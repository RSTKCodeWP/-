import { describe, it, expect } from "vitest";
import {
  parseEndpointSpec,
  NetMavlinkTransport,
} from "@/lib/protocol/transport/net-mavlink";

describe("parseEndpointSpec", () => {
  it("parses udp:host:port as listen mode", () => {
    expect(parseEndpointSpec("udp:0.0.0.0:14550")).toEqual({
      proto: "udp",
      host: "0.0.0.0",
      port: 14550,
      mode: "listen",
    });
  });

  it("treats udpin as listen and udpout as target", () => {
    expect(parseEndpointSpec("udpin:0.0.0.0:14550")).toMatchObject({
      proto: "udp",
      mode: "listen",
    });
    expect(parseEndpointSpec("udpout:192.168.1.50:14550")).toEqual({
      proto: "udp",
      host: "192.168.1.50",
      port: 14550,
      mode: "target",
    });
  });

  it("parses tcp:host:port without a mode", () => {
    expect(parseEndpointSpec("tcp:127.0.0.1:5760")).toEqual({
      proto: "tcp",
      host: "127.0.0.1",
      port: 5760,
    });
  });

  it("defaults a bare host:port to udp listen, wildcard host", () => {
    expect(parseEndpointSpec("127.0.0.1:14550")).toMatchObject({
      proto: "udp",
      host: "127.0.0.1",
      port: 14550,
      mode: "listen",
    });
    expect(parseEndpointSpec(":14550")).toMatchObject({
      host: "0.0.0.0",
      port: 14550,
    });
  });

  it("rejects malformed or out-of-range endpoints", () => {
    expect(parseEndpointSpec("")).toBeNull();
    expect(parseEndpointSpec("udp:nohost")).toBeNull();
    expect(parseEndpointSpec("udp:host:99999")).toBeNull();
    expect(parseEndpointSpec("udp:host:0")).toBeNull();
    expect(parseEndpointSpec("udp:host:notaport")).toBeNull();
  });
});

describe("NetMavlinkTransport", () => {
  it("reports udp-proxy / tcp transport types from the proto", () => {
    expect(new NetMavlinkTransport("udp").type).toBe("udp-proxy");
    expect(new NetMavlinkTransport("tcp").type).toBe("tcp");
  });

  it("starts disconnected and refuses send before connect", () => {
    const t = new NetMavlinkTransport("udp");
    expect(t.isConnected).toBe(false);
    expect(() => t.send(new Uint8Array([1, 2, 3]))).toThrow();
  });
});
