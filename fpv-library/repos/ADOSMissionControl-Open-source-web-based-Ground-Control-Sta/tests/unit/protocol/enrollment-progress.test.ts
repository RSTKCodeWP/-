import { describe, it, expect } from "vitest";

import {
  tierForElapsed,
  ENROLL_SLOW_MS,
  ENROLL_STUCK_MS,
  ENROLL_FAIL_MS,
} from "@/components/fc/security/EnrollmentProgress";

describe("tierForElapsed", () => {
  it("returns 'normal' below the slow threshold", () => {
    expect(tierForElapsed(0)).toBe("normal");
    expect(tierForElapsed(ENROLL_SLOW_MS - 1)).toBe("normal");
  });

  it("returns 'slow' at the slow threshold", () => {
    expect(tierForElapsed(ENROLL_SLOW_MS)).toBe("slow");
    expect(tierForElapsed(ENROLL_STUCK_MS - 1)).toBe("slow");
  });

  it("returns 'stuck' at the stuck threshold", () => {
    expect(tierForElapsed(ENROLL_STUCK_MS)).toBe("stuck");
    expect(tierForElapsed(ENROLL_FAIL_MS - 1)).toBe("stuck");
  });

  it("returns 'failed' at the fail threshold", () => {
    expect(tierForElapsed(ENROLL_FAIL_MS)).toBe("failed");
    expect(tierForElapsed(ENROLL_FAIL_MS + 1000)).toBe("failed");
  });

  it("returns 'failed' whenever the failed flag is set, regardless of time", () => {
    expect(tierForElapsed(0, true)).toBe("failed");
    expect(tierForElapsed(500, true)).toBe("failed");
  });

  it("thresholds are in the right order", () => {
    expect(ENROLL_SLOW_MS).toBeLessThan(ENROLL_STUCK_MS);
    expect(ENROLL_STUCK_MS).toBeLessThan(ENROLL_FAIL_MS);
  });
});
