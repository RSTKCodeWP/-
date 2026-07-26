"use client";

/**
 * @module components/fc/security/signing/use-signing-actions
 * @description Extracted state and action handlers for the signing panel.
 *
 * Owns the lifecycle of enrollment, disable, rotate, require-toggle, and the
 * cloud-sync toggle. Also runs the on-mount effect that pulls capability and
 * key presence from the agent.
 */

import { useCallback, useEffect, useState } from "react";
import { useConvex } from "convex/react";
import type { ConvexReactClient } from "convex/react";

import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useDroneManager } from "@/stores/drone-manager";
import { useSigningStore } from "@/stores/signing-store";
import { useAuthStore } from "@/stores/auth-store";
import {
  clear as clearKeystoreRecord,
  getRecord,
  importAndStore,
} from "@/lib/protocol/signing-keystore";
import {
  generateRandomKey,
  keyBytesToHex,
  zeroize,
} from "@/lib/protocol/mavlink-signer";
import { allocateLocalLinkId } from "@/lib/protocol/link-id-allocator";
import {
  isCloudSigningKeySyncEnabled,
  removeCloudKey,
  uploadKey,
} from "@/lib/api/signing-cloud-sync";
import { emitSigningEvent } from "@/lib/api/signing-events";
import { setCloudSyncIntent } from "@/lib/protocol/signing-prefs";
import { ENROLL_FAIL_MS } from "../EnrollmentProgress";
import { useCloudRowSync } from "./use-cloud-row-sync";

export interface SigningActions {
  // Local UI state
  busy: boolean;
  error: string | null;
  enrollStartedAt: number | null;
  enrollFailed: boolean;
  exportOpen: boolean;
  importOpen: boolean;
  cloudSyncBusy: boolean;
  cloudSyncError: string | null;
  // Cloud sync flags
  cloudRowPresent: boolean;
  cloudSyncIntent: boolean;
  // Auth flags surfaced for the UI
  isAuthenticated: boolean;
  authLoading: boolean;
  // UI setters
  setExportOpen: (open: boolean) => void;
  setImportOpen: (open: boolean) => void;
  setEnrollStartedAt: (at: number | null) => void;
  setEnrollFailed: (failed: boolean) => void;
  setBusy: (busy: boolean) => void;
  // Action handlers
  handleEnable: () => Promise<void>;
  handleDisable: () => Promise<void>;
  handleRotate: () => Promise<void>;
  handleRequireToggle: () => Promise<void>;
  handleCloudSyncToggle: () => Promise<void>;
}

