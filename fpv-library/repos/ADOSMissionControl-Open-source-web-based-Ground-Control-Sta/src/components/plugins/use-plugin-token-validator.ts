"use client";

/**
 * @module use-plugin-token-validator
 * @description Builds a `BridgeTokenValidatorOptions` for one plugin
 * iframe. The bridge runs this on every RPC envelope and rejects any
 * call whose token fails one of the 5 checks (presence, expiry, plugin
 * id, agent id, signature against the right issuer secret).
 *
 * Composition:
 *
 *   1. `useCapabilityToken(installId, deviceId, transport)` mints and
 *      refreshes the operator's token for this (plugin, drone) pair.
 *      The bridge does not embed this token in envelopes itself; the
 *      iframe SDK reads it via the bridge's token-publish channel and
 *      stamps each RPC envelope. Here we wire `onTokenExpired` to
 *      `refresh()` so the next mint runs the moment a stale token is
 *      detected at the verifier.
 *
 *   2. Operator HMAC secret (`operatorHmacSecrets.getMyCurrent`)
 *      resolves the `cloud:<userId>` issuer family. The secret rotates
 *      every 30 days; the GCS sees current + previous so tokens minted
 *      just before a rotation still verify until they expire.
 *
 *   3. Per-pairing HMAC secret (`deriveAgentTokenSecret(apiKey)`)
 *      resolves the `agent:<deviceId>` issuer family. HKDF-SHA256
 *      derivation mirrors the agent's `derive_agent_token_secret`, so
 *      a token signed by the agent verifies here without round-tripping
 *      the raw pairing key over the network.
 *
 *   4. `local` issuer raises `TokenInvalid` so any production envelope
 *      claiming `iss: local` against the GCS bridge is rejected.
 *      Production tokens go through `cloud` or `agent`.
 *
 * The hook calls Convex `useAction` via `useCapabilityToken` and is
 * therefore only safe to invoke under a `<ConvexProvider>`. The
 * `<PluginSlot>` mount picks between this hook and a plain pass-through
 * based on `useConvexAvailable()` and the presence of a deviceId; this
 * file assumes both preconditions hold.
 *
 * @license GPL-3.0-only
 */

import { useCallback, useMemo, useRef } from "react";

import { useCapabilityToken } from "@/hooks/use-capability-token";
import { useConvexSkipQuery } from "@/hooks/use-convex-skip-query";
import type { BridgeTokenValidatorOptions } from "@/lib/plugins/bridge";
import {
  TokenInvalid,
  deriveAgentTokenSecret,
  importHmacKeyFromBase64,
  type IssuerKind,
} from "@/lib/plugins/capability-token-claims";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { usePairingStore } from "@/stores/pairing-store";
import { api as convexApi } from "../../../convex/_generated/api";

interface UsePluginTokenValidatorOptions {
  pluginInstallId: string;
  /** Drone device id this iframe is bound to. Required; the caller
   * gates on its presence before mounting this hook. */
  deviceId: string;
}

/**
 * Build the validator for one (plugin install, deviceId) pair.
 * The caller passes the resulting options to `<PluginIframeHost>`;
 * the bridge wires it into the dispatch pipeline.
 */
