import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useMissionLog } from "../store/missionLog";
import { MissionLog } from "./MissionLog";

describe("MissionLog", () => {
  beforeEach(() => useMissionLog.getState().reset());

  it("shows a designed empty state with no entries", () => {
    render(<MissionLog />);
    expect(screen.getByText(/no events|mission log/i)).toBeInTheDocument();
  });

  it("renders appended entries with their text", () => {
    useMissionLog.getState().append({ kind: "detection", text: "trk 42 NEW PINPOINT", t: 1000 });
    useMissionLog.getState().append({ kind: "clearance", text: "trk 42 dispatched", t: 2000 });
    render(<MissionLog />);
    expect(screen.getByText(/trk 42 NEW PINPOINT/)).toBeInTheDocument();
    expect(screen.getByText(/trk 42 dispatched/)).toBeInTheDocument();
  });

  it("shows the most recent entry (newest visible)", () => {
    useMissionLog.getState().append({ kind: "link", text: "first", t: 1 });
    useMissionLog.getState().append({ kind: "link", text: "latest", t: 2 });
    render(<MissionLog />);
    expect(screen.getByText("latest")).toBeInTheDocument();
  });
});
