/**
 * DisplayPort OSD store: applies pushed frames into a character grid.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useDisplayPortStore } from "@/stores/displayport-store";
import type { DroneProtocol } from "@/lib/protocol/types";
import type { DisplayPortOp } from "@/lib/protocol/msp/decoders/config/displayport";

function fakeProto() {
  let emit: ((op: DisplayPortOp) => void) | null = null;
  const proto = {
    onDisplayPort: (cb: (op: DisplayPortOp) => void) => {
      emit = cb;
      return () => {
        emit = null;
      };
    },
  } as Partial<DroneProtocol>;
  const send = (op: DisplayPortOp) => {
    if (!emit) throw new Error("not attached");
    emit(op);
  };
  return { proto: proto as DroneProtocol, send };
}

describe("displayport-store", () => {
  beforeEach(() => useDisplayPortStore.getState().detach());

  it("applies pushed ops and commits a frame on DRAW", () => {
    const { proto, send } = fakeProto();
    useDisplayPortStore.getState().attach(proto);
    send({ kind: "clear" });
    send({ kind: "writeString", row: 2, col: 5, attr: 0, fontPage: 0, blink: false, text: "ALT 120" });
    // no committed frame until DRAW_SCREEN
    expect(useDisplayPortStore.getState().lastFrameAt).toBeNull();
    send({ kind: "draw" });
    const st = useDisplayPortStore.getState();
    expect(st.lastFrameAt).not.toBeNull();
    expect(st.lines[2].slice(5, 12)).toBe("ALT 120");
  });

  it("resizes on an OPTIONS frame", () => {
    const { proto, send } = fakeProto();
    useDisplayPortStore.getState().attach(proto);
    send({ kind: "options", fontType: 0, resolution: 2 }); // HD_6022 = 60x22
    expect(useDisplayPortStore.getState().cols).toBe(60);
    expect(useDisplayPortStore.getState().resolutionLabel).toContain("60x22");
  });

  it("attach is inert when the protocol lacks onDisplayPort", () => {
    useDisplayPortStore.getState().attach({} as DroneProtocol);
    expect(useDisplayPortStore.getState().attached).toBe(false);
  });
});
