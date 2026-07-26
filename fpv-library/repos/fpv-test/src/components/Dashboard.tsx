/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import { motion } from "motion/react";
import { ActiveView } from "../types";
import { playBeep, playSwitchClick } from "../utils/audio";
import { Shield, Zap, RefreshCw, Cpu, Radio, ChevronRight, Play, Eye, Flame, Award, Orbit, Gauge } from "lucide-react";

// Import the generated images
import fpvDroneHero from "../assets/images/fpv_drone_hero_1780037160014.png";

interface DashboardProps {
  setActiveView: (view: ActiveView) => void;
  isArmed: boolean;
  flightMode: string;
}

export default function Dashboard({ setActiveView, isArmed, flightMode }: DashboardProps) {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [glitchText, setGlitchText] = useState("VORTEX METRIC");

  // Handle subtle interactive mouse tilt effect
  const handleMouseMove = (e: React.MouseEvent) => {
    const { clientX, clientY, currentTarget } = e;
    const { left, top, width, height } = currentTarget.getBoundingClientRect();
    const x = (clientX - left - width / 2) / (width / 2); // Normalized -1 to 1
    const y = (clientY - top - height / 2) / (height / 2);
    setMousePos({ x, y });
  };

  const handleMouseLeave = () => {
    setMousePos({ x: 0, y: 0 });
  };

  // Subtle cyclic OSD visual glitch
  useEffect(() => {
    const texts = ["VORTEX METRIC", "APEX CARBON", "6S SCREAMER", "ANTI-GRAV INIT", "BETAFLIGHT 4.4"];
    const interval = setInterval(() => {
      const randomText = texts[Math.floor(Math.random() * texts.length)];
      setGlitchText(randomText);
    }, 3800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex-1 w-full bg-[#050505] text-white overflow-y-auto px-6 py-8 md:py-16 relative flex flex-col justify-start">
      
      {/* Background ambient lighting glows */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-cyan-500/5 blur-[140px] pointer-events-none" />
      <div className="absolute bottom-1/3 right-1/4 w-[450px] h-[450px] rounded-full bg-orange-500/5 blur-[160px] pointer-events-none" />
      
      {/* Absolute overlay scanning grids */}
      <div className="absolute inset-0 bg-[#050505] bg-[linear-gradient(to_right,rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none z-0" />

      {/* Large Kinetic Overlays from Bold Typography Design */}
      <div className="absolute top-1/6 -left-12 rotate-[-12deg] opacity-15 select-none pointer-events-none z-0 hidden lg:block overflow-hidden w-full max-w-[50%]">
        <div className="text-[120px] font-black italic leading-none text-stroke-zinc antialiased tracking-tighter -skew-x-12">
          AERODYNAMIC
        </div>
      </div>
      
      <div className="absolute bottom-1/4 -right-16 rotate-[6deg] opacity-25 select-none pointer-events-none z-0 hidden lg:block overflow-hidden w-full max-w-[50%] text-right">
        <div className="text-[130px] font-black italic leading-none text-stroke-orange antialiased tracking-tighter -skew-x-12">
          UNBOUND
        </div>
      </div>

      {/* Main Container */}
      <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-10 items-center relative z-10 flex-1">
        
        {/* LEFT COMPONENT: Bold Kinetic Headings & Marketing Copy */}
        <div className="lg:col-span-5 flex flex-col gap-6 text-left relative z-10">
          
          {/* Tag & Status Indicators */}
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-0.5 rounded-xs border border-cyan-500/30 bg-cyan-950/20 text-cyan-400 font-mono text-[9px] tracking-widest uppercase animate-pulse font-bold">
              SYS established
            </span>
            <span className="text-zinc-500 font-mono text-[9px] tracking-widest flex items-center gap-1.5 font-bold">
              <span className={`w-1.5 h-1.5 rounded-full ${isArmed ? "bg-orange-500 animate-ping" : "bg-cyan-400"}`} />
              LINK STATE: {isArmed ? "ARMED" : "STABLE"}
            </span>
          </div>

          {/* Core brutalist kinetic heading with strong italic and skew pairings */}
          <div className="border-l-4 border-orange-600 pl-4 py-1">
            <div className="text-[10px] uppercase text-zinc-500 tracking-[0.3em] font-mono mb-2">Extreme Flight Profile</div>
            <h1 className="text-4xl sm:text-5xl xl:text-6xl font-sans font-black tracking-tighter leading-tight text-zinc-100 uppercase select-none italic -skew-x-12">
              BREAK THE <br />
              <span className="text-orange-600 filter drop-shadow-[0_0_20px_rgba(234,88,12,0.15)]">
                GRID OF GRAVITY
              </span>
            </h1>
          </div>

          <p className="text-zinc-400 font-normal text-sm leading-relaxed font-sans max-w-md">
            The ultimate expression of spatial racing engineering. We blend professional carbon monocoques, peak 6S thrust loops, and active digital HD telemetry to build unparalleled, aggressive FPV flight configurations.
          </p>

          {/* Spatial telemetry indicators bar stylized from OSD theme */}
          <div className="grid grid-cols-3 gap-6 border-y border-zinc-800/80 py-5 font-mono">
            <div className="flex flex-col border-l border-zinc-900 pl-3">
              <span className="text-zinc-500 text-[9px] tracking-wider uppercase font-bold">Dry Weight</span>
              <span className="text-zinc-200 text-3xl font-black italic -skew-x-12 mt-1">
                325<span className="text-cyan-400 text-sm not-italic ml-0.5">g</span>
              </span>
            </div>
            <div className="flex flex-col border-l border-zinc-900 pl-3">
              <span className="text-zinc-500 text-[9px] tracking-wider uppercase font-bold">Peak Thrust</span>
              <span className="text-zinc-200 text-3xl font-black italic -skew-x-12 mt-1">
                8.4<span className="text-orange-600 text-sm not-italic ml-0.5">kg</span>
              </span>
            </div>
            <div className="flex flex-col border-l border-zinc-900 pl-3">
              <span className="text-zinc-500 text-[9px] tracking-wider uppercase font-bold">Max Throttle</span>
              <span className="text-emerald-400 text-3xl font-black italic -skew-x-12 mt-1">
                215<span className="text-zinc-500 text-xs not-italic ml-0.5">kmh</span>
              </span>
            </div>
          </div>

          {/* Interactive Calls to action with glowing hover states resembling Transmitter triggers */}
          <div className="flex flex-col sm:flex-row gap-4 mt-2">
            <button
              id="cta-build"
              onClick={() => {
                playSwitchClick();
                setActiveView(ActiveView.CONFIGURATOR);
              }}
              className="px-8 py-4 bg-orange-600 text-zinc-100 font-black font-mono text-xs tracking-[0.2em] rounded-full uppercase hover-glow-orange hover:bg-orange-500 transition-all duration-150 cursor-pointer flex items-center justify-center gap-2"
            >
              <Zap size={14} className="fill-zinc-100" />
              ARM & CONFIGURE
            </button>
            <button
              id="cta-sim"
              onClick={() => {
                playSwitchClick();
                setActiveView(ActiveView.SIMULATOR);
              }}
              className="px-8 py-4 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-300 font-bold font-mono text-xs tracking-widest rounded-full uppercase transition-all duration-150 cursor-pointer flex items-center justify-center gap-2"
            >
              <Play size={14} className="fill-current text-cyan-400" />
              FLY VIRTUAL SIM
            </button>
          </div>

        </div>

        {/* RIGHT COMPONENT: 3D Holographic Parallax Drone View */}
        <div
          className="lg:col-span-7 flex flex-col items-center justify-center relative min-h-[400px] lg:min-h-[500px] cursor-grab select-none w-full"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Subtle spinning technical compass radar beneath the drone */}
          <div className="absolute w-80 h-80 rounded-full border border-dashed border-cyan-500/10 animate-[spin_40s_linear_infinite] flex items-center justify-center pointer-events-none">
            <div className="w-56 h-56 rounded-full border border-zinc-800 border-dotted flex items-center justify-center">
              <div className="w-32 h-32 rounded-full border border-orange-500/10 animate-[spin_10s_linear_infinite_reverse]" />
            </div>
          </div>

          {/* Floating HUD Telemetry Boxes (OSD overlays) */}
          <motion.div
            id="hud-osd-info-1"
            className="absolute top-4 left-4 bg-[#0c0d10]/90 border border-zinc-800 p-3 rounded-sm font-mono text-[9px] text-zinc-400 backdrop-blur-md flex flex-col gap-1 w-44 shadow-2xl pointer-events-none"
            animate={{
              y: [0, -6, 0],
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="flex justify-between border-b border-zinc-800 pb-1 mb-1 text-cyan-400 font-bold">
              <span>[ CELLS IN SEQUENCE ]</span>
              <span className="animate-pulse">Established</span>
            </div>
            <div className="flex justify-between">
              <span>CELL 1..3:</span>
              <span className="text-zinc-200">3.82V / 3.84V</span>
            </div>
            <div className="flex justify-between">
              <span>CELL 4..6:</span>
              <span className="text-zinc-200">3.83V / 3.82V</span>
            </div>
            <div className="flex justify-between text-orange-500 font-bold">
              <span>TOTAL (6S):</span>
              <span>22.95V</span>
            </div>
          </motion.div>

          {/* Top Right HUD Diagnostic */}
          <motion.div
            id="hud-osd-info-2"
            className="absolute top-8 right-4 bg-[#0c0d10]/90 border border-zinc-800 p-3 rounded-sm font-mono text-[9px] text-zinc-400 backdrop-blur-md flex flex-col gap-1 w-44 shadow-2xl pointer-events-none"
            animate={{
              y: [0, 8, 0],
            }}
            transition={{
              duration: 4.5,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 0.5,
            }}
          >
            <div className="flex justify-between border-b border-zinc-800 pb-1 mb-1 text-orange-500 font-bold">
              <span>[ IMU GYROSCOPE ]</span>
              <span className="animate-pulse">CAL</span>
            </div>
            <div className="flex justify-between">
              <span>ROLL RATE:</span>
              <span className="text-zinc-200">670 °/s</span>
            </div>
            <div className="flex justify-between">
              <span>PITCH RATE:</span>
              <span className="text-zinc-200">620 °/s</span>
            </div>
            <div className="flex justify-between text-cyan-400 font-bold">
              <span>OSD FREQ:</span>
              <span>4.31 kHz</span>
            </div>
          </motion.div>

          {/* Bottom Center Glitch HUD stats */}
          <motion.div
            id="hud-osd-info-3"
            className="absolute bottom-4 right-10 bg-[#0c0d10]/95 border border-zinc-800 px-3 py-1.5 rounded-sm font-mono text-[9px] text-cyan-400 backdrop-blur-md shadow-lg pointer-events-none flex items-center gap-3"
            animate={{
              scale: [1, 0.98, 1],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#00F5FF]" />
            <div className="flex flex-col">
              <span className="text-zinc-500 font-bold uppercase text-[7px] leading-tight">DIAGNOSTIC STATUS</span>
              <span className="text-white text-[10px] tracking-wider font-extrabold">{glitchText}</span>
            </div>
          </motion.div>

          {/* CORE IMMERSIVE DRONE: Smooth 3D-Look Parallax Rotation Wrapper */}
          <motion.div
            className="relative z-15 p-4 transition-all duration-300"
            style={{
              transform: `rotateX(${-mousePos.y * 18}deg) rotateY(${mousePos.x * 24}deg)`,
            }}
            animate={{
              y: [0, -12, 0], // Subtle continuous floating bounce
            }}
            transition={{
              duration: 5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            title="Grab or hover to rotate in spatial layout"
          >
            {/* Glowing neon halo backing the drone */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 rounded-full bg-cyan-400/10 blur-[60px] pointer-events-none" />

            <div className="absolute -top-10 left-1/2 -translate-x-1/2 text-center w-full">
              <span className="block text-[10px] font-bold uppercase tracking-[0.6em] text-zinc-500 mb-2">CARBON SERIES XLL</span>
              <div className="bg-zinc-900/40 backdrop-blur-md border border-zinc-800 px-5 py-2.5 rounded-full inline-flex items-center gap-3">
                <span className="text-orange-500 font-black tracking-widest text-[9px] italic">STAY AGGRESSIVE</span>
                <div className="w-px h-3 bg-zinc-800" />
                <span className="text-zinc-300 font-bold tracking-widest text-[9px]">6S MAX SPEED</span>
              </div>
            </div>

            <img
              src={fpvDroneHero}
              alt="APEX FPV Carbon Racing Quadcopter Drone"
              referrerPolicy="no-referrer"
              className="w-72 sm:w-85 xl:w-[410px] object-contain drop-shadow-[0_25px_45px_rgba(234,88,12,0.15)] select-none pointer-events-none filter brightness-110 saturate-110 mt-10"
            />
            
            {/* Holographic scanning vector target overlay directly on drone */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none w-52 h-52 border border-cyan-400/20 rounded-full flex items-center justify-center animate-pulse">
              <div className="w-44 h-44 border border-zinc-800 rounded-full border-dashed" />
              <div className="w-2.5 h-2.5 rounded-full bg-orange-600 absolute animate-ping" />
            </div>
          </motion.div>

        </div>

      </div>

      {/* UI Decal Lines from Design HTML */}
      <div className="absolute bottom-32 left-8 hidden xl:block z-20 pointer-events-none">
        <div className="text-[10px] font-mono leading-tight text-zinc-500 text-left">
          <span className="text-cyan-400 font-bold">[01]</span> INITIATE STARTUP SEQUENCE...<br/>
          <span className="text-cyan-400 font-bold">[02]</span> GYRO CALIBRATION: OK<br/>
          <span className="text-cyan-400 font-bold">[03]</span> ESC SYNC: STATUS OK<br/>
          <span className="text-orange-500 font-bold">[04]</span> MOTORS: READY TO ARM
        </div>
      </div>

      <div className="absolute top-44 right-8 w-24 h-[1px] bg-gradient-to-r from-orange-600 to-transparent hidden xl:block z-10 pointer-events-none"></div>

      {/* FOOTER FEATURE BENEFITS (Dribbble trending bento highlights) */}
      <div className="max-w-7xl mx-auto w-full mt-10 md:mt-16 border-t border-zinc-800/50 pt-8 relative z-20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-mono text-left">
          
          <div className="bg-zinc-950/40 p-5 rounded-lg border border-zinc-800/40 hover:border-cyan-500/25 transition-all flex gap-3">
            <Award className="text-cyan-400 shrink-0 mt-0.5" size={16} />
            <div className="flex flex-col gap-1">
              <span className="text-zinc-300 text-xs font-bold uppercase tracking-wider">Awwwards Concept Elite</span>
              <p className="text-zinc-500 text-[11px] leading-relaxed">Integrated next-generation cybernetic design layouts with dynamic, responsive multi-axis micro-interactions.</p>
            </div>
          </div>

          <div className="bg-zinc-950/40 p-5 rounded-lg border border-zinc-800/40 hover:border-orange-500/25 transition-all flex gap-3">
            <Orbit className="text-orange-500 shrink-0 mt-0.5" size={16} />
            <div className="flex flex-col gap-1">
              <span className="text-zinc-300 text-xs font-bold uppercase tracking-wider">Spatial 3D Kinetics</span>
              <p className="text-zinc-500 text-[11px] leading-relaxed">Experience tactile control loops. Drag gimbals directly in the bottom navigation bar to manipulate the drone HUD.</p>
            </div>
          </div>

          <div className="bg-zinc-950/40 p-5 rounded-lg border border-zinc-800/40 hover:border-emerald-500/25 transition-all flex gap-3">
            <Gauge className="text-emerald-400 shrink-0 mt-0.5" size={16} />
            <div className="flex flex-col gap-1">
              <span className="text-zinc-300 text-xs font-bold uppercase tracking-wider">Zero Latency OSD Sim</span>
              <p className="text-zinc-500 text-[11px] leading-relaxed font-normal">Switch feed to pure analog mode to experience vintage visual feedback, CRT scanlines, and instant feed response.</p>
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
