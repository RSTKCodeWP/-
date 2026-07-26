import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

const toastSpy = vi.fn();

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: toastSpy }),
}));

import { useFlashCommitToast } from "@/hooks/use-flash-commit-toast";

describe("useFlashCommitToast", () => {
  it("fires the default success toast when ok is true", () => {
    toastSpy.mockClear();
    const { result } = renderHook(() => useFlashCommitToast());
    result.current.showFlashResult(true);
    expect(toastSpy).toHaveBeenCalledWith(
      "Written to flash — persists after reboot",
      "success",
    );
  });

  it("fires the default error toast when ok is false", () => {
    toastSpy.mockClear();
    const { result } = renderHook(() => useFlashCommitToast());
    result.current.showFlashResult(false);
    expect(toastSpy).toHaveBeenCalledWith("Failed to write to flash", "error");
  });

  it("respects a custom successMessage override", () => {
    toastSpy.mockClear();
    const { result } = renderHook(() => useFlashCommitToast());
    result.current.showFlashResult(true, { successMessage: "Saved to flash" });
    expect(toastSpy).toHaveBeenCalledWith("Saved to flash", "success");
  });

  it("respects a custom errorMessage override", () => {
    toastSpy.mockClear();
    const { result } = renderHook(() => useFlashCommitToast());
    result.current.showFlashResult(false, { errorMessage: "Commit rejected" });
    expect(toastSpy).toHaveBeenCalledWith("Commit rejected", "error");
  });

  it("returns a stable callback across re-renders", () => {
    toastSpy.mockClear();
    const { result, rerender } = renderHook(() => useFlashCommitToast());
    const first = result.current.showFlashResult;
    rerender();
    expect(result.current.showFlashResult).toBe(first);
  });
});
