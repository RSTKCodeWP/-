import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { usePseudoTxStore, preferredRcChannels, initPseudoTx } from './pseudo-tx-store';
import { RC_MID } from '../utils/pseudo-tx';

/** Minimal Gamepad stand-in; only the fields the store reads. */
function pad(axes: number[], buttons: boolean[] = [], index = 0, id = 'RadioMaster TX16S') {
  return {
    axes,
    buttons: buttons.map((pressed) => ({ pressed })),
    index,
    id,
  } as unknown as Gamepad;
}

function setPads(pads: (Gamepad | null)[]) {
  // `navigator` is getter-only here, so it has to be stubbed rather than assigned.
  vi.stubGlobal('navigator', { getGamepads: () => pads });
}

describe('pseudo transmitter store', () => {
  beforeEach(() => {
    usePseudoTxStore.getState().disable();
    usePseudoTxStore.getState().resetMapping();
    setPads([]);
  });

  afterEach(() => {
    usePseudoTxStore.getState().disable();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('is off until asked for, and reports nothing connected', () => {
    const s = usePseudoTxStore.getState();
    expect(s.enabled).toBe(false);
    expect(s.connected).toBe(false);
    expect(s.channels.every((c) => c === RC_MID)).toBe(true);
  });

  it('picks up a handset and converts sticks to channels', () => {
    setPads([pad([1, -1, 0, 0])]);
    usePseudoTxStore.getState().poll();
    const s = usePseudoTxStore.getState();
    expect(s.connected).toBe(true);
    expect(s.deviceName).toContain('TX16S');
    expect(s.isTransmitter).toBe(true);
    expect(s.channels[0]).toBe(2000);
    expect(s.channels[1]).toBe(1000);
  });

  it('notices the handset being unplugged', () => {
    setPads([pad([0.5, 0, 0, 0])]);
    usePseudoTxStore.getState().poll();
    expect(usePseudoTxStore.getState().connected).toBe(true);
    setPads([]);
    usePseudoTxStore.getState().poll();
    expect(usePseudoTxStore.getState().connected).toBe(false);
  });

  it('learns a channel from whichever control is wiggled', () => {
    setPads([pad([0, 0, 0, 0, 0, 0])]);
    usePseudoTxStore.getState().poll();
    usePseudoTxStore.getState().startLearn(6);
    // Move axis 5 only.
    setPads([pad([0, 0, 0, 0, 0, 0.9])]);
    usePseudoTxStore.getState().poll();
    const s = usePseudoTxStore.getState();
    expect(s.learning).toBeNull();
    expect(s.mapping[6]!.source).toEqual({ kind: 'axis', index: 5 });
    expect(s.channels[6]).toBeGreaterThan(1800);
  });

  it('learns a switch as a button', () => {
    setPads([pad([0, 0], [false, false, false])]);
    usePseudoTxStore.getState().poll();
    usePseudoTxStore.getState().startLearn(4);
    setPads([pad([0, 0], [false, true, false])]);
    usePseudoTxStore.getState().poll();
    expect(usePseudoTxStore.getState().mapping[4]!.source).toEqual({ kind: 'button', index: 1 });
  });
});

describe('source preference', () => {
  beforeEach(() => {
    usePseudoTxStore.getState().disable();
    setPads([]);
  });

  it('overrides a live flight controller when the switch is on', () => {
    // THE SITL CASE. The flight stack streams RC_CHANNELS constantly, so a "prefer whatever
    // the FC sends" rule would permanently shadow the handset and the switch would appear to
    // do nothing - which is exactly the bug this asserts against. Turning it on is an explicit
    // choice and must win.
    setPads([pad([1, 1, 1, 1])]);
    usePseudoTxStore.setState({ enabled: true });
    usePseudoTxStore.getState().poll();
    const r = preferredRcChannels([1100, 1200, 1300, 1400]);
    expect(r.source).toBe('pseudo');
    expect(r.channels[0]).toBe(2000);
  });

  it('uses the flight controller when the switch is off', () => {
    setPads([pad([1, 1, 1, 1])]);
    usePseudoTxStore.setState({ enabled: false });
    const r = preferredRcChannels([1100, 1200, 1300, 1400]);
    expect(r.source).toBe('fc');
    expect(r.channels[0]).toBe(1100);
  });

  it('falls back to the FC if the switch is on but nothing is plugged in', () => {
    setPads([]);
    usePseudoTxStore.setState({ enabled: true });
    usePseudoTxStore.getState().poll();
    expect(preferredRcChannels([1100, 1200]).source).toBe('fc');
  });

  it('falls back to the handset when no FC data has arrived', () => {
    setPads([pad([1, -1, 0, 0])]);
    usePseudoTxStore.setState({ enabled: true });
    usePseudoTxStore.getState().poll();
    const r = preferredRcChannels([]);
    expect(r.source).toBe('pseudo');
    expect(r.channels[0]).toBe(2000);
  });

  it('reports no source when nothing is attached and the stand-in is off', () => {
    expect(preferredRcChannels([]).source).toBe('none');
    expect(preferredRcChannels(undefined).source).toBe('none');
  });

  it('treats an all-zero FC frame as no data, not as a valid reading', () => {
    // A store initialised to zeros must not masquerade as a live link.
    setPads([pad([1, 0, 0, 0])]);
    usePseudoTxStore.setState({ enabled: true });
    usePseudoTxStore.getState().poll();
    expect(preferredRcChannels([0, 0, 0, 0]).source).toBe('pseudo');
  });
});

/**
 * Every pop-out is its own renderer process running this same store, so two windows poll at
 * once. Chromium only refreshes gamepad state for the FOCUSED document, so the unfocused
 * window reads frozen axes - and must stay off the wire.
 */
describe('multi-window handover', () => {
  const send = vi.fn();
  const listeners = new Map<string, (e: StorageEvent) => void>();

  function stubWindow(focused: boolean) {
    const store = new Map<string, string>();
    vi.stubGlobal('window', {
      electronAPI: {
        ardupilotSitlRcSend: send,
        ardupilotSitlRcStart: vi.fn().mockResolvedValue({ success: true }),
        ardupilotSitlRcStop: vi.fn().mockResolvedValue({ success: true }),
      },
      addEventListener: (name: string, fn: (e: StorageEvent) => void) => listeners.set(name, fn),
    });
    vi.stubGlobal('document', { hasFocus: () => focused });
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    });
  }

  beforeEach(() => {
    send.mockReset();
    send.mockResolvedValue(undefined);
    listeners.clear();
    usePseudoTxStore.setState({ enabled: false, pollTimer: null, connected: false });
    setPads([]);
  });

  afterEach(() => {
    usePseudoTxStore.getState().disable();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('sends while this window has focus', () => {
    stubWindow(true);
    setPads([pad([1, 1, 1, 1])]);
    usePseudoTxStore.setState({ enabled: true });
    usePseudoTxStore.getState().poll();
    expect(send).toHaveBeenCalledTimes(1);
  });

  it('stays silent while another window has focus, instead of sending frozen sticks', () => {
    stubWindow(false);
    setPads([pad([1, 1, 1, 1])]);
    usePseudoTxStore.setState({ enabled: true });
    usePseudoTxStore.getState().poll();
    expect(send).not.toHaveBeenCalled();
    // Still tracked locally, so the window's own UI stays truthful.
    expect(usePseudoTxStore.getState().channels[0]).toBe(2000);
  });

  it('picks the handset up on boot when another window already switched it on', () => {
    stubWindow(true);
    localStorage.setItem('ardudeck.pseudoTx.enabled', '1');
    initPseudoTx();
    expect(usePseudoTxStore.getState().enabled).toBe(true);
  });

  it('stays off on boot when nothing switched it on', () => {
    stubWindow(true);
    initPseudoTx();
    expect(usePseudoTxStore.getState().enabled).toBe(false);
  });

  it('follows a switch thrown in another window', () => {
    stubWindow(true);
    initPseudoTx();
    const onStorage = listeners.get('storage')!;

    onStorage({ key: 'ardudeck.pseudoTx.enabled', newValue: '1' } as StorageEvent);
    expect(usePseudoTxStore.getState().enabled).toBe(true);

    onStorage({ key: 'ardudeck.pseudoTx.enabled', newValue: '0' } as StorageEvent);
    expect(usePseudoTxStore.getState().enabled).toBe(false);
  });

  it('ignores unrelated storage keys', () => {
    stubWindow(true);
    initPseudoTx();
    listeners.get('storage')!({ key: 'something.else', newValue: '1' } as StorageEvent);
    expect(usePseudoTxStore.getState().enabled).toBe(false);
  });
});
