/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import { ActiveView, FlightMode, DroneConfig } from "./types";
import { DEFAULT_CONFIG } from "./data/droneParts";
import { playBeep, playSwitchClick } from "./utils/audio";

// Components
import Dashboard from "./components/Dashboard";
import Configurator from "./components/Configurator";
import FpvSimulator from "./components/FpvSimulator";
import Specs from "./components/Specs";
import Academy from "./components/Academy";

// Icons
import { Radio, Battery, Satellite, Volume2, Cpu, Sparkles, AlertTriangle, Settings, BookOpen, FileText, Play } from "lucide-react";

export default function App() {
  const [activeView, setActiveView] = useState<ActiveView>(ActiveView.DASHBOARD);
  const [config, setConfig] = useState<DroneConfig>(DEFAULT_CONFIG);
  
  // Interactive global telemetry controls
  const [isArmed, setIsArmed] = useState(false);
  const [flightMode, setFlightMode] = useState<FlightMode>("ACRO");
  const [analogFeed, setAnalogFeed] = useState(false);
  const [beeperActive, setBeeperActive] = useState(false);

  // Joy-Stick RC transmitter mode-2 variables
  const [throttle, setThrottle] = useState(0); // 0 to 100
  const [yaw, setYaw] = useState(0); // -100 to 100
  const [pitch, setPitch] = useState(0); // -100 to 100
  const [roll, setRoll] = useState(0); // -100 to 100

  // Standard restore config on mount if saved
  useEffect(() => {
    try {
      const stored = localStorage.getItem("apex_fpv_custom_config");
      if (stored) {
        setConfig(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to parse cached quadcopter config:", e);
    }
  }, []);

  // Cycle view with small sound confirmations
  const handleSetView = (view: ActiveView) => {
    playSwitchClick();
    setActiveView(view);
  };

  return (
    <div className="w-full min-h-screen bg-[#050505] text-zinc-100 flex flex-col justify-between items-stretch overflow-hidden font-sans select-none antialiased relative">
      
      {/* Background Texture: Carbon Fiber Pattern */}
      <div className="absolute inset-0 opacity-15 carbon-pattern pointer-events-none z-0" />

      {/* 1. TOP BAR BRAND HEADER WITH INTEGRATED NAVIGATION */}
      <header className="w-full border-b border-zinc-900 bg-[#050505]/95 backdrop-blur-md relative z-30">
        {/* Neon orange/cyan scan-glow bar */}
        <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-cyan-400 via-orange-600 to-transparent" />

        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          
          {/* Brand Logo & Telemetry Arming Status */}
          <div className="flex items-center justify-between md:justify-start gap-4 shrink-0">
            <div className="flex flex-col text-left">
              <div className="text-[9px] tracking-[0.3em] uppercase text-cyan-400 font-bold mb-0.5">
                Sys: {isArmed ? "ARMED (" + flightMode + ")" : "Established"}
              </div>
              <div className="flex items-center gap-2">
                <div 
                  className="text-2xl font-black italic tracking-tighter uppercase cursor-pointer hover:opacity-85 select-none"
                  onClick={() => handleSetView(ActiveView.DASHBOARD)}
                >
                  APEX <span className="text-orange-600 font-extrabold text-shadow-glow">V4</span>
                </div>
                {beeperActive && (
                  <div className="text-[8px] tracking-widest text-yellow-400 animate-pulse font-mono font-bold uppercase border border-yellow-700/40 bg-yellow-950/20 px-1.5 ml-1">
                    [ BUZZ ]
                  </div>
                )}
              </div>
            </div>

            {/* Mobile-only Link display and current throttle reading */}
            <div className="flex items-center gap-3.5 text-xs text-zinc-500 font-mono md:hidden pr-2">
              <span className="flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${isArmed ? "bg-orange-500 animate-ping" : "bg-cyan-400"}`} />
                {isArmed ? "ARMED" : "STABLE"}
              </span>
              <span>THR: <strong className="text-zinc-300">{throttle}%</strong></span>
            </div>
          </div>

          {/* PRIMARY NAVIGATION SWITCH BAR */}
          <nav className="flex items-center justify-start overflow-x-auto gap-1 bg-zinc-950 p-1 border border-zinc-900 rounded-xl no-scrollbar max-w-full">
            <button
              id="nav-telemetry"
              onClick={() => handleSetView(ActiveView.DASHBOARD)}
              className={`py-2 px-3 sm:px-4 rounded-lg text-[9px] sm:text-xs font-black tracking-widest uppercase transition-all flex items-center gap-1.5 cursor-pointer shrink-0 ${
                activeView === ActiveView.DASHBOARD
                  ? "bg-orange-600 text-zinc-100 shadow-[0_2px_10px_rgba(234,88,12,0.3)]"
                  : "text-zinc-500 hover:text-zinc-200"
              }`}
            >
              <Radio size={12} />
              <span>Telemetry</span>
            </button>

            <button
              id="nav-builder"
              onClick={() => handleSetView(ActiveView.CONFIGURATOR)}
              className={`py-2 px-3 sm:px-4 rounded-lg text-[9px] sm:text-xs font-black tracking-widest uppercase transition-all flex items-center gap-1.5 cursor-pointer shrink-0 ${
                activeView === ActiveView.CONFIGURATOR
                  ? "bg-orange-600 text-zinc-100 shadow-[0_2px_10px_rgba(234,88,12,0.3)]"
                  : "text-zinc-500 hover:text-zinc-200"
              }`}
            >
              <Cpu size={12} />
              <span>Builder</span>
            </button>

            <button
              id="nav-academy"
              onClick={() => handleSetView(ActiveView.ACADEMY)}
              className={`py-2 px-3 sm:px-4 rounded-lg text-[9px] sm:text-xs font-black tracking-widest uppercase transition-all flex items-center gap-1.5 cursor-pointer shrink-0 ${
                activeView === ActiveView.ACADEMY
                  ? "bg-orange-600 text-zinc-100 shadow-[0_2px_10px_rgba(234,88,12,0.3)]"
                  : "text-zinc-500 hover:text-zinc-200"
              }`}
            >
              <BookOpen size={12} />
              <span className="text-shadow-neon">Online Academy</span>
            </button>

            <button
              id="nav-specs"
              onClick={() => handleSetView(ActiveView.SPECS)}
              className={`py-2 px-3 sm:px-4 rounded-lg text-[9px] sm:text-xs font-black tracking-widest uppercase transition-all flex items-center gap-1.5 cursor-pointer shrink-0 ${
                activeView === ActiveView.SPECS
                  ? "bg-orange-600 text-zinc-100 shadow-[0_2px_10px_rgba(234,88,12,0.3)]"
                  : "text-zinc-500 hover:text-zinc-200"
              }`}
            >
              <FileText size={12} />
              <span>Specs & Safety</span>
            </button>

            <button
              id="nav-simulator"
              onClick={() => handleSetView(ActiveView.SIMULATOR)}
              className={`py-2 px-3 sm:px-4 rounded-lg text-[9px] sm:text-xs font-black tracking-widest uppercase transition-all flex items-center gap-1.5 cursor-pointer shrink-0 ${
                activeView === ActiveView.SIMULATOR
                  ? "bg-orange-600 text-zinc-100 shadow-[0_2px_10px_rgba(234,88,12,0.3)]"
                  : "text-zinc-500 hover:text-zinc-200"
              }`}
            >
              <Play size={12} />
              <span>Simulator</span>
            </button>
          </nav>

          {/* Desktop telemetry diagnostic readouts */}
          <div className="hidden md:flex gap-6 text-right shrink-0">
            <div className="flex flex-col">
              <span className="text-[8px] uppercase tracking-widest text-[#4f555d] mb-0.5 font-bold">TX LINK STATE</span>
              <span className="text-sm font-mono text-cyan-400 font-extrabold select-none flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${isArmed ? "bg-orange-500 animate-ping" : "bg-emerald-500"}`} />
                {isArmed ? "ARMED" : "STABLE"}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[8px] uppercase tracking-widest text-[#4f555d] mb-0.5 font-bold">TX RSSI</span>
              <span className="text-sm font-mono text-cyan-400 font-extrabold">99%</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[8px] uppercase tracking-widest text-[#4f555d] mb-0.5 font-bold">ESC BATTERY</span>
              <span className="text-sm font-mono text-cyan-400 font-extrabold">22.8V <span className="text-[9px] padding-0 text-zinc-500 font-bold">6S</span></span>
            </div>
          </div>

        </div>
      </header>

      {/* 2. MAIN SWAPPABLE VIEWPORT */}
      <main className="flex-1 w-full bg-[#07090b] relative flex flex-col items-stretch overflow-hidden select-none min-h-[460px]">
        {activeView === ActiveView.DASHBOARD && (
          <Dashboard
            setActiveView={setActiveView}
            isArmed={isArmed}
            flightMode={flightMode}
          />
        )}
        
        {activeView === ActiveView.CONFIGURATOR && (
          <Configurator
            config={config}
            setConfig={setConfig}
          />
        )}

        {activeView === ActiveView.ACADEMY && (
          <Academy />
        )}

        {activeView === ActiveView.SIMULATOR && (
          <FpvSimulator
            config={config}
            isArmed={isArmed}
            setIsArmed={setIsArmed}
            flightMode={flightMode}
            setFlightMode={setFlightMode}
            analogFeed={analogFeed}
            setAnalogFeed={setAnalogFeed}
            beeperActive={beeperActive}
            setBeeperActive={setBeeperActive}
            throttle={throttle}
            setThrottle={setThrottle}
            yaw={yaw}
            setYaw={setYaw}
            pitch={pitch}
            setPitch={setPitch}
            roll={roll}
            setRoll={setRoll}
          />
        )}

        {activeView === ActiveView.SPECS && (
          <Specs />
        )}
      </main>

      {/* 3. COMPACT STANDARD BRAND FOOTER */}
      <footer className="w-full border-t border-zinc-900 bg-[#050505] py-6 px-6 relative z-10 text-center text-xs text-zinc-500 font-mono shrink-0">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-orange-600 font-black tracking-widest text-sm italic">APEX FPV</span>
            <span className="text-zinc-800">|</span>
            <span>THE FPV DIGITAL ACADEMY & TUNER FLIGHT CHASSIS</span>
          </div>
          <div className="text-[10px] text-zinc-600">
            &copy; {new Date().getFullYear()} APEX FPV V4. ALL RIGHTS RESERVED. FLY RESPONSIBLY.
          </div>
        </div>
      </footer>

    </div>
  );
}
