/**
 * AP_Periph firmware index parser tests.
 *
 * Covers the HTML row extractor, file kind classifier, vendor
 * grouping helper, client cache behavior, and the embedded fallback
 * path used when the network is unreachable.
 *
 * @license GPL-3.0-only
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApPeriphManifest,
  EMBEDDED_BOARD_LIST,
  classifyBoardFile,
  groupBoardsByVendor,
  isChannelName,
  parseDirectoryIndex,
} from "@/lib/protocol/firmware/ap-periph-manifest";
import { sanitizePath } from "@/lib/protocol/firmware/ap-periph-path";

// ── Fixtures ───────────────────────────────────────────────

const TOP_INDEX = `
<html><head><title>Index</title></head><body>
<h1>Index of /AP_Periph</h1>
<table>
<tr><th><a href="?C=N;O=D">Name</a></th><th>Last modified</th><th>Size</th></tr>
<tr><td><a href="../">Parent Directory</a></td><td></td><td></td></tr>
<tr><td><a href="stable/">stable/</a></td><td>2026-05-01 12:00</td><td>-</td></tr>
<tr><td><a href="beta/">beta/</a></td><td>2026-05-15 12:00</td><td>-</td></tr>
<tr><td><a href="latest/">latest/</a></td><td>2026-05-19 12:00</td><td>-</td></tr>
<tr><td><a href="2026-05/">2026-05/</a></td><td>2026-05-19 12:00</td><td>-</td></tr>
<tr><td><a href="random-folder/">random-folder/</a></td><td>2026-05-19 12:00</td><td>-</td></tr>
</table>
</body></html>
`;

const CHANNEL_INDEX = `
<html><body>
<a href="?C=N;O=D">Name</a>
<a href="../">Parent Directory</a>
<a href="MatekL431-GPS/">MatekL431-GPS/</a>            2026-05-19 12:00    -
<a href="Here4AP/">Here4AP/</a>                       2026-05-19 12:00    -
<a href="HolybroF4_PMU/">HolybroF4_PMU/</a>           2026-05-19 12:00    -
</body></html>
`;

const BOARD_INDEX = `
<html><body>
<a href="../">Parent Directory</a>
<a href="AP_Periph.bin">AP_Periph.bin</a>                              2026-05-19 12:00    245760
<a href="AP_Periph_with_bl.hex">AP_Periph_with_bl.hex</a>              2026-05-19 12:00    512000
<a href="AP_Periph.apj">AP_Periph.apj</a>                              2026-05-19 12:00    246784
<a href="AP_Periph.elf">AP_Periph.elf</a>                              2026-05-19 12:00    1.5M
<a href="firmware-version.txt">firmware-version.txt</a>                2026-05-19 12:00    16
<a href="git-version.txt">git-version.txt</a>                          2026-05-19 12:00    45
<a href="features.txt">features.txt</a>                                2026-05-19 12:00    1024
</body></html>
`;

const VERSION_TXT = "1.6.0\n";
const GIT_TXT = "git commit: abcdef1234567890 on 2026-05-19\n";

// ── parseDirectoryIndex ────────────────────────────────────

describe("parseDirectoryIndex", () => {
  it("extracts channel folders from a top-level index", () => {
    const entries = parseDirectoryIndex(TOP_INDEX);
    const folders = entries.filter((e) => e.isDir).map((e) => e.name);
    expect(folders).toContain("stable");
    expect(folders).toContain("beta");
    expect(folders).toContain("latest");
    expect(folders).toContain("2026-05");
    // The "?C=N;O=D" sort link must be filtered out.
    expect(folders).not.toContain("?C=N;O=D");
  });

  it("extracts board folders from a channel index", () => {
    const entries = parseDirectoryIndex(CHANNEL_INDEX);
    const folders = entries.filter((e) => e.isDir).map((e) => e.name);
    expect(folders).toEqual(expect.arrayContaining(["MatekL431-GPS", "Here4AP", "HolybroF4_PMU"]));
  });

  it("extracts files with sizes from a board index", () => {
    const entries = parseDirectoryIndex(BOARD_INDEX);
    const files = entries.filter((e) => !e.isDir);
    const names = files.map((f) => f.name);
    expect(names).toEqual(
      expect.arrayContaining([
        "AP_Periph.bin",
        "AP_Periph_with_bl.hex",
        "AP_Periph.apj",
        "AP_Periph.elf",
        "firmware-version.txt",
        "git-version.txt",
        "features.txt",
      ]),
    );
    const bin = files.find((f) => f.name === "AP_Periph.bin");
    expect(bin?.sizeBytes).toBe(245760);
    const elf = files.find((f) => f.name === "AP_Periph.elf");
    // 1.5M ≈ 1.5 × 1024 × 1024.
    expect(elf?.sizeBytes).toBe(Math.round(1.5 * 1024 * 1024));
  });

  it("skips parent-directory links", () => {
    const entries = parseDirectoryIndex(BOARD_INDEX);
    expect(entries.find((e) => e.href === "../")).toBeUndefined();
  });
});

// ── classifyBoardFile ──────────────────────────────────────

describe("classifyBoardFile", () => {
  it.each([
    ["AP_Periph.bin", "app"],
    ["AP_Periph_with_bl.hex", "with-bl"],
    ["AP_Periph.apj", "apj"],
    ["AP_Periph.elf", "elf"],
    ["firmware-version.txt", "version-txt"],
    ["features.txt", "features-txt"],
    ["git-version.txt", "git-version-txt"],
    ["something-else.txt", "other"],
  ])("classifies %s as %s", (name, kind) => {
    expect(classifyBoardFile(name)).toBe(kind);
  });
});

// ── isChannelName ──────────────────────────────────────────

describe("isChannelName", () => {
  it("accepts the named channels", () => {
    expect(isChannelName("stable")).toBe(true);
    expect(isChannelName("beta")).toBe(true);
    expect(isChannelName("latest")).toBe(true);
  });

  it("accepts year-month build folders", () => {
    expect(isChannelName("2026-05")).toBe(true);
    expect(isChannelName("2024-11-rc1")).toBe(true);
  });

  it("rejects board folder names", () => {
    expect(isChannelName("MatekL431-GPS")).toBe(false);
    expect(isChannelName("Here4AP")).toBe(false);
  });
});

// ── groupBoardsByVendor ────────────────────────────────────

describe("groupBoardsByVendor", () => {
  it("groups boards by common vendor prefix", () => {
    const sample = [
      "MatekL431-GPS",
      "MatekG474-Periph",
      "Sierra-F405",
      "HolybroF4_PMU",
      "CubeOrange-periph",
      "ARK_GPS",
      "f103-GPS",
      "sitl_periph_gps",
      "AeroFox-Airspeed",
      "VM-L431-Periph-Pico",
      "BotBloxSwitch",
      "WeirdBoard",
    ];

    const grouped = groupBoardsByVendor(sample);
    expect(grouped.get("Matek")).toEqual(expect.arrayContaining(["MatekL431-GPS", "MatekG474-Periph"]));
    expect(grouped.get("Sierra")).toContain("Sierra-F405");
    expect(grouped.get("Holybro")).toContain("HolybroF4_PMU");
    expect(grouped.get("CubePilot")).toContain("CubeOrange-periph");
    expect(grouped.get("ARK")).toContain("ARK_GPS");
    expect(grouped.get("F1/F3/F4 reference")).toContain("f103-GPS");
    expect(grouped.get("SITL")).toContain("sitl_periph_gps");
    expect(grouped.get("AeroFox")).toContain("AeroFox-Airspeed");
    expect(grouped.get("VimDrones")).toContain("VM-L431-Periph-Pico");
    expect(grouped.get("BotBlox")).toContain("BotBloxSwitch");
    expect(grouped.get("Other")).toContain("WeirdBoard");
  });
});

// ── sanitizePath (proxy route) ─────────────────────────────

describe("sanitizePath", () => {
  it("accepts root", () => {
    expect(sanitizePath("")).toBe("");
  });

  it("accepts shallow trailing-slash paths", () => {
    expect(sanitizePath("stable/")).toBe("stable/");
    expect(sanitizePath("stable/MatekL431-GPS/")).toBe("stable/MatekL431-GPS/");
  });

  it("accepts file paths", () => {
    expect(sanitizePath("stable/MatekL431-GPS/AP_Periph.bin")).toBe("stable/MatekL431-GPS/AP_Periph.bin");
  });

  it("rejects traversal", () => {
    expect(sanitizePath("../etc/passwd")).toBeNull();
    expect(sanitizePath("stable/../latest/")).toBeNull();
  });

  it("rejects absolute paths and protocol escapes", () => {
    expect(sanitizePath("/etc/passwd")).toBeNull();
    expect(sanitizePath("http://evil/")).toBeNull();
  });

  it("rejects unknown characters", () => {
    expect(sanitizePath("stable/Mat ek/")).toBeNull();
    expect(sanitizePath("stable/<script>/")).toBeNull();
  });

  it("rejects paths deeper than channel/board/file", () => {
    expect(sanitizePath("a/b/c/d")).toBeNull();
  });
});

// ── ApPeriphManifest client ───────────────────────────────

describe("ApPeriphManifest", () => {
  let client: ApPeriphManifest;
  const realFetch = globalThis.fetch;

  beforeEach(async () => {
    client = new ApPeriphManifest();
    await client.clearCache();
  });

  afterEach(() => {
    globalThis.fetch = realFetch;
    vi.restoreAllMocks();
  });

  function mockFetchByPath(map: Record<string, { ok: boolean; status?: number; body: string; etag?: string }>) {
    const fn = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : (input as Request).url;
      const u = new URL(url, "http://localhost");
      const path = u.searchParams.get("path") ?? "";
      const hit = map[path];
      if (!hit) {
        return new Response("", { status: 404 });
      }
      const headers: Record<string, string> = { "Content-Type": "text/html" };
      if (hit.etag) headers["ETag"] = hit.etag;
      return new Response(hit.body, { status: hit.status ?? (hit.ok ? 200 : 502), headers });
    });
    globalThis.fetch = fn as unknown as typeof fetch;
    return fn;
  }

  it("lists channels from the upstream index", async () => {
    mockFetchByPath({ "": { ok: true, body: TOP_INDEX } });
    const channels = await client.listChannels();
    expect(channels).toEqual(expect.arrayContaining(["stable", "beta", "latest", "2026-05"]));
    // The "random-folder" entry isn't a channel name.
    expect(channels).not.toContain("random-folder");
  });

  it("lists boards from a channel index", async () => {
    mockFetchByPath({ "stable/": { ok: true, body: CHANNEL_INDEX } });
    const boards = await client.listBoards("stable");
    expect(boards).toEqual(expect.arrayContaining(["MatekL431-GPS", "Here4AP", "HolybroF4_PMU"]));
  });

  it("returns a parsed board manifest with version and git commit", async () => {
    mockFetchByPath({
      "stable/MatekL431-GPS/": { ok: true, body: BOARD_INDEX },
      "stable/MatekL431-GPS/firmware-version.txt": { ok: true, body: VERSION_TXT },
      "stable/MatekL431-GPS/git-version.txt": { ok: true, body: GIT_TXT },
    });
    const manifest = await client.getBoardManifest("stable", "MatekL431-GPS");
    expect(manifest.board).toBe("MatekL431-GPS");
    expect(manifest.channel).toBe("stable");
    expect(manifest.version).toBe("1.6.0");
    expect(manifest.gitCommit).toBe("abcdef1234567890");
    expect(manifest.dateLabel).toBe("2026-05-19");
    const app = manifest.files.find((f) => f.kind === "app");
    expect(app?.url).toBe("https://firmware.ardupilot.org/AP_Periph/stable/MatekL431-GPS/AP_Periph.bin");
  });

  it("uses an in-memory cache on repeat reads inside the TTL", async () => {
    const fn = mockFetchByPath({ "stable/": { ok: true, body: CHANNEL_INDEX } });
    await client.listBoards("stable");
    await client.listBoards("stable");
    // Two reads, one network round-trip.
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("falls back to the embedded board list when fetch rejects", async () => {
    globalThis.fetch = vi.fn(async () => {
      throw new Error("network down");
    }) as unknown as typeof fetch;
    const boards = await client.listBoards("stable");
    expect(boards.length).toBeGreaterThan(0);
    expect(boards).toEqual([...EMBEDDED_BOARD_LIST]);
  });

  it("falls back to the embedded channel list when the top index fails", async () => {
    globalThis.fetch = vi.fn(async () => new Response("", { status: 502 })) as unknown as typeof fetch;
    const channels = await client.listChannels();
    expect(channels).toEqual(expect.arrayContaining(["stable", "beta", "latest"]));
  });
});
