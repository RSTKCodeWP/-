/**
 * @license GPL-3.0-only
 * Survey deliverable presets: clicking one writes the target side/front overlap
 * into the survey config.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("next-intl", () => ({ useTranslations: () => (k: string) => k }));
vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn(async () => null),
      setItem: vi.fn(async () => {}),
      removeItem: vi.fn(async () => {}),
    }),
  },
}));

import { SurveyDeliverablePresets } from "@/components/planner/PatternEditor";
import { usePatternStore } from "@/stores/pattern-store";
import { CAMERA_PROFILES, computeLineSpacing, computeTriggerDistance } from "@/lib/patterns/gsd-calculator";

type OverlapConfig = { _sidelap?: number; _frontlap?: number };
type GridConfig = OverlapConfig & { lineSpacing?: number; cameraTriggerDistance?: number };

beforeEach(() => {
  usePatternStore.setState({ surveyConfig: {} });
});

describe("SurveyDeliverablePresets", () => {
  it("renders one button per preset", () => {
    render(<SurveyDeliverablePresets />);
    expect(screen.getByText("presetOrthomosaic")).toBeInTheDocument();
    expect(screen.getByText("presetModel3d")).toBeInTheDocument();
    expect(screen.getByText("presetFastLowDetail")).toBeInTheDocument();
  });

  it("orthomosaic preset writes 70/70", () => {
    render(<SurveyDeliverablePresets />);
    fireEvent.click(screen.getByText("presetOrthomosaic"));
    const cfg = usePatternStore.getState().surveyConfig as OverlapConfig;
    expect(cfg._sidelap).toBe(70);
    expect(cfg._frontlap).toBe(70);
  });

  it("3D-model preset writes 80/80", () => {
    render(<SurveyDeliverablePresets />);
    fireEvent.click(screen.getByText("presetModel3d"));
    const cfg = usePatternStore.getState().surveyConfig as OverlapConfig;
    expect(cfg._sidelap).toBe(80);
    expect(cfg._frontlap).toBe(80);
  });

  it("fast/low-detail preset writes 60/60", () => {
    render(<SurveyDeliverablePresets />);
    fireEvent.click(screen.getByText("presetFastLowDetail"));
    const cfg = usePatternStore.getState().surveyConfig as OverlapConfig;
    expect(cfg._sidelap).toBe(60);
    expect(cfg._frontlap).toBe(60);
  });

  it("recomputes the grid geometry the generator reads when a camera is selected", () => {
    // The generator only reads lineSpacing + cameraTriggerDistance, so a preset
    // that changed overlap without recomputing these would not change the grid.
    const cam = CAMERA_PROFILES[0];
    // Extracted to a const so the extra planner-only `_cameraName` field is not
    // rejected by the object-literal excess-property check.
    const seed = { altitude: 50, _cameraName: cam.name, lineSpacing: 999, cameraTriggerDistance: 999 };
    usePatternStore.setState({ surveyConfig: seed });
    render(<SurveyDeliverablePresets />);
    fireEvent.click(screen.getByText("presetModel3d")); // 80 / 80
    const cfg = usePatternStore.getState().surveyConfig as GridConfig;
    expect(cfg._sidelap).toBe(80);
    expect(cfg.lineSpacing).toBe(Math.round(computeLineSpacing(50, cam, 0.8) * 10) / 10);
    expect(cfg.cameraTriggerDistance).toBe(Math.round(computeTriggerDistance(50, cam, 0.8) * 10) / 10);
    expect(cfg.lineSpacing).not.toBe(999); // proves the grid actually changed
  });
});
