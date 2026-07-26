/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { FRAMES, MOTORS, PROPS, VTXS } from "../data/droneParts";
import { playSwitchClick, playBeep } from "../utils/audio";
import { Check, ShieldCheck, Zap, Radio, Globe, Heart, ShieldAlert, Sparkles, Orbit } from "lucide-react";

export default function Specs() {
  const handleContactSupport = () => {
    playBeep(2200, 0.08);
    setTimeout(() => playBeep(2900, 0.12), 100);
    alert("APEX FPV Global Support Center contacted. System telemetry diagnostics submitted successfully.");
  };

  return (
    <div className="flex-1 w-full bg-[#050505] text-white p-6 md:p-12 overflow-y-auto flex flex-col justify-start relative select-none">
      
      {/* Background visual light elements */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full bg-cyan-500/5 blur-[120px] pointer-events-none" />
      
      {/* Container header from Bold Typography style */}
      <div className="max-w-7xl mx-auto w-full mb-10 border-l-2 border-orange-600 pl-4 py-1 text-left">
        <span className="text-zinc-500 font-mono text-[9px] tracking-[0.3em] uppercase block mb-1">HARDWARE DIRECTORY & GLOBAL CALIBRATIONS</span>
        <h2 className="text-3xl md:text-4xl font-black uppercase tracking-tighter text-zinc-100 italic -skew-x-12">
          SYSTEM SPEC STANDARDS
        </h2>
      </div>

      <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-3 gap-8 items-start flex-1 text-left">
        
        {/* PANEL 1: Elite Class Comparison Matrix */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <div className="bg-[#0b0c0e]/90 rounded-2xl border border-zinc-900 p-6 md:p-8 font-mono relative overflow-hidden backdrop-blur-md">
            <h3 className="text-xs text-orange-400 font-bold uppercase tracking-widest border-b border-zinc-900 pb-3 mb-5 flex justify-between items-center">
              <span>DRONE CLASS MATRIX</span>
              <span className="text-[10px] text-zinc-500 uppercase">Betaflight v4.4 Default profiles</span>
            </h3>

            {/* Matrix comparison table */}
            <div className="overflow-x-auto">
              <table className="w-full text-[11px] text-zinc-400 font-normal leading-relaxed">
                <thead>
                  <tr className="border-b border-zinc-900 text-zinc-500">
                    <th className="pb-3 text-left">PILOT ARCHITECTURE</th>
                    <th className="pb-3 text-center">WEIGHT</th>
                    <th className="pb-3 text-center">VOLTAGE CELLS</th>
                    <th className="pb-3 text-center">PEAK THRUST</th>
                    <th className="pb-3 text-right">TOP VELOCITY</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900">
                  <tr className="hover:bg-zinc-900/10">
                    <td className="py-4 font-bold text-zinc-100 italic">
                      CLASS 5" FREESTYLE (APEX)
                    </td>
                    <td className="text-center text-cyan-400 font-bold">345g</td>
                    <td className="text-center text-zinc-300">6S (22.2V)</td>
                    <td className="text-center text-zinc-350">8.40 kg</td>
                    <td className="text-right text-orange-500 font-black italic -skew-x-12">175 km/h</td>
                  </tr>
                  <tr className="hover:bg-zinc-900/10">
                    <td className="py-4 font-bold text-zinc-100 italic">
                      CLASS 6" LONG RANGE (SCYTHE)
                    </td>
                    <td className="text-center text-cyan-400 font-bold">368g</td>
                    <td className="text-center text-zinc-300">6S (22.2V)</td>
                    <td className="text-center font-semibold text-zinc-350">7.40 kg</td>
                    <td className="text-right text-orange-500 font-black italic -skew-x-12">190 km/h</td>
                  </tr>
                  <tr className="hover:bg-zinc-900/10">
                    <td className="py-4 font-bold text-zinc-100 italic">
                      CLASS 5" FAST TOOTHPICK (SCREAMER)
                    </td>
                    <td className="text-center text-cyan-400 font-bold">291g</td>
                    <td className="text-center text-zinc-300">4S / 6S compat</td>
                    <td className="text-center font-bold text-zinc-350">9.80 kg</td>
                    <td className="text-right text-cyan-400 font-black italic -skew-x-12">215 km/h</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex items-start gap-4 bg-zinc-950/40 p-4 rounded-xl border border-zinc-900">
              <ShieldCheck className="text-emerald-400 shrink-0 mt-0.5" size={16} />
              <p className="text-[10px] text-zinc-500 leading-relaxed font-sans font-normal">
                APEX FPV pre-flashes and tunes every quadcopter build with official custom ESC RPM filtering, bidirectional Dshot, and static notch filter damping tailored strictly to motor weights.
              </p>
            </div>
          </div>

          {/* Core Hardware Standard specs list */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full font-mono">
            {/* VTX Transmission guidelines specs */}
            <div className="bg-[#0b0c0e]/80 p-6 rounded-xl border border-zinc-900 flex flex-col gap-3">
              <span className="text-[10px] text-cyan-400 tracking-[0.2em] font-extrabold uppercase">[ DIGITAL VS ANALOG FEED ]</span>
              <p className="text-zinc-500 text-[11px] leading-relaxed font-sans">
                Digital units stream stunning HD feeds but add a minor transceiver processing latency of ~28ms. Pure analog outputs near-zero latency but features retro grain, color bleeding, and antenna fuzz.
              </p>
            </div>
            {/* Battery requirements */}
            <div className="bg-[#0b0c0e]/80 p-6 rounded-xl border border-zinc-900 flex flex-col gap-3">
              <span className="text-[10px] text-orange-600 tracking-[0.2em] font-extrabold uppercase">[ BATTERY RECOMMENDATION ]</span>
              <p className="text-zinc-500 text-[11px] leading-relaxed font-sans font-normal">
                We strongly advise selecting premium 6S LiPo batteries rated above 130C discharge capacities to avoid extreme battery sag or motor dropouts during rapid full-throttle loops.
              </p>
            </div>
          </div>
        </div>

        {/* PANEL 2: Global Service support diagnostics side box */}
        <div className="lg:col-span-1 flex flex-col gap-6 w-full font-mono">
          <div className="bg-[#0b0c0e]/90 border border-zinc-900 rounded-2xl p-6 flex flex-col gap-4 text-left relative overflow-hidden backdrop-blur-md">
            <div className="absolute top-0 bottom-0 right-0 w-1.5 bg-gradient-to-b from-orange-600 to-cyan-400" />
            <h3 className="text-xs text-zinc-300 font-bold uppercase tracking-wider border-b border-zinc-905 pb-3 flex items-center gap-1.5 justify-between">
              <span>SYSTEM GUARANTEE</span>
              <Sparkles size={11} className="text-orange-500" />
            </h3>

            <div className="flex flex-col gap-3 text-[11px] text-zinc-400 font-sans">
              <div className="flex items-start gap-2.5">
                <Check size={12} className="text-cyan-400 mt-0.5 shrink-0" />
                <span>100% High-Grade Carbon Fiber build structure guarantee.</span>
              </div>
              <div className="flex items-start gap-2.5">
                <Check size={12} className="text-cyan-400 mt-0.5 shrink-0" />
                <span>Advanced PID pre-tuned dynamic flights right out of box.</span>
              </div>
              <div className="flex items-start gap-2.5">
                <Check size={12} className="text-cyan-400 mt-0.5 shrink-0" />
                <span>Free lifetime ESC warranty covering rotor node parts.</span>
              </div>
            </div>

            <button
              onClick={handleContactSupport}
              className="mt-4 px-4 py-3 bg-orange-600 hover:bg-orange-500 text-zinc-100 rounded-full uppercase tracking-widest text-[10px] font-black cursor-pointer transition-all w-full text-center hover-glow-orange"
            >
              Contact Global Labs
            </button>
          </div>

          <div className="bg-[#0b0c0e]/80 p-6 rounded-2xl border border-zinc-900 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Orbit className="text-cyan-400" size={16} />
              <span className="text-xs font-bold tracking-wider text-zinc-300 uppercase">RPM Filtering</span>
            </div>
            <p className="text-zinc-500 text-[11px] font-sans leading-relaxed">
              Every motor frame features harmonic spectrum tracking to filter high-frequency oscillations. Gives your flight controller perfectly clean gyro readings for pristine micro-tuning angles.
            </p>
          </div>
        </div>

      </div>

      {/* Safety Protocol Section */}
      <div className="max-w-7xl mx-auto w-full mt-8">
        <div className="bg-[#0b0c0e]/95 rounded-2xl border border-zinc-900 p-6 md:p-8 font-mono relative overflow-hidden backdrop-blur-md">
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-red-600/5 to-transparent pointer-events-none" />
          
          <h3 className="text-xs text-red-500 font-bold uppercase tracking-widest border-b border-zinc-900 pb-3 mb-5 flex justify-between items-center">
            <span>BATTERY SAFETY PROTOCOL // LIPO VOLTAGE CRITERIA</span>
            <span className="text-[10px] text-zinc-500 uppercase">Emergency Thresholds</span>
          </h3>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 text-left flex flex-col justify-between gap-4">
              <div>
                <h4 className="text-zinc-100 font-black uppercase text-sm mb-2 italic flex items-center gap-2">
                  <ShieldAlert className="text-red-500 shrink-0" size={16} />
                  FAILSAFE STANDARDS
                </h4>
                <p className="text-zinc-500 text-[11px] font-sans leading-relaxed">
                  Real-time voltage monitoring mitigates battery &apos;sag&apos; during full-throttle loops. Operating lithium packs inside safety limits protects the craft from low-power reboot locks, motor dropouts, and sudden physical desyncs.
                </p>
              </div>
              <div className="flex items-start gap-2.5 bg-red-950/20 p-4 rounded-xl border border-red-955/40 text-red-400">
                <span className="text-[10px] leading-relaxed font-sans">
                  <strong>RISK ADVISORY:</strong> Over-discharging any pack past <strong>3.00V per cell</strong> causes irreversible heat expansion, anode oxidation, and permanent capacity destruction.
                </span>
              </div>
            </div>

            <div className="lg:col-span-2 overflow-x-auto flex flex-col gap-4">
              <table className="w-full text-[11px] text-zinc-400 font-normal leading-relaxed">
                <thead>
                  <tr className="border-b border-zinc-900 text-zinc-500">
                    <th className="pb-3 text-left">CELL CONFIGURATION</th>
                    <th className="pb-3 text-center">FULL NOMINAL</th>
                    <th className="pb-3 text-center">LOW WARN (3.50V)</th>
                    <th className="pb-3 text-center text-orange-500 font-black">FAILSAFE LIMIT (3.30V)</th>
                    <th className="pb-3 text-right text-red-500">CRITICAL DAMAGE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900">
                  <tr className="hover:bg-zinc-900/10">
                    <td className="py-4 font-bold text-zinc-100 italic">4S LIPO (14.80V)</td>
                    <td className="text-center text-cyan-400 font-bold">16.80V</td>
                    <td className="text-center text-zinc-300">14.00V</td>
                    <td className="text-center text-orange-500 font-black italic -skew-x-12">13.20V</td>
                    <td className="text-right text-red-500 font-black italic -skew-x-12">Under 12.00V</td>
                  </tr>
                  <tr className="hover:bg-zinc-900/10">
                    <td className="py-4 font-bold text-zinc-100 italic">6S LIPO (22.20V)</td>
                    <td className="text-center text-cyan-400 font-bold">25.20V</td>
                    <td className="text-center text-zinc-300">21.00V</td>
                    <td className="text-center text-orange-500 font-black italic -skew-x-12">19.80V</td>
                    <td className="text-right text-red-500 font-black italic -skew-x-12">Under 18.00V</td>
                  </tr>
                </tbody>
              </table>

              <div className="text-[10px] text-zinc-500 leading-relaxed font-sans text-left bg-zinc-950/40 p-3.5 rounded-xl border border-zinc-900">
                <strong>STORAGE BEST PRACTICE:</strong> Balance-charge storage cycles to <strong>3.80V–3.85V per cell</strong> within 48 hours is mandatory for battery chemistry preservation. Never store completely exhausted cells.
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
