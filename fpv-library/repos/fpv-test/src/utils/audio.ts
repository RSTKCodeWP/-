/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

let audioCtx: AudioContext | null = null;
let motorOsc: OscillatorNode | null = null;
let motorGain: GainNode | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    // Standard cross-browser audio initialization
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

// Esc tone sequence: Dii-Dii-Doo ARM!
export function playEscTones() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const playTone = (freq: number, start: number, duration: number) => {
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();
    
    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, start);
    
    gainNode.gain.setValueAtTime(0, start);
    gainNode.gain.linearRampToValueAtTime(0.06, start + 0.02);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, start + duration - 0.02);
    
    osc.connect(gainNode);
    gainNode.connect(ctx.destination);
    
    osc.start(start);
    osc.stop(start + duration);
  };

  playTone(880, now, 0.12);      // Tone 1
  playTone(1100, now + 0.15, 0.12); // Tone 2
  playTone(1320, now + 0.30, 0.25); // Tone 3 (Final Arm chime)
}

// Beeper beep sound
export function playBeep(freq = 2800, duration = 0.08) {
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gainNode = ctx.createGain();

  osc.type = "square";
  osc.frequency.setValueAtTime(freq, now);

  gainNode.gain.setValueAtTime(0.08, now);
  gainNode.gain.exponentialRampToValueAtTime(0.0001, now + duration);

  osc.connect(gainNode);
  gainNode.connect(ctx.destination);

  osc.start(now);
  osc.stop(now + duration);
}

// Switch toggle mechanical click click
export function playSwitchClick() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gainNode = ctx.createGain();

  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(150, now);
  osc.frequency.exponentialRampToValueAtTime(80, now + 0.02);

  gainNode.gain.setValueAtTime(0.04, now);
  gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.02);

  osc.connect(gainNode);
  gainNode.connect(ctx.destination);

  osc.start(now);
  osc.stop(now + 0.02);
}

// FPV Motor Buzz engine (Dynamic continuous sound based on throttle!)
export function startMotorSound() {
  const ctx = getAudioContext();
  if (!ctx) return;

  if (motorOsc) return; // Already running

  const osc = ctx.createOscillator();
  const gainNode = ctx.createGain();

  // FPV motors sound like screaming angry bees: combination of sawtooth + sine
  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(90, ctx.currentTime);

  gainNode.gain.setValueAtTime(0.001, ctx.currentTime);

  osc.connect(gainNode);
  gainNode.connect(ctx.destination);

  osc.start();
  
  motorOsc = osc;
  motorGain = gainNode;
}

export function updateMotorSound(throttle: number) { // throttle is 0 to 1
  const ctx = getAudioContext();
  if (!ctx || !motorOsc || !motorGain) return;

  const t = ctx.currentTime;
  // Map 0-1 throttle to a roaring FPV sound: 85Hz (idle) to 480Hz (full punch!)
  const frequency = 85 + (throttle * 395);
  // Gain increases from quiet idle to loud hum
  const targetGain = 0.005 + (throttle * 0.035);

  motorOsc.frequency.setTargetAtTime(frequency, t, 0.05);
  motorGain.gain.setTargetAtTime(targetGain, t, 0.05);
}

export function stopMotorSound() {
  if (motorOsc) {
    try {
      motorOsc.stop();
    } catch (e) {}
    motorOsc = null;
  }
  motorGain = null;
}
