/**
 * Pseudo Transmitter switch
 *
 * One toggle that lets a USB-connected handset (EdgeTX in "USB Joystick" mode) stand in for a
 * real RC link, so modes, quick setup, telemetry and the 3D view can be configured and tested
 * with no flight controller and no receiver attached.
 *
 * Deliberately manual. It never turns itself on: a stand-in that appears by itself is a stand-in
 * that will eventually be mistaken for a live aircraft, and the whole point of the switch is
 * that you always know which you are looking at. Real FC channels always take priority anyway
 * (see `preferredRcChannels`), so leaving it on with hardware attached is harmless.
 *
 * Styling follows the surrounding config cards: `bg-surface rounded-xl border border-subtle p-4`
 * with an emerald toggle, so it reads as part of the page rather than bolted on.
 */

import { useState } from 'react';
import { Usb, ChevronDown, ChevronRight } from 'lucide-react';
import { usePseudoTxStore } from '../stores/pseudo-tx-store';
import type { ChannelSource } from '../utils/pseudo-tx';

/** Human-readable description of where a channel gets its value. */
function sourceLabel(src: ChannelSource): string {
  switch (src.kind) {
    case 'none':
      return 'unassigned';
    case 'axis':
      return `axis ${src.index}`;
    case 'button':
      return `button ${src.index}`;
    case 'button3':
      return `buttons ${src.low}/${src.high}`;
  }
}

/**
 * Channel mapping, taught by moving the control you want to bind.
 *
 * There is no preset to pick, because channel order (AETR, TAER, ...) is a per-model setting
 * on the transmitter and cannot be read back over USB. Asking the user to move the control is
 * the only way to know, and it takes a second per channel.
 */
