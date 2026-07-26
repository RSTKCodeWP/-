import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  PluginAgentClient,
  PluginAgentError,
} from "@/lib/agent/plugin-client";

const ORIGINAL_FETCH = globalThis.fetch;

function mockFetch(impl: typeof fetch) {
  globalThis.fetch = impl as typeof fetch;
}

afterEach(() => {
  globalThis.fetch = ORIGINAL_FETCH;
});

describe("PluginAgentClient", () => {
  let client: PluginAgentClient;
  beforeEach(() => {
    client = new PluginAgentClient("http://agent.local", "k1");
  });

  it("sends the api key header on list", async () => {
    let captured: Headers | undefined;
    mockFetch(async (input, init) => {
      captured = new Headers(init?.headers);
      return new Response(JSON.stringify({ installs: [] }), { status: 200 });
    });
    await client.list();
    expect(captured?.get("X-ADOS-Key")).toBe("k1");
  });

  it("uploads as multipart on install", async () => {
    let bodyType: string | undefined;
    let methodSeen: string | undefined;
    mockFetch(async (_input, init) => {
      methodSeen = init?.method;
      const body = init?.body;
      bodyType = body && typeof body === "object" ? body.constructor.name : "";
      return new Response(
        JSON.stringify({
          ok: true,
          plugin_id: "com.example.basic",
          version: "0.1.0",
          signer_id: null,
          risk: "low",
          permissions_requested: ["event.publish"],
        }),
        { status: 200 },
      );
    });
    const file = new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], "x.adosplug");
    const result = await client.install(file);
    expect(methodSeen).toBe("POST");
    expect(bodyType).toBe("FormData");
    expect(result.plugin_id).toBe("com.example.basic");
  });

  it("decodes the structured error envelope into PluginAgentError", async () => {
    mockFetch(
      async () =>
        new Response(
          JSON.stringify({
            ok: false,
            code: 11,
            kind: "permission_deny",
            detail: "plugin com.example.basic did not declare permission vehicle.command",
          }),
          { status: 400 },
        ),
    );
    await expect(client.grant("com.example.basic", "vehicle.command")).rejects.toEqual(
      expect.objectContaining({
        code: 11,
        kind: "permission_deny",
      }),
    );
  });

  it("falls back to transport_error on non-JSON failure body", async () => {
    mockFetch(async () => new Response("nope", { status: 500 }));
    await expect(client.enable("com.example.basic")).rejects.toBeInstanceOf(
      PluginAgentError,
    );
  });

  it("encodes plugin id in the URL", async () => {
    let captured: string | URL | Request | undefined;
    mockFetch(async (input) => {
      captured = input;
      return new Response("{}", { status: 200 });
    });
    await client.disable("com.example.has slashes/and+chars");
    expect(String(captured)).toContain(
      encodeURIComponent("com.example.has slashes/and+chars"),
    );
  });

  it("appends keep_data=1 only when requested", async () => {
    const seen: string[] = [];
    mockFetch(async (input) => {
      seen.push(String(input));
      return new Response("{}", { status: 200 });
    });
    await client.remove("com.example.basic");
    await client.remove("com.example.basic", { keepData: true });
    expect(seen[0]).not.toContain("keep_data");
    expect(seen[1]).toContain("keep_data=1");
  });
});
