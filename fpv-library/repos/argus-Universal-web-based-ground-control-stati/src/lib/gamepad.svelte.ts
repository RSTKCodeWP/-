import { dispatch } from './transport';
import { app } from './stores.svelte';

export interface ChannelMap {
  roll: number;
  pitch: number;
  throttle: number;
  yaw: number;
  invertRoll: boolean;
  invertPitch: boolean;
  invertThrottle: boolean;
  invertYaw: boolean;
}

const DEFAULT_MAP: ChannelMap = {
  roll: 0,
  pitch: 1,
  throttle: 3,
  yaw: 2,
  invertRoll: false,
  invertPitch: true,
  invertThrottle: true,
  invertYaw: false,
};

class GamepadState {
  connected: boolean = $state(false);
  name: string = $state('');
  axes: number[] = $state([0, 0, 0, 0]);
  buttons: boolean[] = $state([]);
  enabled: boolean = $state(false);
  deadzone: number = $state(0.08);
  channelMap: ChannelMap = $state({ ...DEFAULT_MAP });
}

export const gamepad = new GamepadState();

let animFrame = 0;
let gpIndex = -1;

export function loadGamepadMap() {
  try {
    const saved = JSON.parse(localStorage.getItem('argus_gamepad_map') || '{}');
    if (saved.roll !== undefined) gamepad.channelMap = { ...DEFAULT_MAP, ...saved };
  } catch {}
}

export function saveGamepadMap() {
  try {
    localStorage.setItem('argus_gamepad_map', JSON.stringify(gamepad.channelMap));
  } catch {}
}

export function startGamepad() {
  gamepad.enabled = true;
  window.addEventListener('gamepadconnected', onConnect);
  window.addEventListener('gamepaddisconnected', onDisconnect);
  poll();
}

export function stopGamepad() {
  gamepad.enabled = false;
  window.removeEventListener('gamepadconnected', onConnect);
  window.removeEventListener('gamepaddisconnected', onDisconnect);
  if (animFrame) cancelAnimationFrame(animFrame);
  animFrame = 0;
  gamepad.connected = false;
}

function onConnect(e: GamepadEvent) {
  gpIndex = e.gamepad.index;
  gamepad.connected = true;
  gamepad.name = e.gamepad.id.slice(0, 40);
}

function onDisconnect() {
  gpIndex = -1;
  gamepad.connected = false;
  gamepad.name = '';
  gamepad.axes = [0, 0, 0, 0];
}

function applyDeadzone(v: number): number {
  const dz = gamepad.deadzone;
  if (Math.abs(v) < dz) return 0;
  return (v - Math.sign(v) * dz) / (1 - dz);
}

let lastSend = 0;

function poll() {
  if (!gamepad.enabled) return;
  animFrame = requestAnimationFrame(poll);

  const gps = navigator.getGamepads();
  if (gpIndex < 0 || !gps[gpIndex]) return;
  const gp = gps[gpIndex]!;

  const axes = [
    applyDeadzone(gp.axes[0] || 0),
    applyDeadzone(gp.axes[1] || 0),
    applyDeadzone(gp.axes[2] || 0),
    applyDeadzone(gp.axes[3] || 0),
  ];
  gamepad.axes = axes;
  gamepad.buttons = Array.from(gp.buttons).map((b) => b.pressed);

  const now = performance.now();
  if (now - lastSend < 50) return;
  lastSend = now;

  if (!app.drone.connected || !app.drone.armed) return;

  const m = gamepad.channelMap;
  const roll = 1500 + Math.round(axes[m.roll] * (m.invertRoll ? -500 : 500));
  const pitch = 1500 + Math.round(axes[m.pitch] * (m.invertPitch ? -500 : 500));
  const thr = 1500 + Math.round(axes[m.throttle] * (m.invertThrottle ? -500 : 500));
  const yaw = 1500 + Math.round(axes[m.yaw] * (m.invertYaw ? -500 : 500));

  dispatch('rc_override', undefined, {
    channels: [roll, pitch, thr, yaw, 0, 0, 0, 0],
  });
}