function MappingPanel(): JSX.Element {
  const mapping = usePseudoTxStore((s) => s.mapping);
  const channels = usePseudoTxStore((s) => s.channels);
  const learning = usePseudoTxStore((s) => s.learning);
  const startLearn = usePseudoTxStore((s) => s.startLearn);
  const cancelLearn = usePseudoTxStore((s) => s.cancelLearn);
  const setSource = usePseudoTxStore((s) => s.setSource);
  const resetMapping = usePseudoTxStore((s) => s.resetMapping);

  return (
    <div className="mt-3 pt-3 border-t border-subtle">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-content">Channel mapping</span>
        <button
          type="button"
          onClick={resetMapping}
          className="text-xs text-content-secondary hover:text-content transition-colors"
        >
          Reset
        </button>
      </div>

      <div className="space-y-1.5">
        {mapping.slice(0, 8).map((m, i) => {
          const pwm = channels[i] ?? 1500;
          const pct = Math.min(100, Math.max(0, ((pwm - 1000) / 1000) * 100));
          const isLearning = learning === i;
          return (
            <div key={i} className="flex items-center gap-2.5">
              <span className="w-9 shrink-0 text-xs text-content-secondary">CH{i + 1}</span>

              <div className="relative flex-1 h-5 rounded-lg bg-surface-raised overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 bg-blue-500/40 transition-[width] duration-75"
                  style={{ width: `${pct}%` }}
                />
                <span className="absolute inset-0 flex items-center justify-center text-[10px] tabular-nums text-content">
                  {pwm}
                </span>
              </div>

              <span
                className="w-20 shrink-0 text-[10px] text-content-secondary truncate"
                title={sourceLabel(m.source)}
              >
                {sourceLabel(m.source)}
              </span>

              <button
                type="button"
                onClick={() => (isLearning ? cancelLearn() : startLearn(i))}
                className={`shrink-0 px-2 py-1 rounded-lg text-xs transition-colors ${
                  isLearning
                    ? 'bg-blue-500/15 text-blue-400 border border-blue-500/40 animate-pulse'
                    : 'bg-surface-raised text-content-secondary border border-subtle hover:text-content'
                }`}
              >
                {isLearning ? 'move it' : 'Assign'}
              </button>

              <button
                type="button"
                onClick={() => setSource(i, { kind: 'none' })}
                disabled={m.source.kind === 'none'}
                title="Unassign"
                className="shrink-0 w-5 text-xs text-content-secondary hover:text-content disabled:opacity-0 transition-colors"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>

      <p className="mt-2 text-xs text-content-secondary">
        Press <span className="text-content">Assign</span>, then move the stick or flick the
        switch you want on that channel. Unassigned channels hold 1500.
      </p>

      <DeviceMonitor />
    </div>
  );
}

/**
 * Everything the handset actually reports, live.
 *
 * This exists because a switch that "does not work" has three quite different causes and they
 * are indistinguishable from the channel bars alone: the switch may be on an axis nobody
 * mapped, it may arrive as a button, or Chromium may have forced the device into its
 * "standard" gamepad layout, which keeps four axes and DISCARDS the rest - taking every switch
 * with them. Watching the raw values while flicking a switch says which.
 */
function DeviceMonitor(): JSX.Element {
  const raw = usePseudoTxStore((s) => s.raw);
  const mappingMode = usePseudoTxStore((s) => s.mappingMode);
  const standard = mappingMode === 'standard';

  return (
    <div className="mt-3 pt-3 border-t border-subtle">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-content">Device monitor</span>
        <span className="text-[10px] text-content-secondary">
          {raw.axes.length} axes - {raw.buttons.length} buttons
          {mappingMode ? ` - mapping "${mappingMode}"` : ' - raw HID'}
        </span>
      </div>

      {standard && (
        <p className="mb-2 text-xs text-amber-400">
          The browser has applied its standard gamepad layout to this device, which keeps only
          four axes and drops the rest - so the switches never arrive. Re-plug with the handset
          already in USB Joystick mode, or use a model whose USB descriptor is not recognised as
          a game controller.
        </p>
      )}

      <div className="grid grid-cols-5 gap-1">
        {raw.axes.map((v, i) => (
          <div key={`a${i}`} className="rounded bg-surface-raised px-1.5 py-1">
            <div className="text-[10px] text-content-secondary">a{i}</div>
            <div className="text-[10px] tabular-nums text-content">{v.toFixed(2)}</div>
          </div>
        ))}
      </div>

      {raw.buttons.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {raw.buttons.map((down, i) => (
            <span
              key={`b${i}`}
              className={`px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
                down ? 'bg-emerald-500/20 text-emerald-400' : 'bg-surface-raised text-content-secondary'
              }`}
            >
              {i}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function PseudoTxSwitch(): JSX.Element {
  const [showMap, setShowMap] = useState(false);
  const enabled = usePseudoTxStore((s) => s.enabled);
  const connected = usePseudoTxStore((s) => s.connected);
  const deviceName = usePseudoTxStore((s) => s.deviceName);
  const isTransmitter = usePseudoTxStore((s) => s.isTransmitter);
  const enable = usePseudoTxStore((s) => s.enable);
  const disable = usePseudoTxStore((s) => s.disable);
  const sendError = usePseudoTxStore((s) => s.sendError);
  const sentFrames = usePseudoTxStore((s) => s.sentFrames);

  const detail = !enabled
    ? 'Off - the sliders below are driving RC'
    : connected
      ? `${deviceName} - ${sentFrames} RC frames sent`
      : 'Waiting for a handset - set EdgeTX to USB Joystick mode';

  return (
    <div className="bg-surface rounded-xl border border-subtle p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-start gap-2.5 min-w-0">
          <Usb
            className={`w-4 h-4 mt-0.5 shrink-0 ${
              enabled && connected ? 'text-emerald-400' : 'text-content-secondary'
            }`}
          />
          <div className="min-w-0">
            <h3 className="text-sm font-medium text-content">Fly with USB transmitter</h3>
            <p className="text-xs text-content-secondary mt-0.5 truncate" title={detail}>
              {sendError ? <span className="text-amber-400">{sendError}</span> : detail}
              {enabled && connected && !isTransmitter && (
                <span className="text-amber-400"> - looks like a gamepad, not a handset</span>
              )}
            </p>
          </div>
        </div>

        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label="Fly with USB transmitter"
          onClick={() => (enabled ? disable() : enable())}
          className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${
            enabled ? 'bg-emerald-500' : 'bg-surface-raised'
          }`}
        >
          <div
            className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
              enabled ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>

      {enabled && connected && (
        <>
          <button
            type="button"
            onClick={() => setShowMap((v) => !v)}
            className="mt-3 flex items-center gap-1 text-xs text-content-secondary hover:text-content transition-colors"
          >
            {showMap ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            Channel mapping
          </button>
          {showMap && <MappingPanel />}
        </>
      )}
    </div>
  );
}
