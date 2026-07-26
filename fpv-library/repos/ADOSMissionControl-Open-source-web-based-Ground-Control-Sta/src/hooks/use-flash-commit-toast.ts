/**
 * @module hooks/use-flash-commit-toast
 * @description Shared success/error toast for FC panels that write parameters
 * to flash. Keeps the string copy consistent across the 20+ panels that call
 * `commitToFlash()` from `usePanelParams`.
 *
 * Usage:
 *
 *   const { showFlashResult } = useFlashCommitToast();
 *   async function handleFlash() {
 *     const ok = await commitToFlash();
 *     showFlashResult(ok);
 *   }
 *
 * Override the success copy per panel when the default "persists after reboot"
 * framing is misleading (e.g. panels that only persist a subset):
 *
 *   showFlashResult(ok, { successMessage: "Written to flash" });
 *
 * @license GPL-3.0-only
 */

import { useCallback } from "react";
import { useToast } from "@/components/ui/toast";

const DEFAULT_SUCCESS = "Written to flash — persists after reboot";
const DEFAULT_ERROR = "Failed to write to flash";

export interface FlashResultOptions {
  /** Override the success message for a specific panel. */
  successMessage?: string;
  /** Override the error message for a specific panel. */
  errorMessage?: string;
}

export interface FlashCommitToast {
  /**
   * Show a success or error toast based on the flash-commit result. Pass
   * `ok: true` from `commitToFlash()` to show the success toast; `false`
   * to show the error toast.
   */
  showFlashResult: (ok: boolean, options?: FlashResultOptions) => void;
}

export function useFlashCommitToast(): FlashCommitToast {
  const { toast } = useToast();

  const showFlashResult = useCallback(
    (ok: boolean, options?: FlashResultOptions) => {
      if (ok) {
        toast(options?.successMessage ?? DEFAULT_SUCCESS, "success");
      } else {
        toast(options?.errorMessage ?? DEFAULT_ERROR, "error");
      }
    },
    [toast],
  );

  return { showFlashResult };
}
