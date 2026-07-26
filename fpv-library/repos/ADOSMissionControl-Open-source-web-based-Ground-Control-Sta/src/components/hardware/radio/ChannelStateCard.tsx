"use client";

/**
 * @module hardware/radio/ChannelStateCard
 * @description Surfaces the channel rendezvous and hop state of the WFB
 * link: the fixed home channel both sides boot on, the channel currently
 * in use, band, regulatory domain, whether the radio is in monitor mode
 * and actually transmitting, the peer-rendezvous state (linked vs
 * searching vs no peer) and the hop supervisor state. Read-only: the
 * agent owns channel/band/reg-domain config. Renders only when the agent
 * reports at least one of these fields so older agents stay silent.
 * @license GPL-3.0-only
 */

import { Radio as RadioIcon, Crosshair, ArrowLeftRight, Lock } from "lucide-react";
import { useTranslations } from "next-intl";
import type {
  RadioPeerLink,
  RadioHopState,
  RadioAcquireState,
} from "@/lib/api/ground-station/types";
import {
  EMPTY,
  peerLinkClass,
  hopStateClass,
  acquireStateClass,
} from "./constants";
import {
  peerLinkLabel,
  hopStateLabel,
  acquireStateLabel,
  bandLabel,
} from "./labels";
import { StatRow } from "./StatRow";

export interface ChannelStateCardProps {
  homeChannel: number | null;
  channel: number | null;
  freqMhz: number | null;
  band: string | null;
  regDomain: string | null;
  monitorActive: boolean | null;
  txActive: boolean | null;
  peerLink: RadioPeerLink | null;
  hopState: RadioHopState | null;
  // Ground receive acquirer mode + its boolean lock flag. Null on the
  // transmit side and on older agents.
  acquireState: RadioAcquireState | null;
  channelLocked: boolean | null;
}

export function ChannelStateCard({
  homeChannel,
  channel,
  freqMhz,
  band,
  regDomain,
  monitorActive,
  txActive,
  peerLink,
  hopState,
  acquireState,
  channelLocked,
}: ChannelStateCardProps) {
  const t = useTranslations("hardware.radio");

  // Forward-compatible: an older agent reports none of these and the
  // whole card stays hidden so the panel doesn't show a row of dashes.
  const hasAnything =
    homeChannel != null ||
    band != null ||
    regDomain != null ||
    monitorActive != null ||
    txActive != null ||
    peerLink != null ||
    hopState != null ||
    acquireState != null ||
    channelLocked != null;
  if (!hasAnything) return null;

  // The drone "locked on home channel N and transmitting" vs "searching
  // for a peer" indicator. txActive true + peerLink linked is the happy
  // path; anything else is the operator's cue that the link is stuck.
  const showTxState = monitorActive != null || txActive != null;

  return (
    <section className="rounded border border-border-default bg-bg-secondary p-5">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {peerLink != null ? (
          <span
            className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs ${peerLinkClass(peerLink)}`}
          >
            <Crosshair size={12} />
            {peerLinkLabel(t, peerLink)}
          </span>
        ) : null}
        {hopState != null ? (
          <span
            className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs ${hopStateClass(hopState)}`}
          >
            <ArrowLeftRight size={12} />
            {t("hop")}: {hopStateLabel(t, hopState)}
          </span>
        ) : null}
        {acquireState != null ? (
          <span
            className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs ${acquireStateClass(acquireState)}`}
          >
            <Lock size={12} />
            {t("acquire")}: {acquireStateLabel(t, acquireState)}
          </span>
        ) : null}
        {txActive === true ? (
          <span className="inline-flex items-center gap-1.5 rounded border border-status-success/40 bg-status-success/10 px-2.5 py-1 text-xs text-status-success">
            <RadioIcon size={12} />
            {t("txActiveBadge")}
          </span>
        ) : txActive === false ? (
          <span className="inline-flex items-center gap-1.5 rounded border border-status-warning/40 bg-status-warning/10 px-2.5 py-1 text-xs text-status-warning">
            <RadioIcon size={12} />
            {t("txIdleBadge")}
          </span>
        ) : null}
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        {homeChannel != null ? (
          <StatRow label={t("homeChannel")} value={`CH ${homeChannel}`} />
        ) : null}
        <StatRow
          label={t("currentChannel")}
          value={
            channel == null
              ? EMPTY
              : freqMhz == null
                ? `CH ${channel}`
                : `CH ${channel} (${freqMhz.toFixed(0)} MHz)`
          }
        />
        {band != null ? (
          <StatRow label={t("band")} value={bandLabel(t, band)} />
        ) : null}
        {regDomain != null ? (
          <StatRow label={t("operatingRegion")} value={regDomain} />
        ) : (
          <StatRow
            label={t("operatingRegion")}
            value={t("operatingRegionUnrestricted")}
            valueClass="text-status-warning"
          />
        )}
        {showTxState ? (
          <StatRow
            label={t("monitorMode")}
            value={
              monitorActive == null
                ? EMPTY
                : monitorActive
                  ? t("stateOn")
                  : t("stateOff")
            }
            valueClass={
              monitorActive === false ? "text-status-warning" : undefined
            }
          />
        ) : null}
        {channelLocked != null ? (
          <StatRow
            label={t("channelLocked")}
            value={channelLocked ? t("stateYes") : t("stateNo")}
            valueClass={
              channelLocked ? "text-status-success" : "text-status-warning"
            }
          />
        ) : null}
      </dl>
    </section>
  );
}
