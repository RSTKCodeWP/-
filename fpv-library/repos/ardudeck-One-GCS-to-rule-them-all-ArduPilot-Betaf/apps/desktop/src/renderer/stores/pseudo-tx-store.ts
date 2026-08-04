/**
 * Pseudo Transmitter Store
 *
 * A USB-connected handset (EdgeTX in "USB Joystick" mode) standing in for a real RC link, so
 * the screens that need a transmitter work with no flight controller and no receiver attached:
 * modes setup, quick setup, telemetry and the 3D view.
 *
 * Chromium already exposes the handset through the Gamepad API, so there is no native module,
 * no driver and no extra permission involved. Shaping lives in `utils/pseudo-tx.ts` and is
 * shared, in behaviour, with the simulator's own RC path so the two cannot disagree about
 * where centre is.
 *
 * The switch is AUTHORITATIVE. When it is on, the handset is the RC source, full stop - that is
 * what the label promises. An earlier version preferred flight-controller channels whenever any
 * were arriving, which quietly disabled the whole feature under SITL: the flight stack streams
 * RC_CHANNELS constantly, so the "live link" test was always true and the switch did nothing in
 * the one situation it exists for. Turning it on is an explicit choice; honour it.
 */

import { create } from 'zustand';
import {
  RC_CHANNEL_COUNT,
  RC_MID,
  type ChannelMap,
  type ChannelSource,
  type RawDevice,
  defaultMapping,
  detectMovedControl,
  devicesToChannels,
  looksLikeTransmitter,
} from '../utils/pseudo-tx';

/** 50 Hz, matching a real receiver's frame rate. */
const POLL_MS = 20;

const EMPTY_DEVICE: RawDevice = { axes: [], buttons: [] };

/**
 * Shared across windows via localStorage, because every pop-out is a separate Electron
 * BrowserWindow with its OWN renderer process and therefore its own copy of this store.
 * Switching the handset on in the SITL tab has to reach the popped-out 3D view too, or that
 * window sits there with `enabled: false` and never streams anything.
 */
const ENABLED_KEY = 'ardudeck.pseudoTx.enabled';

function readEnabledFlag(): boolean {
  try {
    return localStorage.getItem(ENABLED_KEY) === '1';
  } catch {
    return false;
  }
}

function writeEnabledFlag(on: boolean): void {
  try {
    localStorage.setItem(ENABLED_KEY, on ? '1' : '0');
  } catch {
    // Private mode / storage disabled: the switch still works in this window.
  }
}

/**
 * The preload bridge, or undefined outside a renderer. Guarded so the store's logic stays
 * unit-testable in a plain node environment, where `window` does not exist at all.
 */
function api(): Window['electronAPI'] | undefined {
  return typeof window === 'undefined' ? undefined : window.electronAPI;
}

function readGamepad(
  index: number | null,
): { dev: RawDevice; id: string; index: number; mapping: string } | null {
  if (typeof navigator === 'undefined' || !navigator.getGamepads) return null;
  const pads = Array.from(navigator.getGamepads()).filter((p): p is Gamepad => p != null);
  if (pads.length === 0) return null;
  const pad = (index != null && pads.find((p) => p.index === index)) || pads[0]!;
  return {
    dev: { axes: Array.from(pad.axes), buttons: pad.buttons.map((b) => b.pressed) },
    id: pad.id,
    index: pad.index,
    mapping: pad.mapping ?? '',
  };
}

interface PseudoTxState {
  /** User has switched the stand-in on. Off by default: it must never surprise anyone. */
  enabled: boolean;
  connected: boolean;
  deviceName: string;
  deviceIndex: number | null;
  /** Looks like a handset rather than a console pad. Advisory only. */
  isTransmitter: boolean;
  /**
   * Chromium's gamepad mapping mode. "standard" means it has forced the device into the
   * console-pad layout of 4 axes plus buttons, DISCARDING any further axes - which silently
   * hides every switch on a handset. Empty string means raw HID, which is what we want.
   */
  mappingMode: string;

  channels: number[];
  mapping: ChannelMap[];
  raw: RawDevice;

  /** Set when RC frames are not reaching SITL. */
  sendError: string | null;
  /** Frames actually handed to the bridge. Zero while 'on' means the chain is broken. */
  sentFrames: number;

