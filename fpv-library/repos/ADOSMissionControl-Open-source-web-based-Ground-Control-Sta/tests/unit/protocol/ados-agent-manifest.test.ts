/**
 * Unit tests for the ADOS Agent firmware manifest client. Verifies the
 * 1-hour cache, per-stack board filtering, board lookup, install
 * resolution, and error propagation when the proxy fails.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  AdosAgentManifest,
  type AdosAgentManifestData,
} from "@/lib/protocol/firmware/ados-agent-manifest";

function buildManifest(): AdosAgentManifestData {
  return {
    schemaVersion: 1,
    agentVersion: "lite-v0.1.3",
    generatedAt: "2026-05-06T00:00:00Z",
    boards: [
      {
        id: "luckfox-pico-zero",
        label: "Luckfox Pico Zero",
        soc: "RV1106G3",
        arch: "armv7-musl",
        stacks: ["ados-drone-agent"],
        installs: {
          "ados-drone-agent": {
            method: "web-flash",
            imageUrl: "https://example.org/lite.img.gz",
            sha256: "deadbeef",
            minisignSignature: "AAAA",
            imageSizeBytes: 50_000_000,
            notes: ["Hold the BOOT button while plugging USB-C"],
          },
        },
        bootrom: { vendorId: 0x2207, productId: 0x110c },
      },
      {
        id: "rpi4b",
        label: "Raspberry Pi 4 Model B",
        soc: "BCM2711",
        arch: "aarch64-glibc",
        stacks: ["ados-drone-agent", "ados-ground-agent"],
        installs: {
          "ados-drone-agent": {
            method: "curl",
            command: "curl -sSL https://example.org/install.sh | sudo bash",
          },
          "ados-ground-agent": {
            method: "curl",
            command:
              "curl -sSL https://example.org/install.sh | sudo bash -s -- --profile ground-station",
            notes: ["Plug in your radio adapter, OLED, and buttons first."],
          },
        },
      },
      {
        id: "pi-zero-2w",
        label: "Raspberry Pi Zero 2 W",
        soc: "BCM2710A1",
        arch: "aarch64-musl",
        stacks: ["ados-drone-agent"],
        installs: {
          "ados-drone-agent": {
            method: "curl",
            command: "curl -sSL https://example.org/install-lite.sh | sudo bash",
          },
        },
      },
    ],
  };
}

function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  const status = init.status ?? 200;
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
}

describe("AdosAgentManifest", () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("getManifest", () => {
    it("fetches the manifest from /api/ados-manifest", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const result = await client.getManifest();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith("/api/ados-manifest");
      expect(result.agentVersion).toBe("lite-v0.1.3");
      expect(result.boards).toHaveLength(3);
    });

    it("caches the manifest for 1 hour and skips re-fetching", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      await client.getManifest();
      await client.getManifest();
      await client.getManifest();

      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it("re-fetches after the cache TTL has elapsed", async () => {
      vi.useFakeTimers();
      mockFetch.mockResolvedValue(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      await client.getManifest();
      // Advance past the 1-hour TTL.
      vi.advanceTimersByTime(60 * 60 * 1000 + 1);
      await client.getManifest();

      expect(mockFetch).toHaveBeenCalledTimes(2);
      vi.useRealTimers();
    });
  });

  describe("getBoardsForStack", () => {
    it("returns boards whose stacks array includes ados-drone-agent", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const boards = await client.getBoardsForStack("ados-drone-agent");
      expect(boards.map((b) => b.id).sort()).toEqual([
        "luckfox-pico-zero",
        "pi-zero-2w",
        "rpi4b",
      ]);
    });

    it("returns only ground-eligible boards for ados-ground-agent", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const boards = await client.getBoardsForStack("ados-ground-agent");
      expect(boards.map((b) => b.id)).toEqual(["rpi4b"]);
    });
  });

  describe("getBoardById", () => {
    it("returns the matching board", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const board = await client.getBoardById("luckfox-pico-zero");
      expect(board).not.toBeNull();
      expect(board?.label).toBe("Luckfox Pico Zero");
      expect(board?.soc).toBe("RV1106G3");
    });

    it("returns null when no board matches the id", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const board = await client.getBoardById("does-not-exist");
      expect(board).toBeNull();
    });
  });

  describe("getInstall", () => {
    it("returns the per-stack install config when present", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const install = await client.getInstall("rpi4b", "ados-ground-agent");
      expect(install).not.toBeNull();
      expect(install?.method).toBe("curl");
      if (install?.method === "curl") {
        expect(install.command).toContain("--profile ground-station");
      }
    });

    it("returns null when the board does not exist", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const install = await client.getInstall("nope", "ados-drone-agent");
      expect(install).toBeNull();
    });

    it("returns null when the board exists but lacks the requested stack", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const install = await client.getInstall(
        "luckfox-pico-zero",
        "ados-ground-agent",
      );
      expect(install).toBeNull();
    });
  });

  describe("getAgentVersion", () => {
    it("returns the manifest agentVersion field", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const version = await client.getAgentVersion();
      expect(version).toBe("lite-v0.1.3");
    });
  });

  describe("clearCache", () => {
    it("forces the next getManifest call to re-fetch", async () => {
      mockFetch.mockResolvedValue(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      await client.getManifest();
      expect(mockFetch).toHaveBeenCalledTimes(1);

      client.clearCache();
      await client.getManifest();
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  describe("error handling", () => {
    it("rejects with a status-derived message when fetch returns 500", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}),
      } as Response);
      const client = new AdosAgentManifest();
      await expect(client.getManifest()).rejects.toThrow(/500/);
    });

    it("rejects with the body error message when the proxy responds non-ok with an error field", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: async () => ({ error: "upstream unavailable" }),
      } as Response);
      const client = new AdosAgentManifest();
      await expect(client.getManifest()).rejects.toThrow("upstream unavailable");
    });

    it("rejects when an ok response carries an error field in the body", async () => {
      mockFetch.mockResolvedValueOnce(
        jsonResponse({ error: "manifest not generated yet" }),
      );
      const client = new AdosAgentManifest();
      await expect(client.getManifest()).rejects.toThrow(
        "manifest not generated yet",
      );
    });

    it("rejects manifests whose schemaVersion is newer than this build supports", async () => {
      const fromTheFuture = { ...buildManifest(), schemaVersion: 2 };
      mockFetch.mockResolvedValueOnce(jsonResponse(fromTheFuture));
      const client = new AdosAgentManifest();
      await expect(client.getManifest()).rejects.toThrow(
        /schema version 2 is newer/i,
      );
    });

    it("accepts manifests at the current schemaVersion", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const result = await client.getManifest();
      expect(result.schemaVersion).toBe(1);
    });
  });

  describe("source field", () => {
    it("exposes the upstream source via getSource() when present", async () => {
      mockFetch.mockResolvedValueOnce(
        jsonResponse({ ...buildManifest(), source: "github" }),
      );
      const client = new AdosAgentManifest();
      const source = await client.getSource();
      expect(source).toBe("github");
    });

    it("exposes the fallback source via getSource() when present", async () => {
      mockFetch.mockResolvedValueOnce(
        jsonResponse({ ...buildManifest(), source: "fallback" }),
      );
      const client = new AdosAgentManifest();
      const source = await client.getSource();
      expect(source).toBe("fallback");
    });

    it("returns null from getSource() when the proxy omits the field", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(buildManifest()));
      const client = new AdosAgentManifest();
      const source = await client.getSource();
      expect(source).toBeNull();
    });
  });
});
