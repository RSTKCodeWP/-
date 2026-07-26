/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { FRAMES, MOTORS, PROPS, VTXS } from "../data/droneParts";
import { DroneConfig, DronePart } from "../types";
import { playBeep, playSwitchClick } from "../utils/audio";
import { motion, AnimatePresence } from "motion/react";
import { Shield, Zap, RefreshCw, Cpu, Radio, DollarSign, Scale, Gauge, Percent, CircleAlert, Eye } from "lucide-react";

interface ConfiguratorProps {
  config: DroneConfig;
  setConfig: (config: DroneConfig) => void;
}

export default function Configurator({ config, setConfig }: ConfiguratorProps) {
  const [activeCategory, setActiveCategory] = useState<"frame" | "motor" | "props" | "vtx">("frame");
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeSchematicPin, setActiveSchematicPin] = useState<string | null>(null);

  // Dynamic Center of Gravity weights and locations tuning states
  const [rightPanelMode, setRightPanelMode] = useState<"schematic" | "cog">("cog");
  const [batOffsetY, setBatOffsetY] = useState<number>(5);
  const [batOffsetX, setBatOffsetX] = useState<number>(0);
  const [goproMounted, setGoproMounted] = useState<boolean>(false);
  const [debrisOnFr, setDebrisOnFr] = useState<boolean>(false);

  // Category list
  const CATEGORIES = [
    { id: "frame", name: "CHASSIS / FRAME", parts: FRAMES },
    { id: "motor", name: "PROPULSION MOTORS", parts: MOTORS },
    { id: "props", name: "AERODYNAMIC PROPS", parts: PROPS },
    { id: "vtx", name: "VIDEO TELEMETRY VTX", parts: VTXS }
  ];

  // Calculations
  const calculatedDryWeight = config.frame.weight + (config.motor.weight * 4) + config.props.weight + config.vtx.weight;
  // Standard 6S 1300mAh high C-rate LiPo battery weighs around 220g
  const batteryWeight = 220;

  // Dynamic weight alignment offsets (mm) and weight calculations
  const wheelbaseNum = parseFloat(config.frame.specs["Wheelbase"]?.toString() || "225");
  const lx = Math.round((wheelbaseNum * 0.707) / 2);
  const ly = Math.round((wheelbaseNum * 0.707) / 2);

  const cogComponents = [
    { name: "Chassis Core", weight: config.frame.weight, x: 0, y: 0 },
    { name: "FC System Stack", weight: 25, x: 0, y: 0 },
    { name: "VTX System", weight: config.vtx.weight, x: 0, y: -45 }, // rear mounted
    { name: "Motor FL & Prop", weight: config.motor.weight + (config.props.weight / 4), x: -lx, y: ly },
    { name: "Motor FR & Prop", weight: config.motor.weight + (config.props.weight / 4), x: lx, y: ly },
    { name: "Motor RL & Prop", weight: config.motor.weight + (config.props.weight / 4), x: -lx, y: -ly },
    { name: "Motor RR & Prop", weight: config.motor.weight + (config.props.weight / 4), x: lx, y: -ly },
    { name: "LiPo Battery Pack", weight: batteryWeight, x: batOffsetX, y: batOffsetY },
    ...(goproMounted ? [{ name: "Hero Action Cam", weight: 120, x: 0, y: 65 }] : []),
    ...(debrisOnFr ? [{ name: "Arm Debris FR", weight: 12, x: lx, y: ly }] : [])
  ];

  let calculatedTotalMass = 0;
  let weightedSumX = 0;
  let weightedSumY = 0;

  cogComponents.forEach((c) => {
    calculatedTotalMass += c.weight;
    weightedSumX += c.weight * c.x;
    weightedSumY += c.weight * c.y;
  });

  const cogX = weightedSumX / calculatedTotalMass;
  const cogY = weightedSumY / calculatedTotalMass;
  const cogDist = Math.sqrt(cogX * cogX + cogY * cogY);

  // Exponential decay rating for visual feedback: index 100% when balance is zero
  const balanceEfficiency = Math.max(0, Math.min(100, Math.round(100 - (cogDist * 3.8))));

  // Adjusted Wet Weight depending on GoPro and debris payloads for maximum accuracy!
  const calculatedWetWeight = calculatedDryWeight + batteryWeight + (goproMounted ? 120 : 0) + (debrisOnFr ? 12 : 0);

  const totalPrice = config.frame.price + config.motor.price + config.props.price + config.vtx.price + (goproMounted ? 399 : 0);

  // Peak thrust calculations
  // We extract "Peak Thrust" string like "2.1 kg", multiply by 4 to get total thrust
  const getSingleThrustKg = (): number => {
    const thrustStr = config.motor.specs["Peak Thrust"]?.toString() || "2.0";
    return parseFloat(thrustStr);
  };
  const totalThrustKg = getSingleThrustKg() * 4;
  const wetWeightKg = calculatedWetWeight / 1000;
  const thrustToWeightRatio = Math.round((totalThrustKg / wetWeightKg) * 10) / 10;

  // Max speed theory: pitch * kv rating, scaled by frame efficiency
  const pitchVal = parseFloat(config.props.specs["Pitch"]?.toString() || "4.3");
  const kvVal = parseFloat(config.motor.specs["KV Rating"]?.toString() || "1900");
  const theoreticalTopSpeed = Math.round(100 + (pitchVal * (kvVal / 100) * (config.frame.id === "screamer-5" ? 1.45 : 1.3)));

  // Estimated Flight Time
  const estimatedFlightTimeMin = Math.round((1400 / (calculatedWetWeight * 0.45 + (10 - pitchVal) * 10)) * 10) / 10;

  const handleSelectPart = (part: DronePart) => {
    playSwitchClick();
    setConfig({
      ...config,
      [activeCategory]: part
    });
  };

  const handleSaveConfig = () => {
    playBeep(2100, 0.12);
    setTimeout(() => playBeep(2800, 0.12), 100);
    localStorage.setItem("apex_fpv_custom_config", JSON.stringify(config));
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  // Node schematics list shown on the visual vector SVG map of the FPV drone
  const SCHEMATIC_PINS = [
    { id: "cam", x: "128px", y: "45px", title: "FPV Lens & VTX", desc: config.vtx.name },
    { id: "motor_fl", x: "65px", y: "85px", title: "Motor Front-Left", desc: `${config.motor.name} + ${config.props.name}` },
    { id: "motor_fr", x: "191px", y: "85px", title: "Motor Front-Right", desc: `${config.motor.name} + ${config.props.name}` },
    { id: "fc", x: "128px", y: "128px", title: "Apex Flight Controller", desc: "ICM42688 Gyro / STM32F405 MCU" },
    { id: "bat", x: "128px", y: "185px", title: "LiPo Battery Tray", desc: "Supports 6S 1300-1550mAh" },
    { id: "motor_rl", x: "65px", y: "171px", title: "Motor Rear-Left", desc: `${config.motor.name} + ${config.props.name}` },
    { id: "motor_rr", x: "191px", y: "171px", title: "Motor Rear-Right", desc: `${config.motor.name} + ${config.props.name}` }
  ];

  return (
    <div className="flex-1 w-full bg-[#050505] text-white p-6 md:p-12 overflow-y-auto flex flex-col justify-start relative select-none">
      
      {/* Background decoration elements */}
      <div className="absolute top-10 right-10 w-80 h-80 rounded-full bg-orange-500/5 blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-10 w-96 h-96 rounded-full bg-cyan-500/5 blur-3xl pointer-events-none" />

      {/* Breadcrumb / Title Bar - Styled beautifully with left border parameter indicators */}
      <div className="max-w-7xl mx-auto w-full flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-10 border-l-2 border-orange-600 pl-4 py-1">
        <div className="text-left animate-fade-in">
          <span className="text-zinc-500 font-mono text-[9px] tracking-[0.3em] uppercase block mb-1">TUNING LAB // ASSEMBLY STATION</span>
          <h2 className="text-3xl md:text-4xl font-black italic -skew-x-12 tracking-tighter uppercase leading-none text-zinc-100 flex items-center gap-2">
            APEX CONFIGURATOR
            <span className="text-orange-600 not-italic">V4</span>
          </h2>
        </div>
        
        {/* Save button with glowing action state from design HTML */}
        <button
          onClick={handleSaveConfig}
          className="relative px-8 py-3.5 bg-orange-600 hover:bg-orange-500 text-zinc-100 font-extrabold font-mono text-xs tracking-widest rounded-full uppercase cursor-pointer hover-glow-orange transition-all duration-150 flex items-center gap-2"
        >
          {saveSuccess ? (
            <span className="text-zinc-100 flex items-center gap-1.5 animate-pulse">
              [ CONFIG RECORDED ]
            </span>
          ) : (
            <span className="flex items-center gap-1.5 font-black uppercase tracking-[0.15em]">
              <Cpu size={12} className="animate-spin" />
              RECORD BUILD CONFIG
            </span>
          )}
        </button>
      </div>

      {/* Main Grid Layout: Interactive Builder */}
      <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-8 items-start flex-1">
        
        {/* LEFT COMPONENT: 2-column Parts Selection List & Options (6 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-6 w-full relative z-10 text-left">
          
          {/* Category Tabs */}
          <div className="flex bg-[#0b0c0e] border border-zinc-900 rounded-lg p-1.5 gap-1.5 w-full overflow-x-auto shadow-inner">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => {
                  playSwitchClick();
                  setActiveCategory(cat.id as any);
                }}
                className={`flex-1 py-2 px-3 text-center rounded-md font-mono text-[10px] tracking-wider uppercase font-black cursor-pointer transition-all whitespace-nowrap ${
                  activeCategory === cat.id
                    ? "bg-zinc-900 text-zinc-100 shadow-xl border-l-2 border-orange-600"
                    : "text-zinc-500 hover:text-zinc-350 hover:bg-zinc-900/40"
                }`}
              >
                {cat.id === activeCategory ? <span className="text-orange-500 mr-1.5">●</span> : null}
                {cat.id}
              </button>
            ))}
          </div>

          {/* Active selection column grid */}
          <div className="flex flex-col gap-4">
            {CATEGORIES.find(c => c.id === activeCategory)?.parts.map((p) => {
              const isSelected = config[activeCategory].id === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => handleSelectPart(p)}
                  className={`relative p-5 md:p-6 rounded-2xl border text-left cursor-pointer transition-all ${
                    isSelected
                      ? "bg-[#0b0c0f]/95 border-cyan-400 shadow-[0_4px_30px_rgba(6,182,212,0.15)] md:translate-x-1"
                      : "bg-[#0b0c0e]/60 border-zinc-900 hover:border-zinc-800 hover:bg-[#0b0c0f]"
                  }`}
                >
                  {/* Selected check highlight glow */}
                  {isSelected && (
                    <div className="absolute top-0 bottom-0 left-0 w-1 bg-cyan-400 rounded-l-2xl" />
                  )}

                  <div className="flex justify-between items-start gap-4 mb-2">
                    <div>
                      <h4 className={`text-base md:text-lg font-black font-mono tracking-tight uppercase ${isSelected ? "text-cyan-400" : "text-zinc-100"}`}>
                        {p.name}
                      </h4>
                      <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest bg-zinc-950/40 px-2 py-0.5 mt-1.5 inline-block rounded">
                        WEIGHT: {p.weight}g
                      </span>
                    </div>
                    <span className={`font-mono text-base md:text-lg font-black italic -skew-x-12 ${isSelected ? "text-orange-500" : "text-zinc-400"}`}>
                      ${p.price}
                    </span>
                  </div>

                  <p className="text-xs text-zinc-400 leading-relaxed font-sans mb-4 font-normal">
                    {p.description}
                  </p>

                  {/* Inline spec bullet indicators */}
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2 pt-4 border-t border-zinc-900 text-[10px] font-mono text-zinc-500">
                    {Object.entries(p.specs).slice(0, 4).map(([k, v]) => (
                      <div key={k} className="flex justify-between border-l border-zinc-950/80 pl-2">
                        <span>{k}:</span>
                        <span className="text-zinc-400 font-extrabold">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

        </div>

        {/* RIGHT COMPONENT: Spec Calculations & Schematic Map (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-6 w-full relative z-10 text-left font-mono">
          
          {/* Diagnostic spec calculator panel with elegant technical borders */}
          <div className="bg-[#0b0c0f]/90 rounded-2xl border border-zinc-900 p-6 font-mono relative overflow-hidden backdrop-blur-md">
            <div className="absolute top-0 right-0 w-24 h-24 bg-linear-to-bl from-cyan-400/5 to-transparent pointer-events-none" />
            <h3 className="text-xs text-zinc-400 font-bold uppercase tracking-widest border-b border-zinc-900 pb-3 mb-5 flex items-center justify-between">
              <span>DYNAMIC TELEMETRY MATH</span>
              <span className="text-[9px] text-cyan-400 animate-pulse font-extrabold">● STABLE LINK</span>
            </h3>

            <div className="grid grid-cols-2 gap-4">
              {/* Thrust ratio indicator box */}
              <div className="bg-[#050505]/40 p-4 rounded-xl border border-zinc-900 text-left">
                <span className="text-zinc-500 text-[9px] uppercase font-bold">Thrust-Ratio</span>
                <div className="text-2xl font-black text-[#ff4d00] mt-1 italic -skew-x-12 flex items-baseline gap-1">
                  {thrustToWeightRatio} <span className="text-xs font-bold text-zinc-500 not-italic">:1</span>
                </div>
                <div className="w-full bg-zinc-950 h-1.5 rounded-full mt-2.5 overflow-hidden border border-zinc-900">
                  <div
                    className="h-full bg-orange-600 rounded-full"
                    style={{ width: `${Math.min(100, (thrustToWeightRatio / 22) * 100)}%` }}
                  />
                </div>
                <span className="text-[8px] text-zinc-500 mt-2 block font-sans">FREESTYLE LAB IS 8:1</span>
              </div>

              {/* Total mass */}
              <div className="bg-[#050505]/40 p-4 rounded-xl border border-zinc-900 text-left">
                <span className="text-zinc-500 text-[9px] uppercase font-bold">AuW Takeoff Mass</span>
                <div className="text-2xl font-black text-cyan-400 mt-1 italic -skew-x-12 flex items-baseline gap-1">
                  {calculatedWetWeight} <span className="text-xs font-bold text-zinc-500 not-italic">g</span>
                </div>
                <span className="text-[8px] text-zinc-500 mt-2 block font-sans">Includes 220g 6S LiPo</span>
              </div>

              {/* Top Velocity theoretical */}
              <div className="bg-[#050505]/40 p-4 rounded-xl border border-zinc-900 text-left">
                <span className="text-zinc-500 text-[9px] uppercase font-bold">Peak Velocity Est</span>
                <div className="text-2xl font-black text-orange-500 mt-1 italic -skew-x-12 flex items-baseline gap-1">
                  {theoreticalTopSpeed} <span className="text-xs font-bold text-zinc-500 not-italic">kmh</span>
                </div>
                <span className="text-[8px] text-zinc-500 mt-2 block font-sans">Estimated speed corridor</span>
              </div>

              {/* Cruising Flight Time */}
              <div className="bg-[#050505]/40 p-4 rounded-xl border border-zinc-900 text-left">
                <span className="text-zinc-500 text-[9px] uppercase font-bold">Cruising Standard</span>
                <div className="text-2xl font-black text-emerald-400 mt-1 italic -skew-x-12 flex items-baseline gap-1">
                  {estimatedFlightTimeMin} <span className="text-xs font-bold text-zinc-500 not-italic">min</span>
                </div>
                <span className="text-[8px] text-zinc-500 mt-2 block font-sans">Based on {pitchVal}" pitch load</span>
              </div>
            </div>

            {/* Price check box */}
            <div className="mt-6 border-t border-zinc-900 pt-4 flex items-center justify-between">
              <div className="flex flex-col text-left">
                <span className="text-zinc-500 text-[9px] uppercase font-bold">ESTIMATED BILL OF MATERIALS</span>
                <span className="text-2xl font-black text-zinc-100 italic -skew-x-12 mt-1">${totalPrice}</span>
              </div>
              <span className="text-[9px] text-zinc-500 max-w-[180px] text-right font-sans">
                DShot bidirectional tune pre-assembled and shipped.
              </span>
            </div>
          </div>

          {/* Interactive Blueprint & Center of Gravity (COG) Vector Map */}
          <div className="bg-[#0b0c0f]/90 rounded-2xl border border-zinc-900 p-6 text-center flex flex-col items-center backdrop-blur-md">
            
            {/* Toggle header between modes */}
            <div className="text-left w-full mb-4 pb-2 border-b border-zinc-900 flex justify-between items-center font-mono">
              <div className="flex bg-zinc-950 p-1 rounded-lg gap-1 border border-zinc-900">
                <button
                  type="button"
                  onClick={() => { playSwitchClick(); setRightPanelMode("cog"); }}
                  className={`px-3 py-1 rounded text-[9px] uppercase font-black transition-all cursor-pointer ${
                    rightPanelMode === "cog"
                      ? "bg-zinc-900 text-orange-500 font-extrabold border-l border-orange-500"
                      : "text-zinc-500 hover:text-zinc-350"
                  }`}
                >
                  COG BALANCER
                </button>
                <button
                  type="button"
                  onClick={() => { playSwitchClick(); setRightPanelMode("schematic"); }}
                  className={`px-3 py-1 rounded text-[9px] uppercase font-black transition-all cursor-pointer ${
                    rightPanelMode === "schematic"
                      ? "bg-zinc-900 text-cyan-400 font-extrabold border-l border-cyan-400"
                      : "text-zinc-500 hover:text-zinc-350"
                  }`}
                >
                  BLUEPRINT
                </button>
              </div>
              <span className="text-[8px] text-zinc-500 uppercase tracking-widest font-black">AERO LAB V4</span>
            </div>

            {rightPanelMode === "cog" ? (
              <div className="w-full flex flex-col items-center">
                {/* 2D Coordinate Grid Canvas for COG */}
                <div className="w-64 h-64 relative bg-[#040404]/90 border-2 border-zinc-900 rounded-2xl flex items-center justify-center p-2 shadow-inner overflow-hidden">
                  
                  {/* Visual grid overlay lines */}
                  <div className="absolute inset-0 grid grid-cols-10 grid-rows-10 opacity-[0.03] pointer-events-none">
                    {Array.from({ length: 11 }).map((_, i) => (
                      <div key={`vc-${i}`} className="absolute top-0 bottom-0 w-px bg-white" style={{ left: `${i * 10}%` }} />
                    ))}
                    {Array.from({ length: 11 }).map((_, i) => (
                      <div key={`hc-${i}`} className="absolute left-0 right-0 h-px bg-white" style={{ top: `${i * 10}%` }} />
                    ))}
                  </div>

                  {/* Absolute axis guidelines */}
                  <div className="absolute h-full w-px bg-zinc-900/35" />
                  <div className="absolute w-full h-px bg-zinc-900/35" />

                  {/* Structural Frame arm visuals representing Wheelbase */}
                  <svg width="200" height="200" viewBox="0 0 200 200" fill="none" className="absolute opacity-20 text-zinc-600 pointer-events-none">
                    <line x1="100" y1="100" x2="40" y2="40" stroke="currentColor" strokeWidth="2" strokeDasharray="3 3" />
                    <line x1="100" y1="100" x2="160" y2="40" stroke="currentColor" strokeWidth="2" strokeDasharray="3 3" />
                    <line x1="100" y1="100" x2="40" y2="160" stroke="currentColor" strokeWidth="2" strokeDasharray="3 3" />
                    <line x1="100" y1="100" x2="160" y2="160" stroke="currentColor" strokeWidth="2" strokeDasharray="3 3" />
                    <circle cx="100" cy="100" r="12" stroke="currentColor" strokeWidth="1" />
                  </svg>

                  {/* Physical Components Position Plot Markers */}
                  {/* FL Motor */}
                  <div className="absolute w-2 h-2 rounded-full bg-zinc-800 border border-zinc-600 shadow-[0_0_6px_rgba(255,255,255,0.1)]" style={{ left: 'calc(50% - 60px - 4px)', top: 'calc(50% - 60px - 4px)' }} title="FL Motor" />
                  {/* FR Motor */}
                  <div className="absolute w-2 h-2 rounded-full bg-zinc-800 border border-zinc-600 shadow-[0_0_6px_rgba(255,255,255,0.1)]" style={{ left: 'calc(50% + 60px - 4px)', top: 'calc(50% - 60px - 4px)' }} title="FR Motor" />
                  {/* RL Motor */}
                  <div className="absolute w-2 h-2 rounded-full bg-zinc-800 border border-zinc-600 shadow-[0_0_6px_rgba(255,255,255,0.1)]" style={{ left: 'calc(50% - 60px - 4px)', top: 'calc(50% + 60px - 4px)' }} title="RL Motor" />
                  {/* RR Motor */}
                  <div className="absolute w-2 h-2 rounded-full bg-zinc-800 border border-zinc-600 shadow-[0_0_6px_rgba(255,255,255,0.1)]" style={{ left: 'calc(50% + 60px - 4px)', top: 'calc(50% + 60px - 4px)' }} title="RR Motor" />

                  {/* Rear mounted VTX module */}
                  <div className="absolute w-3 h-1.5 bg-violet-600/50 border border-violet-500 rounded-sm" style={{ left: 'calc(50% - 6px)', top: 'calc(50% + 45px - 3px)' }} title="Rear VTX Unit" />

                  {/* Front Mounted GoPro payload toggle */}
                  {goproMounted && (
                    <div className="absolute w-4.5 h-3 bg-rose-600/60 border border-rose-500 rounded-sm flex items-center justify-center animate-pulse" style={{ left: 'calc(50% - 9px)', top: 'calc(50% - 65px - 6px)' }} title="Front Action Camera">
                      <span className="text-[5px] text-rose-200">GP</span>
                    </div>
                  )}

                  {/* Front-Right Mud Debris arm payload */}
                  {debrisOnFr && (
                    <div className="absolute w-3 h-3 bg-emerald-600/60 border border-emerald-500 rounded-full animate-bounce" style={{ left: 'calc(50% + 60px - 6px)', top: 'calc(50% - 60px - 6px)' }} title="Mud/Grass on Prop" />
                  )}

                  {/* LiPo Battery visual box (slides based on sliders) */}
                  <div
                    className="absolute w-6 h-12 bg-amber-600/25 border-2 border-amber-500/70 rounded-md flex items-center justify-center transition-all duration-150 ease-out shadow-lg shadow-amber-950/20"
                    style={{
                      left: `calc(50% + ${batOffsetX * 1.5}px - 12px)`,
                      top: `calc(50% - ${batOffsetY * 1.5}px - 24px)`
                    }}
                  >
                    <span className="text-[6px] text-amber-400 font-mono font-black scale-75">LiPo</span>
                  </div>

                  {/* Golden Gyroscope Geometric Center Target (0,0) */}
                  <div className="absolute w-3.5 h-3.5 border border-emerald-500/80 rounded-full flex items-center justify-center pointer-events-none">
                    <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full" />
                  </div>
                  <span className="absolute text-[8px] text-emerald-500 opacity-60 font-mono" style={{ left: 'calc(50% + 10px)', top: 'calc(50% - 15px)' }}>
                    GYRO CR (0,0)
                  </span>

                  {/* Real-time Dynamic Center of Gravity Target Crosshair */}
                  <div
                    className="absolute w-5 h-5 border-2 border-orange-500 rounded-full flex items-center justify-center animate-pulse transition-all duration-150 ease-out shadow-[0_0_15px_rgba(234,88,12,0.8)] bg-zinc-950/20"
                    style={{
                      left: `calc(50% + ${cogX * 1.5}px - 10px)`,
                      top: `calc(50% - ${cogY * 1.5}px - 10px)`
                    }}
                  >
                    <div className="w-2 h-2 bg-orange-600 rounded-full" />
                    {/* Dynamic offset vector line between center and COG */}
                    <svg className="absolute overflow-visible pointer-events-none" style={{ left: 10, top: 10 }}>
                      <line
                        x1={0}
                        y1={0}
                        x2={-cogX * 1.5}
                        y2={cogY * 1.5}
                        stroke="#ea580c"
                        strokeWidth="1.5"
                        strokeDasharray="2 2"
                      />
                    </svg>
                  </div>

                </div>

                {/* Dashboard Stats Readout for Balance metrics */}
                <div className="w-full mt-4 grid grid-cols-3 gap-2 bg-zinc-950/60 p-3.5 border border-zinc-900 rounded-xl text-left font-mono">
                  <div className="flex flex-col">
                    <span className="text-[8px] text-zinc-500 uppercase font-black">COG Offset-X</span>
                    <span className={`text-xs font-black mt-1 ${Math.abs(cogX) > 1.5 ? "text-orange-500" : "text-zinc-200"}`}>
                      {cogX > 0 ? "+" : ""}{cogX.toFixed(1)} mm
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[8px] text-zinc-500 uppercase font-black">COG Offset-Y</span>
                    <span className={`text-xs font-black mt-1 ${Math.abs(cogY) > 2.5 ? "text-orange-500" : "text-zinc-200"}`}>
                      {cogY > 0 ? "+" : ""}{cogY.toFixed(1)} mm
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[8px] text-zinc-500 uppercase font-black">MOMENT SCORE</span>
                    <span className={`text-xs font-black mt-1 ${
                      balanceEfficiency > 92 ? "text-emerald-400" : balanceEfficiency > 75 ? "text-yellow-500" : "text-red-500"
                    }`}>
                      {balanceEfficiency}%
                    </span>
                  </div>
                </div>

                {/* Real-time Assessment & Correction Advice Panel */}
                <div className="w-full mt-3 p-3 bg-zinc-950/40 rounded-xl border border-zinc-900 text-[10px] leading-relaxed font-sans text-left flex items-start gap-2.5">
                  <CircleAlert className={`shrink-0 mt-0.5 ${
                    cogDist < 2.5 ? "text-emerald-500" : "text-amber-500"
                  }`} size={14} />
                  <div>
                    {cogDist < 2.5 ? (
                      <span className="text-emerald-400 font-bold block uppercase tracking-wide">RIG PERFECTLY BALANCED</span>
                    ) : (
                      <span className="text-amber-500 font-bold block uppercase tracking-wide">PID COMPENSATION ALERT</span>
                    )}
                    <span className="text-zinc-400 block mt-0.5 font-normal leading-relaxed">
                      {cogDist < 2.5 
                        ? "Center of gravity is perfectly aligned with the FC gyro core coordinate axis. Enjoy smooth drift-free acrobatics and cool motor Temps."
                        : cogY < -2.5
                          ? `Rear motors are bearing +${Math.round(Math.abs(cogY) * 2.8)}% extra friction. Slide LiPo battery SLIGHTLY FORWARD (+) on strap.`
                          : cogY > 2.5
                            ? `Front motors are bearing +${Math.round(cogY * 2.8)}% extra friction. Slide LiPo battery BACKWARD (-) on strap.`
                            : "Batteries are mostly balanced. Tweak horizontal offsets to prevent off-axis tracking on high-G roll-outs."
                      }
                    </span>
                  </div>
                </div>

                {/* Calibration Sliders */}
                <div className="w-full mt-4 space-y-3.5 pt-3.5 border-t border-zinc-900 text-left font-mono">
                  {/* Battery Strap Y */}
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between text-[9px] font-black text-zinc-500 uppercase leading-none">
                      <span>LiPo Battery Strap Y-Slide</span>
                      <span className="text-amber-500 font-black">{batOffsetY > 0 ? "+" : ""}{batOffsetY} mm</span>
                    </div>
                    <input
                      type="range"
                      min="-30"
                      max="30"
                      value={batOffsetY}
                      onChange={(e) => {
                        playSwitchClick();
                        setBatOffsetY(parseInt(e.target.value));
                      }}
                      className="w-full accent-amber-500 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                    />
                  </div>

                  {/* Battery Strap X */}
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between text-[9px] font-black text-zinc-500 uppercase leading-none">
                      <span>LiPo Battery Strap X-Slide (Roll Center)</span>
                      <span className="text-amber-500 font-black">{batOffsetX > 0 ? "+" : ""}{batOffsetX} mm</span>
                    </div>
                    <input
                      type="range"
                      min="-10"
                      max="10"
                      value={batOffsetX}
                      onChange={(e) => {
                        playSwitchClick();
                        setBatOffsetX(parseInt(e.target.value));
                      }}
                      className="w-full accent-amber-500 h-1 bg-zinc-900 rounded-lg cursor-pointer"
                    />
                  </div>

                  {/* Payload Toggles */}
                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        playSwitchClick();
                        setGoproMounted(!goproMounted);
                      }}
                      className={`py-2 px-3 border rounded-xl text-[9px] uppercase font-black transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                        goproMounted
                          ? "bg-rose-950/25 border-rose-900/40 text-rose-400"
                          : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-400"
                      }`}
                    >
                      <span>GOPro Core (+120g)</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        playSwitchClick();
                        setDebrisOnFr(!debrisOnFr);
                      }}
                      className={`py-2 px-3 border rounded-xl text-[9px] uppercase font-black transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                        debrisOnFr
                          ? "bg-emerald-950/20 border-emerald-900/40 text-emerald-400"
                          : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-400"
                      }`}
                    >
                      <span>MUD DEBRIS (+12g)</span>
                    </button>
                  </div>
                </div>

              </div>
            ) : (
              /* SVG Schematic Blueprint Mode */
              <div className="w-full flex flex-col items-center">
                <div className="w-64 h-64 relative bg-[#050505]/60 border border-zinc-900 rounded-2xl flex items-center justify-center p-2">
                  {/* Outer circle coordinates */}
                  <div className="absolute inset-4 border border-zinc-900/60 rounded-full border-dashed" />
                  <div className="absolute h-full w-px bg-zinc-900/20" />
                  <div className="absolute w-full h-px bg-zinc-900/20" />

                  <svg width="200" height="200" viewBox="0 0 200 200" fill="none" className="opacity-70 text-zinc-700">
                    {/* Arm structural lines */}
                    <line x1="40" y1="40" x2="160" y2="160" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
                    <line x1="40" y1="160" x2="160" y2="40" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
                    {/* Central FC body block */}
                    <rect x="75" y="75" width="50" height="50" rx="3" stroke="currentColor" strokeWidth="4" />
                    {/* Motor circles */}
                    <circle cx="45" cy="45" r="16" stroke="currentColor" strokeWidth="3" />
                    <circle cx="155" cy="45" r="16" stroke="currentColor" strokeWidth="3" />
                    <circle cx="45" cy="155" r="16" stroke="currentColor" strokeWidth="3" />
                    <circle cx="155" cy="155" r="16" stroke="currentColor" strokeWidth="3" />
                    
                    {/* FPV Camera block front */}
                    <path d="M85 45 L115 45 L115 15 L85 15 Z" stroke="currentColor" strokeWidth="3" />
                    <circle cx="100" cy="25" r="4" fill="currentColor" />
                  </svg>

                  {/* Dynamic hotspot pins */}
                  {SCHEMATIC_PINS.map((pin) => (
                    <button
                      key={pin.id}
                      type="button"
                      onMouseEnter={() => {
                        playBeep(2900, 0.03);
                        setActiveSchematicPin(pin.id);
                      }}
                      onMouseLeave={() => setActiveSchematicPin(null)}
                      className="absolute w-4 h-4 rounded-full flex items-center justify-center cursor-pointer group"
                      style={{
                        left: `calc(${pin.x} - 8px)`,
                        top: `calc(${pin.y} - 8px)`
                      }}
                    >
                      <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 absolute group-hover:animate-ping opacity-75" />
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 absolute animate-pulse" />
                    </button>
                  ))}

                  {/* Popover on active hovered node */}
                  <AnimatePresence>
                    {activeSchematicPin && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute bg-[#050505] p-3 border border-orange-600 rounded shadow-2xl left-1/2 -translate-x-1/2 -top-4 w-48 text-left font-mono z-40 text-left"
                      >
                        <div className="text-[9px] font-black text-orange-500 uppercase leading-normal border-b border-zinc-900 pb-0.5 mb-1.5">
                          {SCHEMATIC_PINS.find(p => p.id === activeSchematicPin)?.title}
                        </div>
                        <div className="text-[8px] text-zinc-300 leading-normal">
                          {SCHEMATIC_PINS.find(p => p.id === activeSchematicPin)?.desc}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                <div className="text-[10px] font-mono text-zinc-500 mt-3 text-left self-start leading-relaxed">
                  CHASSIS: <span className="text-zinc-300 font-extrabold">{config.frame.name}</span> <br />
                  VTX UNIT: <span className="text-zinc-300 font-extrabold">{config.vtx.name}</span>
                </div>
              </div>
            )}

          </div>

        </div>

      </div>

    </div>
  );
}
