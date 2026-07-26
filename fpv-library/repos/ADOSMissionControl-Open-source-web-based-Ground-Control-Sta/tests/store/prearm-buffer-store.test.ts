import { describe, it, expect, beforeEach } from "vitest";
import {
  usePrearmBufferStore,
  type PrearmChannelState,
} from "@/stores/prearm-buffer-store";

describe("prearm-buffer-store", () => {
  beforeEach(() => {
    usePrearmBufferStore.setState({
      buffers: {},
      vision: { status: "unknown", updatedAt: 0 },
    });
  });

  describe("STATUSTEXT buffer", () => {
    it("filters to PreArm: prefix and caps at 20 lines", () => {
      const { push, peek } = usePrearmBufferStore.getState();
      for (let i = 0; i < 25; i++) {
        push("drone-1", `PreArm: line ${i}`);
      }
      push("drone-1", "ignored: not a prearm line");
      const lines = peek("drone-1");
      expect(lines).toHaveLength(20);
      expect(lines[0]).toBe("PreArm: line 5");
      expect(lines[19]).toBe("PreArm: line 24");
    });
  });

  describe("vision channel", () => {
    it("initializes to unknown", () => {
      const vision = usePrearmBufferStore.getState().vision;
      expect(vision.status).toBe("unknown");
      expect(vision.updatedAt).toBe(0);
      expect(vision.reason).toBeUndefined();
    });

    it("setVisionState publishes a new snapshot", () => {
      const next: PrearmChannelState = {
        status: "blocking",
        reason: "Vision companion process is critical. Vision navigation cannot arm.",
        updatedAt: 1_700_000_000_000,
      };
      usePrearmBufferStore.getState().setVisionState(next);
      const vision = usePrearmBufferStore.getState().vision;
      expect(vision).toEqual(next);
    });

    it("is idempotent — identical snapshot does not change the state object", () => {
      const snapshot: PrearmChannelState = {
        status: "ok",
        reason: "Vision navigation: ready",
        updatedAt: 1_700_000_000_000,
      };
      usePrearmBufferStore.getState().setVisionState(snapshot);
      const ref = usePrearmBufferStore.getState().vision;
      usePrearmBufferStore.getState().setVisionState({ ...snapshot });
      expect(usePrearmBufferStore.getState().vision).toBe(ref);
    });

    it("re-publishing the initial unknown snapshot does not throw", () => {
      const init: PrearmChannelState = { status: "unknown", updatedAt: 0 };
      expect(() => {
        usePrearmBufferStore.getState().setVisionState(init);
      }).not.toThrow();
      expect(usePrearmBufferStore.getState().vision.status).toBe("unknown");
    });
  });
});