  /** Channel currently being taught by wiggling a control, or null. */
  learning: number | null;
  learnBaseline: RawDevice | null;

  pollTimer: ReturnType<typeof setInterval> | null;

  enable: () => void;
  disable: () => void;
  poll: () => void;
  startLearn: (channel: number) => void;
  cancelLearn: () => void;
  setSource: (channel: number, source: ChannelSource) => void;
  updateMap: (channel: number, patch: Partial<ChannelMap>) => void;
  resetMapping: () => void;
}

export const usePseudoTxStore = create<PseudoTxState>((set, get) => ({
  enabled: false,
  connected: false,
  deviceName: '',
  deviceIndex: null,
  isTransmitter: false,
  mappingMode: '',
  channels: Array(RC_CHANNEL_COUNT).fill(RC_MID),
  mapping: defaultMapping(),
  raw: EMPTY_DEVICE,
  sendError: null,
  sentFrames: 0,
  learning: null,
  learnBaseline: null,
  pollTimer: null,

  enable: () => {
    writeEnabledFlag(true);
    if (get().pollTimer) return;
    const timer = setInterval(() => get().poll(), POLL_MS);
    set({ enabled: true, pollTimer: timer });
    // Feed SITL from the SAME timer that reads the handset.
    //
    // This used to live in a React effect inside the panel, which meant the stream only ran
    // while that panel happened to be mounted: switch it on from the Receiver tab, walk over
    // to telemetry, the component unmounted and the sticks stopped arriving. SITL then kept
    // seeing `ardupilotRcSender`'s safe default of throttle -1, which is why the aircraft
    // ARMED with the throttle stick at 100% - proof the handset was never reaching it.
    void api()?.ardupilotSitlRcStart?.().catch(() => {});
  },

  disable: () => {
    writeEnabledFlag(false);
    const { pollTimer } = get();
    if (pollTimer) clearInterval(pollTimer);
    // Hand SITL back to its own safe defaults rather than leaving the last stick values latched.
    void api()?.ardupilotSitlRcStop?.().catch(() => {});
    set({
      enabled: false,
      pollTimer: null,
      connected: false,
      learning: null,
      learnBaseline: null,
      channels: Array(RC_CHANNEL_COUNT).fill(RC_MID),
    });
  },

  poll: () => {
    const { learning, learnBaseline, deviceIndex } = get();
    const read = readGamepad(deviceIndex);
    if (!read) {
      if (get().connected) set({ connected: false, deviceName: '' });
      return;
    }
    const { dev, id, index, mapping } = read;

    if (!get().connected || get().deviceIndex !== index) {
      set({
        connected: true,
        deviceName: id,
        deviceIndex: index,
        mappingMode: mapping,
        isTransmitter: looksLikeTransmitter(id, dev.axes.length),
      });
    }

    // Teaching a channel: watch for a control that moves clearly away from its rest state.
    if (learning != null && learnBaseline) {
      const found = detectMovedControl(learnBaseline, dev);
      if (found) {
        get().setSource(learning, found);
        set({ learning: null, learnBaseline: null });
      }
    }

    // Read the mapping AFTER any learn above, not from the snapshot taken at entry: a channel
    // taught this tick must respond on this tick, not on the next one.
    const ch = devicesToChannels(dev, get().mapping);
    set({ raw: dev, channels: ch });

    // Only the FOCUSED window may send.
    //
    // Chromium refreshes gamepad state for the focused document only. Every window runs this
    // poll (they are separate renderer processes), so an unfocused one keeps reading the axes
    // frozen at whatever they were when it lost focus. Letting it send too would interleave
    // stale frames with live ones at 50Hz. This is why the sticks died the moment the 3D view
    // was popped out: the main window still held the switch, but no longer the gamepad.
    if (typeof document !== 'undefined' && !document.hasFocus()) return;

    // SITL takes -1..1 per channel, not microseconds.
    const n = (pwm: number) => Math.min(1, Math.max(-1, (pwm - 1500) / 500));
    const bridge = api();
    // Say so LOUDLY if the bridge is missing. Optional chaining here silently does nothing,
    // which is how this shipped looking connected while sending absolutely nothing.
    if (!bridge?.ardupilotSitlRcSend) {
      if (!get().sendError) {
        set({ sendError: 'No SITL RC bridge in this window - frames are going nowhere' });
      }
      return;
    }
    set({ sentFrames: get().sentFrames + 1, sendError: null });
    void bridge.ardupilotSitlRcSend({
      roll: n(ch[0] ?? 1500),
      pitch: n(ch[1] ?? 1500),
      throttle: n(ch[2] ?? 1000),
      yaw: n(ch[3] ?? 1500),
      aux1: n(ch[4] ?? 1500),
      aux2: n(ch[5] ?? 1500),
      aux3: n(ch[6] ?? 1500),
      aux4: n(ch[7] ?? 1500),
    }).catch((e: unknown) => {
      set({ sendError: `SITL rejected RC: ${String(e)}` });
    });
  },

  startLearn: (channel) => {
    const read = readGamepad(get().deviceIndex);
    set({ learning: channel, learnBaseline: read ? read.dev : EMPTY_DEVICE });
  },

  cancelLearn: () => set({ learning: null, learnBaseline: null }),

  setSource: (channel, source) => {
    const mapping = [...get().mapping];
    const cur = mapping[channel];
    if (!cur) return;
    mapping[channel] = { ...cur, source };
    set({ mapping });
  },

  updateMap: (channel, patch) => {
    const mapping = [...get().mapping];
    const cur = mapping[channel];
    if (!cur) return;
    mapping[channel] = { ...cur, ...patch };
    set({ mapping });
  },

  resetMapping: () => set({ mapping: defaultMapping() }),
}));

