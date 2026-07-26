import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

import { loadPluginBundle } from "@/lib/plugins/bundle-loader";

describe("loadPluginBundle", () => {
  const createSpy = vi.fn(() => "blob:fake-123");
  const revokeSpy = vi.fn();

  beforeEach(() => {
    createSpy.mockClear();
    revokeSpy.mockClear();
    URL.createObjectURL = createSpy as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeSpy as unknown as typeof URL.revokeObjectURL;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches the url and returns a blob url + a working revoke", async () => {
    const blob = new Blob(["<html></html>"], { type: "text/html" });
    const fetchSpy = vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: "OK",
      blob: async () => blob,
    }));
    vi.stubGlobal("fetch", fetchSpy);

    const { blobUrl, revoke } = await loadPluginBundle("https://signed/bundle");

    expect(fetchSpy).toHaveBeenCalledWith("https://signed/bundle");
    expect(createSpy).toHaveBeenCalledWith(blob);
    expect(blobUrl).toBe("blob:fake-123");

    revoke();
    expect(revokeSpy).toHaveBeenCalledWith("blob:fake-123");
  });

  it("throws a clear error on a non-ok response", async () => {
    const fetchSpy = vi.fn(async () => ({
      ok: false,
      status: 404,
      statusText: "Not Found",
      blob: async () => new Blob(),
    }));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(loadPluginBundle("https://signed/missing")).rejects.toThrow(
      /404/,
    );
    expect(createSpy).not.toHaveBeenCalled();
  });
});
