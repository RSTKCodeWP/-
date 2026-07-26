import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRef } from "react";
import { render, cleanup } from "@testing-library/react";

import {
  PluginIframeHost,
  LIFECYCLE_ACK_TIMEOUT_MS,
  type PluginIframeHostHandle,
} from "@/components/plugins/PluginIframeHost";

interface PostedMessage {
  data: unknown;
  origin: string;
}

function mockContentWindowPostMessage(iframe: HTMLIFrameElement): {
  posted: PostedMessage[];
  ackPause: () => void;
  ackResume: () => void;
} {
  const posted: PostedMessage[] = [];
  // happy-dom does not give us a real contentWindow we can postMessage
  // back from cleanly. Replace contentWindow with a stub that captures
  // outbound messages and lets the test dispatch an ACK by firing a
  // message event sourced from the same stub.
  const fakeWindow = {
    postMessage(data: unknown, origin: string) {
      posted.push({ data, origin });
    },
  } as unknown as Window;
  Object.defineProperty(iframe, "contentWindow", {
    configurable: true,
    get: () => fakeWindow,
  });
  const dispatchAck = (method: "pause" | "resume") => {
    // Synthesize a MessageEvent whose `source` matches contentWindow.
    const ev = new MessageEvent("message", {
      data: { type: "lifecycle-ack", method },
      source: fakeWindow as unknown as MessageEventSource,
    });
    window.dispatchEvent(ev);
  };
  return {
    posted,
    ackPause: () => dispatchAck("pause"),
    ackResume: () => dispatchAck("resume"),
  };
}

describe("PluginIframeHost lifecycle (pause / resume)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("resolves pause() on ACK before the grace window expires", async () => {
    const ref = createRef<PluginIframeHostHandle>();
    const { container } = render(
      <PluginIframeHost
        ref={ref}
        pluginId="com.example.alpha"
        slot="drone.detail.tab"
        bundleUrl="blob:alpha"
        grantedCapabilities={new Set(["ui.slot.drone-detail-tab"])}
        handlers={{}}
      />,
    );
    const iframe = container.querySelector("iframe") as HTMLIFrameElement;
    const { posted, ackPause } = mockContentWindowPostMessage(iframe);

    expect(ref.current).not.toBeNull();
    const pausePromise = ref.current!.pause();

    // The pause message should be in the outbound queue immediately.
    expect(posted).toHaveLength(1);
    expect(posted[0]!.data).toMatchObject({
      type: "lifecycle",
      method: "pause",
    });

    ackPause();
    await pausePromise;
  });

  it("resolves pause() after grace timeout when no ACK arrives", async () => {
    const ref = createRef<PluginIframeHostHandle>();
    const { container } = render(
      <PluginIframeHost
        ref={ref}
        pluginId="com.example.alpha"
        slot="drone.detail.tab"
        bundleUrl="blob:alpha"
        grantedCapabilities={new Set(["ui.slot.drone-detail-tab"])}
        handlers={{}}
      />,
    );
    const iframe = container.querySelector("iframe") as HTMLIFrameElement;
    mockContentWindowPostMessage(iframe);

    const pausePromise = ref.current!.pause();
    // Walk the clock past the grace window; the promise must resolve
    // even without an ACK.
    await vi.advanceTimersByTimeAsync(LIFECYCLE_ACK_TIMEOUT_MS + 10);
    await pausePromise;
  });

  it("resume() posts agentId so the plugin re-subscribes to the right drone", async () => {
    const ref = createRef<PluginIframeHostHandle>();
    const { container } = render(
      <PluginIframeHost
        ref={ref}
        pluginId="com.example.alpha"
        slot="drone.detail.tab"
        bundleUrl="blob:alpha"
        grantedCapabilities={new Set(["ui.slot.drone-detail-tab"])}
        handlers={{}}
        agentId="drone-2"
      />,
    );
    const iframe = container.querySelector("iframe") as HTMLIFrameElement;
    const { posted, ackResume } = mockContentWindowPostMessage(iframe);

    const resumePromise = ref.current!.resume();
    ackResume();
    await resumePromise;

    expect(posted[0]!.data).toMatchObject({
      type: "lifecycle",
      method: "resume",
      agentId: "drone-2",
    });
  });
});
