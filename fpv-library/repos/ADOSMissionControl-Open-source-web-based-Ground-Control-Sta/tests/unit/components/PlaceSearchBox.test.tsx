import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

vi.mock("next-intl", () => ({ useTranslations: () => (k: string) => k }));

const toastSpy = vi.fn();
vi.mock("@/components/ui/toast", () => ({ useToast: () => ({ toast: toastSpy }) }));

const forwardGeocodeSpy = vi.fn();
vi.mock("@/lib/geocoding/forward", () => ({ forwardGeocode: (...a: unknown[]) => forwardGeocodeSpy(...a) }));

let demo = false;
vi.mock("@/lib/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/utils")>()),
  isDemoMode: () => demo,
}));

// The planner store is persisted via indexedDBStorage; stub the backing store.
vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn().mockResolvedValue(null),
      setItem: vi.fn().mockResolvedValue(undefined),
      removeItem: vi.fn().mockResolvedValue(undefined),
    }),
  },
}));

import { PlaceSearchBox } from "@/components/planner/PlaceSearchBox";
import { usePlannerStore } from "@/stores/planner-store";

function typeAndEnter(value: string) {
  const input = screen.getByPlaceholderText("searchPlaceholder");
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: "Enter" });
}

describe("PlaceSearchBox", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    demo = false;
    usePlannerStore.setState({ panRequest: null });
    cleanup();
  });

  it("pans to a parsed coordinate pair without hitting the network", () => {
    render(<PlaceSearchBox />);
    typeAndEnter("12.97, 77.59");
    const pan = usePlannerStore.getState().panRequest;
    expect(pan?.lat).toBeCloseTo(12.97);
    expect(pan?.lon).toBeCloseTo(77.59);
    expect(forwardGeocodeSpy).not.toHaveBeenCalled();
  });

  it("geocodes a place name and pans to a single result", async () => {
    forwardGeocodeSpy.mockResolvedValue([{ name: "Bengaluru", lat: 12.9716, lon: 77.5946 }]);
    render(<PlaceSearchBox />);
    typeAndEnter("Bengaluru");
    await waitFor(() => {
      const pan = usePlannerStore.getState().panRequest;
      expect(pan?.lat).toBeCloseTo(12.9716);
    });
    expect(forwardGeocodeSpy).toHaveBeenCalledWith("Bengaluru", 5);
  });

  it("shows a picker for multiple results and pans on selection", async () => {
    forwardGeocodeSpy.mockResolvedValue([
      { name: "Springfield, IL", lat: 39.8, lon: -89.6 },
      { name: "Springfield, MA", lat: 42.1, lon: -72.6 },
    ]);
    render(<PlaceSearchBox />);
    typeAndEnter("Springfield");
    const option = await screen.findByText("Springfield, MA");
    fireEvent.click(option);
    const pan = usePlannerStore.getState().panRequest;
    expect(pan?.lat).toBeCloseTo(42.1);
  });

  it("does not hit the network in demo mode", () => {
    demo = true;
    render(<PlaceSearchBox />);
    typeAndEnter("London");
    expect(forwardGeocodeSpy).not.toHaveBeenCalled();
    expect(toastSpy).toHaveBeenCalled();
    expect(usePlannerStore.getState().panRequest).toBeNull();
  });
});