export function usePluginTokenValidator(
  opts: UsePluginTokenValidatorOptions,
): BridgeTokenValidatorOptions {
  const { pluginInstallId, deviceId } = opts;

  // Transport picks between cloud-issuer and LAN-direct-issuer minting
  // for the current connection. The verifier accepts whichever issuer
  // is on the wire; transport here only influences where the FRESH
  // tokens come from. cloudMode flips on HTTPS or when the LAN URL is
  // unreachable, matching the install dialog's resolver logic.
  const cloudMode = useAgentConnectionStore((s) => s.cloudMode);
  const transport: "cloud" | "lan" = cloudMode ? "cloud" : "lan";

  // Operator HMAC secret. The query soft-fails when the operator is
  // signed out, returning `undefined`; in that case the cloud-issuer
  // resolver below raises and the bridge maps the failure to
  // `signature_invalid` / `token_invalid` for the offending RPC.
  const hmac = useConvexSkipQuery(convexApi.operatorHmacSecrets.getMyCurrent);

  // Paired-drone row for this deviceId. We use the api key (pairing
  // key) as HKDF input material to derive the per-pairing HMAC secret
  // the agent signed with.
  const apiKey = usePairingStore(
    (s) => s.pairedDrones.find((d) => d.deviceId === deviceId)?.apiKey ?? null,
  );

  // Delegate mint orchestration to `useCapabilityToken`. The bridge
  // does not need the token itself (it reads it from `env.token`); we
  // only consume the `refresh` callback so a verifier-side expiry can
  // immediately trigger a fresh mint for the iframe to pick up.
  const tokenForRefresh = useCapabilityToken(
    pluginInstallId,
    deviceId,
    transport,
  );
  const refresh = tokenForRefresh.refresh;

  // Stash latest secret material in refs so the resolver closure stays
  // pinned across renders (the bridge captures the validator object
  // once; we want fresh secrets read on every dispatch).
  const hmacRef = useRef(hmac);
  const apiKeyRef = useRef(apiKey);
  hmacRef.current = hmac;
  apiKeyRef.current = apiKey;

  // Per-validator key caches. Importing a CryptoKey is async and the
  // result is stable for the lifetime of the secret; cache by the
  // secret material to avoid re-importing on every RPC.
  const cloudKeyCache = useRef<Map<string, Promise<CryptoKey>>>(new Map());
  const agentKeyCache = useRef<Map<string, Promise<CryptoKey>>>(new Map());

  const secretResolver = useCallback(
    async (kind: IssuerKind, _subject: string): Promise<CryptoKey> => {
      if (kind === "local") {
        // Local dev tokens carry no agent-id binding; production
        // bridges that see `iss: local` should reject. The agent half
        // gates `local` behind a dev-mode env flag. Until the GCS gets
        // its own dev-mode secret store, refuse here so the offending
        // RPC fails closed.
        throw new TokenInvalid(
          "local-issuer tokens are not supported by the GCS bridge",
        );
      }
      if (kind === "cloud") {
        const current = hmacRef.current;
        if (!current?.secretBase64) {
          throw new TokenInvalid(
            "operator HMAC secret is not loaded; cannot verify cloud-issued token",
          );
        }
        const cached = cloudKeyCache.current.get(current.secretBase64);
        if (cached) return cached;
        const minted = importHmacKeyFromBase64(current.secretBase64);
        cloudKeyCache.current.set(current.secretBase64, minted);
        // Pre-cache the previous secret so rotation-overlap tokens
        // verify without an extra resolver round-trip.
        if (
          current.previousSecretBase64 &&
          !cloudKeyCache.current.has(current.previousSecretBase64)
        ) {
          cloudKeyCache.current.set(
            current.previousSecretBase64,
            importHmacKeyFromBase64(current.previousSecretBase64),
          );
        }
        return minted;
      }
      // kind === "agent"
      const pairing = apiKeyRef.current;
      if (!pairing) {
        throw new TokenInvalid(
          "pairing key unavailable; cannot derive per-pairing HMAC secret",
        );
      }
      const cached = agentKeyCache.current.get(pairing);
      if (cached) return cached;
      const minted = deriveAgentTokenSecret(pairing);
      agentKeyCache.current.set(pairing, minted);
      return minted;
    },
    [],
  );

  const onTokenExpired = useCallback(() => {
    // Fire-and-forget. The hook surfaces the error if the mint fails;
    // the bridge has already responded `capability_denied:token_expired`
    // to the iframe, and the iframe SDK retries from the fresh cache
    // on its next RPC.
    void refresh().catch(() => {
      /* swallowed; surfaced via `useCapabilityToken` */
    });
  }, [refresh]);

  return useMemo<BridgeTokenValidatorOptions>(
    () => ({
      expectedAgentId: deviceId,
      secretResolver,
      onTokenExpired,
    }),
    [deviceId, secretResolver, onTokenExpired],
  );
}
