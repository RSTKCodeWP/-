import { describe, it, expect, afterEach, vi } from "vitest";

import { setPluginNotifier, pluginNotify } from "@/lib/plugins/notifier";

afterEach(() => setPluginNotifier(null));

describe("plugin notifier", () => {
  it("is a no-op when no notifier is wired", () => {
    expect(() => pluginNotify("hi", "info")).not.toThrow();
  });

  it("forwards message + status to the wired callback", () => {
    const spy = vi.fn();
    setPluginNotifier(spy);
    pluginNotify("done", "success");
    expect(spy).toHaveBeenCalledWith("done", "success");
  });

  it("stops forwarding after the notifier is unwired", () => {
    const spy = vi.fn();
    setPluginNotifier(spy);
    setPluginNotifier(null);
    pluginNotify("x", "error");
    expect(spy).not.toHaveBeenCalled();
  });
});