/**
 * Join the handset to this window. Call once per renderer, from the entry point.
 *
 * Pop-outs boot the same bundle in a fresh renderer process, so without this the popped-out 3D
 * view would never poll at all - it would have no idea the switch was ever thrown.
 */
export function initPseudoTx(): void {
  if (typeof window === 'undefined') return;

  if (readEnabledFlag()) usePseudoTxStore.getState().enable();

  window.addEventListener('storage', (e) => {
    if (e.key !== ENABLED_KEY) return;
    const s = usePseudoTxStore.getState();
    const on = e.newValue === '1';
    if (on && !s.enabled) s.enable();
    else if (!on && s.enabled) s.disable();
  });
}

/**
 * RC in the shape the telemetry screens already consume.
 *
 * The switch wins when it is on, including against a live flight controller or SITL: the user
 * asked for the handset. `rssi` is reported as 0 for the stand-in because there is no radio
 * involved and inventing a signal strength on a diagnostics screen would be a lie.
 *
 * A hook rather than a plain read so the OSD live panel, the flight-modes tab, the receiver tab
 * and the 3D view re-render as the sticks move.
 */
export function useEffectiveRc(fc: { channels: number[]; chancount: number; rssi: number }): {
  channels: number[];
  chancount: number;
  rssi: number;
  source: 'fc' | 'pseudo' | 'none';
} {
  const enabled = usePseudoTxStore((s) => s.enabled);
  const connected = usePseudoTxStore((s) => s.connected);
  const channels = usePseudoTxStore((s) => s.channels);

  if (enabled && connected) {
    return { channels, chancount: channels.length, rssi: 0, source: 'pseudo' };
  }
  const live = fc.channels.length > 0 && fc.channels.some((c) => c > 0);
  return { ...fc, source: live ? 'fc' : 'none' };
}

/**
 * RC channels for a consumer to display.
 *
 * The switch wins when it is on. Under SITL the flight stack always streams RC_CHANNELS, so a
 * "prefer whatever the FC sends" rule would permanently shadow the handset - which is the bug
 * this ordering exists to avoid.
 */
export function preferredRcChannels(fcChannels: number[] | undefined): {
  channels: number[];
  source: 'fc' | 'pseudo' | 'none';
} {
  const { enabled, connected, channels } = usePseudoTxStore.getState();
  if (enabled && connected) return { channels, source: 'pseudo' };

  const live = fcChannels && fcChannels.length > 0 && fcChannels.some((c) => c > 0);
  if (live) return { channels: fcChannels!, source: 'fc' };

  return { channels: fcChannels ?? [], source: 'none' };
}
