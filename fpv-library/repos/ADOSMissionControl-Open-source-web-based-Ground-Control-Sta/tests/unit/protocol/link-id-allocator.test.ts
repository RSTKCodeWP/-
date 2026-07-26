import { describe, it, expect } from "vitest";

import {
  allocateLocalLinkId,
  assertValidLinkId,
  isReservedLinkId,
} from "@/lib/protocol/link-id-allocator";

describe("link-id-allocator", () => {

  describe("allocateLocalLinkId", () => {
    it("returns an integer in [1, 254]", () => {
      const id = allocateLocalLinkId("stable-test-device");
      expect(Number.isInteger(id)).toBe(true);
      expect(id).toBeGreaterThanOrEqual(1);
      expect(id).toBeLessThanOrEqual(254);
    });

    it("is deterministic for the same device id", () => {
      const a = allocateLocalLinkId("fixed-device-id-42");
      const b = allocateLocalLinkId("fixed-device-id-42");
      expect(a).toBe(b);
    });

    it("differs for different device ids", () => {
      // Pick two strings known to hash to different buckets under the
      // polynomial rolling hash used by the allocator.
      const a = allocateLocalLinkId("device-one");
      const b = allocateLocalLinkId("device-two");
      expect(a).not.toBe(b);
    });

    it("never returns 0 or 255", () => {
      for (let i = 0; i < 500; i++) {
        const seed = `device-${i}`;
        const id = allocateLocalLinkId(seed);
        expect(isReservedLinkId(id)).toBe(false);
      }
    });
  });

  describe("assertValidLinkId", () => {
    it("accepts 0..255 integers", () => {
      for (const id of [0, 1, 127, 254, 255]) {
        expect(() => assertValidLinkId(id)).not.toThrow();
      }
    });

    it("rejects negative, fractional, and out-of-range values", () => {
      for (const bad of [-1, 256, 300, 1.5, Number.NaN]) {
        expect(() => assertValidLinkId(bad)).toThrow();
      }
    });
  });
});