export function useSigningActions(droneId: string): SigningActions {
  const client = useAgentConnectionStore((s) => s.client);

  const state = useSigningStore((s) => s.drones[droneId]);
  const setCapability = useSigningStore((s) => s.setCapability);
  const setBrowserKey = useSigningStore((s) => s.setBrowserKey);
  const setRequireOnFc = useSigningStore((s) => s.setRequireOnFc);
  const setEnrollmentState = useSigningStore((s) => s.setEnrollmentState);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrollStartedAt, setEnrollStartedAt] = useState<number | null>(null);
  const [enrollFailed, setEnrollFailed] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [cloudSyncBusy, setCloudSyncBusy] = useState(false);
  const [cloudSyncError, setCloudSyncError] = useState<string | null>(null);

  const convexClient: ConvexReactClient = useConvex();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const authLoading = useAuthStore((s) => s.isLoading);

  // cloudSyncIntent is the persisted "I want cloud sync" preference; it
  // and cloudRowPresent can disagree. Operator flips intent on -> next
  // rotation uploads -> cloudRowPresent becomes true. Flipping intent
  // off deletes the row immediately.
  const {
    cloudRowPresent,
    cloudSyncIntent,
    setCloudRowPresent,
    setCloudSyncIntent: setCloudSyncIntentState,
  } = useCloudRowSync(droneId, convexClient, isAuthenticated);

  // On drone change, refresh capability + local key presence.
  useEffect(() => {
    if (!droneId || !client) return;
    let cancelled = false;
    (async () => {
      try {
        const cap = await client.getSigningCapability();
        if (!cancelled) setCapability(droneId, cap);
        const req = await client.getSigningRequire();
        if (!cancelled) setRequireOnFc(droneId, req.require);
      } catch {
        // keep whatever we had
      }
      const rec = await getRecord(droneId);
      if (cancelled) return;
      if (rec) {
        setBrowserKey(droneId, {
          keyId: rec.keyId,
          enrolledAt: rec.enrolledAt,
          enrollmentState:
            rec.enrollmentState === "enrolled"
              ? "enrolled"
              : rec.enrollmentState === "pending_fc_online"
                ? "pending_fc_online"
                : "fc_rejected",
        });
      } else {
        // No browser key. If the agent reports SIGNING_REQUIRE=1, flip
        // to key_missing so the recovery banner appears. If require is
        // off, leave the drone in the "no_browser_key" resting state so
        // the Enable button renders normally.
        setBrowserKey(droneId, null);
        try {
          const req = await client.getSigningRequire();
          if (!cancelled && req.require === true) {
            setEnrollmentState(droneId, "key_missing");
          }
        } catch {
          // non-fatal; ignore
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, droneId, setCapability, setRequireOnFc, setBrowserKey, setEnrollmentState]);

  const handleCloudSyncToggle = useCallback(async () => {
    if (!droneId) return;
    if (!isAuthenticated) {
      setCloudSyncError("Sign in to manage cloud sync.");
      return;
    }
    setCloudSyncBusy(true);
    setCloudSyncError(null);
    const newIntent = !cloudSyncIntent;
    try {
      if (newIntent && !isCloudSigningKeySyncEnabled()) {
        setCloudSyncError("Cloud signing-key sync is disabled until encrypted storage is available.");
        return;
      }

      // Persist intent first so UI reflects the user's choice
      // immediately, regardless of what happens on the cloud side.
      await setCloudSyncIntent(droneId, newIntent);
      setCloudSyncIntentState(newIntent);

      if (!newIntent) {
        // Opt out: remove the cloud row if present. Local key stays so
        // this browser keeps signing. Other devices that already pulled
        // the key keep working until next rotation on any device.
        if (convexClient && cloudRowPresent) {
          await removeCloudKey(convexClient, droneId);
          setCloudRowPresent(false);
        }
        void emitSigningEvent(convexClient, isAuthenticated, {
          droneId,
          eventType: "cloud_sync_off",
          keyIdOld: state?.keyId ?? undefined,
        });
        return;
      }

      // Opt in: we flip the toggle and emit the event immediately. The
      // actual key upload happens on the next enroll or rotate, since
      // that is the only moment raw key bytes are legible in JS memory.
      // If there is no browser key yet, the upload happens on the first
      // enrollment. If there is one, the panel nudges the user to
      // rotate to push it.
      void emitSigningEvent(convexClient, isAuthenticated, {
        droneId,
        eventType: "cloud_sync_on",
        keyIdOld: state?.keyId ?? undefined,
      });
    } catch (e) {
      setCloudSyncError(e instanceof Error ? e.message : String(e));
      // Roll back the intent flag if anything failed on our side.
      try {
        await setCloudSyncIntent(droneId, cloudSyncIntent);
        setCloudSyncIntentState(cloudSyncIntent);
      } catch {
        // nothing to roll back to
      }
    } finally {
      setCloudSyncBusy(false);
    }
  }, [cloudSyncIntent, cloudRowPresent, convexClient, droneId, isAuthenticated, state?.keyId, setCloudRowPresent, setCloudSyncIntentState]);

  const handleEnable = useCallback(async () => {
    if (!client || !droneId) return;
    setBusy(true);
    setError(null);
    setEnrollFailed(false);
    const rawBytes = generateRandomKey();
    const linkId = allocateLocalLinkId();

    // Deferred enrollment check. If the FC is not currently connected,
    // don't enroll yet. Surface a hint so the operator can come back when
    // the drone is online. We intentionally do not persist the key to
    // IndexedDB here: the agent needs the raw bytes to send SETUP_SIGNING,
    // but non-extractable CryptoKey storage cannot hand them back. A
    // "pending" record would be orphaned.
    let capability;
    try {
      capability = await client.getSigningCapability();
    } catch {
      capability = null;
    }
    if (capability && capability.reason === "fc_not_connected") {
      zeroize(rawBytes);
      setError(
        "Flight controller is not connected. Enrollment needs an online drone. Try again once the drone reconnects.",
      );
      setEnrollmentState(droneId, "pending_fc_online");
      setBusy(false);
      return;
    }

    // FC connected path: full enrollment with the tiered progress UI.
    setEnrollStartedAt(Date.now());

    // Hard deadline. If the agent's enroll-fc call has not resolved by
    // ENROLL_FAIL_MS, surface the "failed" tier and stop polling. The
    // in-flight promise still settles eventually; the UI just stops
    // waiting for it.
    let timedOut = false;
    const timeoutId = setTimeout(() => {
      timedOut = true;
      setEnrollFailed(true);
    }, ENROLL_FAIL_MS);

    try {
      const keyHex = keyBytesToHex(rawBytes);
      const result = await client.enrollSigningKey(keyHex, linkId);
      if (timedOut) {
        // The deadline already fired; the operator saw the failure UI.
        // Discard the late success so the next action is clean.
        zeroize(rawBytes);
        return;
      }
      // Cloud sync upload must happen while the hex string is still in
      // scope. importAndStore zeroizes rawBytes, and the non-extractable
      // CryptoKey cannot be exported back. This is the one moment the
      // raw material is legible in JS memory.
      if (cloudSyncIntent && convexClient && isAuthenticated) {
        try {
          await uploadKey(convexClient, {
            droneId,
            keyHex,
            keyId: result.key_id,
            linkIdOwner: linkId,
            enrolledAt: result.enrolled_at,
          });
          setCloudRowPresent(true);
        } catch (e) {
          // Non-fatal: the FC is enrolled and the local store will be
          // populated. Surface a toast but don't roll back the enrollment.
          setCloudSyncError(
            `Cloud sync upload failed: ${e instanceof Error ? e.message : String(e)}`,
          );
        }
      }
      // Agent zeroizes its copy. Now import browser-side as non-extractable
      // and then zeroize the local raw buffer.
      await importAndStore({
        droneId,
        userId: isAuthenticated ? (useAuthStore.getState().user?.id ?? null) : null,
        keyBytes: rawBytes, // importAndStore zeroizes this.
        linkId,
      });
      setBrowserKey(droneId, {
        keyId: result.key_id,
        enrolledAt: result.enrolled_at,
        enrollmentState: "enrolled",
      });
      setEnrollStartedAt(null);
      setEnrollFailed(false);

      // Audit: record whether this was a fresh enrollment or a rotation.
      const prevKeyId = state?.keyId ?? undefined;
      void emitSigningEvent(convexClient, isAuthenticated, {
        droneId,
        eventType: prevKeyId ? "rotation" : "enrollment",
        keyIdOld: prevKeyId,
        keyIdNew: result.key_id,
      });
    } catch (e) {
      if (!timedOut) {
        setError(e instanceof Error ? e.message : String(e));
      }
      zeroize(rawBytes);
    } finally {
      clearTimeout(timeoutId);
      setBusy(false);
    }
  }, [client, droneId, setBrowserKey, setEnrollmentState, cloudSyncIntent, convexClient, isAuthenticated, state?.keyId, setCloudRowPresent]);

  const handleDisable = useCallback(async () => {
    if (!client || !droneId) return;
    if (!confirm("Disable MAVLink signing for this drone?\n\nThis clears the FC's signing store. Any other browsers that hold the current key will stop working.")) {
      return;
    }
    setBusy(true);
    setError(null);
    const prevKeyId = state?.keyId ?? undefined;
    try {
      await client.disableSigningOnFc();
      await clearKeystoreRecord(droneId);
      setBrowserKey(droneId, null);
      setEnrollmentState(droneId, "no_browser_key");
      void emitSigningEvent(convexClient, isAuthenticated, {
        droneId,
        eventType: "disable",
        keyIdOld: prevKeyId,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [client, droneId, setBrowserKey, setEnrollmentState, state, convexClient, isAuthenticated]);

  const handleRotate = useCallback(async () => {
    if (!client || !droneId) return;
    if (!confirm("Rotate the signing key?\n\nA new 32-byte key will be generated and enrolled with the flight controller. The old key will be discarded.")) {
      return;
    }
    await handleEnable();
  }, [client, droneId, handleEnable]);

  const handleRequireToggle = useCallback(async () => {
    if (!client || !droneId) return;
    const next = !state?.requireOnFc;
    setBusy(true);
    setError(null);
    try {
      await client.setSigningRequire(next);
      setRequireOnFc(droneId, next);
      void emitSigningEvent(convexClient, isAuthenticated, {
        droneId,
        eventType: next ? "require_on" : "require_off",
        keyIdOld: state?.keyId ?? undefined,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [client, droneId, state?.requireOnFc, state?.keyId, setRequireOnFc, convexClient, isAuthenticated]);

  return {
    busy,
    error,
    enrollStartedAt,
    enrollFailed,
    exportOpen,
    importOpen,
    cloudSyncBusy,
    cloudSyncError,
    cloudRowPresent,
    cloudSyncIntent,
    isAuthenticated,
    authLoading,
    setExportOpen,
    setImportOpen,
    setEnrollStartedAt,
    setEnrollFailed,
    setBusy,
    handleEnable,
    handleDisable,
    handleRotate,
    handleRequireToggle,
    handleCloudSyncToggle,
  };
}
