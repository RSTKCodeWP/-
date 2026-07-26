import { describe, expect, it } from "vitest";

import { operationalStyle } from "./style";

/* The operational basemap style (DESIGN-SYSTEM §5.1, CARTO Dark Matter lineage): a
 * desaturated dark chart so colored data is the only figure. Offline by construction —
 * with no PMTiles file it renders a flat operational-color background (no network);
 * with one, it adds the vector basemap via the pmtiles:// protocol. */

describe("operationalStyle", () => {
  it("is a valid MapLibre style v8 with a background layer (always offline-renderable)", () => {
    const s = operationalStyle();
    expect(s.version).toBe(8);
    const bg = s.layers.find((l) => l.id === "background");
    expect(bg).toBeDefined();
    expect(bg!.type).toBe("background");
  });

  it("uses the dark operational land color in night mode, not pure black (halos would vanish on #000)", () => {
    const s = operationalStyle({ theme: "night" });
    const bg = s.layers.find((l) => l.id === "background")!;
    const color = (bg.paint as Record<string, string>)["background-color"];
    expect(color).not.toBe("#000000");
    expect(color).not.toBe("#000");
  });

  it("paints a LIGHT land background in day mode (the default operations theme)", () => {
    const s = operationalStyle({ theme: "day" });
    const bg = s.layers.find((l) => l.id === "background")!;
    const color = (bg.paint as Record<string, string>)["background-color"] as string;
    // light land: a high-value warm gray, clearly not the dark-night land
    const [r, g, b] = color.replace("#", "").match(/.{2}/g)!.map((h) => parseInt(h, 16));
    expect((r + g + b) / 3).toBeGreaterThan(180); // bright paper, not dark chart
  });

  it("declares NO network sources when no PMTiles file is given (offline-by-construction)", () => {
    const s = operationalStyle();
    expect(Object.keys(s.sources)).toHaveLength(0);
  });

  it("adds a pmtiles:// vector source when a basemap file is configured", () => {
    const s = operationalStyle({ pmtilesUrl: "pmtiles://./basemap.pmtiles" });
    expect(s.sources.basemap).toBeDefined();
    expect((s.sources.basemap as { url: string }).url).toBe("pmtiles://./basemap.pmtiles");
  });

  it("never references a remote tile server (no http(s) URLs anywhere)", () => {
    const json = JSON.stringify(operationalStyle({ pmtilesUrl: "pmtiles://./basemap.pmtiles" }));
    expect(json).not.toMatch(/https?:\/\//);
  });

  it("does NOT carry a glyphs key when there are no symbol layers (a glyphs:undefined throws on load)", () => {
    // MapLibre's Style._load requires glyphs to be absent or a string — an explicit
    // `glyphs: undefined` fails "string expected" and aborts the load → blank canvas.
    const s = operationalStyle();
    expect("glyphs" in s).toBe(false);
    const withTiles = operationalStyle({ pmtilesUrl: "pmtiles://./basemap.pmtiles" });
    // if any symbol layer exists, a glyphs STRING must be present; otherwise no glyphs key
    const hasSymbol = withTiles.layers.some((l) => l.type === "symbol");
    if (hasSymbol) {
      expect(typeof withTiles.glyphs).toBe("string");
    } else {
      expect("glyphs" in withTiles).toBe(false);
    }
  });
});
