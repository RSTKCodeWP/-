/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from "react";
import { DroneConfig, FlightMode } from "../types";
import { startMotorSound, updateMotorSound, stopMotorSound, playBeep, playEscTones, playSwitchClick } from "../utils/audio";
import { motion, AnimatePresence } from "motion/react";
import { Radio, RefreshCw, Volume2, VolumeX, ShieldAlert, Award, Play, Eye, Lock, Unlock, Sliders, Flame, Check } from "lucide-react";

import fpvCanyonRun from "../assets/images/fpv_canyon_run_1780037179644.png";

interface FpvSimulatorProps {
  config: DroneConfig;
  isArmed: boolean;
  setIsArmed: (armed: boolean) => void;
  flightMode: FlightMode;
  setFlightMode: (mode: FlightMode) => void;
  analogFeed: boolean;
  setAnalogFeed: (analog: boolean) => void;
  beeperActive: boolean;
  setBeeperActive: (active: boolean) => void;
  throttle: number;
  setThrottle: (val: number) => void;
  yaw: number;
  setYaw: (val: number) => void;
  pitch: number;
  setPitch: (val: number) => void;
  roll: number;
  setRoll: (val: number) => void;
}

export default function FpvSimulator({
  config,
  isArmed,
  setIsArmed,
  flightMode,
  setFlightMode,
  analogFeed,
  setAnalogFeed,
  beeperActive,
  setBeeperActive,
  throttle,
  setThrottle,
  yaw,
  setYaw,
  pitch,
  setPitch,
  roll,
  setRoll,
}: FpvSimulatorProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [checklistOpen, setChecklistOpen] = useState(false);
  const [failsafeTest, setFailsafeTest] = useState(false);
  const [laps, setLaps] = useState(0);
  const [gateSize, setGateSize] = useState(10); // 10% to 100% zoom scale of incoming racing gate
  const [gateOffsetX, setGateOffsetX] = useState(0); // Offset in pixels from center
  const [gateOffsetY, setGateOffsetY] = useState(0);
  const [soundEnabled, setSoundEnabled] = useState(true);
  
  // Simulated Betaflight variables
  const [voltage, setVoltage] = useState(22.95); // 6S full battery
  const [milliAmps, setMilliAmps] = useState(0);
  const [rssi, setRssi] = useState(99);
  const [flightTimeSecs, setFlightTimeSecs] = useState(0);
  const [gateMessage, setGateMessage] = useState<string | null>(null);

  // References for keeping track of flight positions
  const animationFrameId = useRef<number | null>(null);
  const flightStateRef = useRef({
    roll: 0,
    pitch: 0,
    yaw: 0,
    throttle: 0,
    px: 0, // dynamic offsets for canyon run background shifting
    py: 0,
  });

  // Track state changes into ref for loop closure
  useEffect(() => {
    flightStateRef.current.roll = roll;
    flightStateRef.current.pitch = pitch;
    flightStateRef.current.yaw = yaw;
    flightStateRef.current.throttle = throttle;
  }, [roll, pitch, yaw, throttle]);

  // Handle Arming transition
  useEffect(() => {
    if (isArmed && isRunning) {
      if (soundEnabled) {
        startMotorSound();
        updateMotorSound(throttle / 100);
      }
    } else {
      stopMotorSound();
    }
    return () => stopMotorSound();
  }, [isArmed, isRunning]);

  // Handle throttle sound pitch adjustments
  useEffect(() => {
    if (isArmed && isRunning && soundEnabled) {
      updateMotorSound(throttle / 100);
    }
  }, [throttle, isArmed, isRunning, soundEnabled]);

  const handleStartSim = () => {
    playSwitchClick();
    setChecklistOpen(true);
  };

  const handleCloseChecklist = () => {
    playSwitchClick();
    setChecklistOpen(false);
  };

  const handleIgnition = () => {
    if (throttle !== 0 || isArmed || beeperActive || flightMode !== "ACRO") {
      playBeep(1200, 0.3);
      return;
    }
    setIsRunning(true);
    setIsArmed(true);
    playEscTones();
    setChecklistOpen(false);
  };

  const handleStopSim = () => {
    playBeep(1600, 0.15);
    setIsRunning(false);
    stopMotorSound();
  };

  // Main Loop logic (60Hz animation ticker)
  useEffect(() => {
    if (!isRunning) return;

    // Reset parameters on restart
    setLaps(0);
    setGateSize(10);
    setGateOffsetX(0);
    setGateOffsetY(0);
    setVoltage(22.95);
    setFlightTimeSecs(0);

    let lastTime = performance.now();
    let gateTimer = 0;
    let secCounter = 0;

    const gameLoop = (currentTime: number) => {
      const dt = (currentTime - lastTime) / 1000;
      lastTime = currentTime;

      const state = flightStateRef.current;
      
      // Calculate background offsets based on user steering
      // Pitch down -> shifts background UP (fly forwards/down). Yaw -> shifts background left/right
      state.px -= (state.yaw * 2.5) * dt;
      state.py += (state.pitch * 2.3) * dt;

      // Keep coordinates constrained so speed feels infinite
      if (Math.abs(state.px) > 280) state.px = 0;
      if (Math.abs(state.py) > 240) state.py = 0;

      // Simulate keyboard continuous auto-leveling of horizon under ANGLE mode
      if (flightMode === "ANGLE") {
        if (roll === 0) setRoll(0);
        if (pitch === 0) setPitch(0);
      }

      // Update Gate Zoom Scale
      // Speed multiplier is proportional to Throttle
      const velocityRatio = (state.throttle / 100) + 0.35; // base speed scroll
      gateTimer += dt * 32 * velocityRatio;

      setGateSize((prev) => {
        let size = prev + dt * 14 * velocityRatio;
        
        // Gate passes pilot: check if they flew inside boundaries
        if (size >= 100) {
          // Check collision calibration window
          // If gate is fairly centered (+- 35px offset) when it gets to 100% scale, it is a lap pass!
          const distanceCenter = Math.sqrt(gateOffsetX * gateOffsetX + gateOffsetY * gateOffsetY);
          
          if (distanceCenter < 38) {
            setLaps((l) => l + 1);
            setGateMessage("GATE LAUNCHED // LAP CLEARED!");
            playBeep(3100, 0.06);
            setTimeout(() => playBeep(4100, 0.1), 60);
            setTimeout(() => setGateMessage(null), 1500);
          } else {
            setGateMessage("CRASHED GATE // RE-ARM ESC");
            playBeep(1500, 0.25);
            setTimeout(() => setGateMessage(null), 1500);
          }

          // Spawn new gate random coords
          setGateOffsetX((Math.random() - 0.5) * 160);
          setGateOffsetY((Math.random() - 0.5) * 110);
          return 10; // reset scale
        }
        return size;
      });

      // Keep gate floating centered with slight parallax
      // Steering pitch and yaw moves the gates oppositely!
      setGateOffsetX((original) => {
        // Adjust gate with yaw input
        return original - (state.yaw * dt * 1.5);
      });
      setGateOffsetY((original) => {
        return original + (state.pitch * dt * 1.3);
      });

      // Battery voltage discharge rate relative to Throttle usage
      setVoltage((v) => {
        const usageSag = (state.throttle / 100) * 0.08;
        const baseLeach = dt * 0.04;
        const nextVolts = v - (usageSag * dt + baseLeach);
        return Math.max(19.2, Math.round(nextVolts * 100) / 100); // minimum battery failsafe (3.2V per cell)
      });

      // Milliamps consumed
      setMilliAmps((ma) => {
        const ampFlow = 5 + (state.throttle / 100) * 85;
        return Math.round(ma + ampFlow * dt);
      });

      // Time counter
      secCounter += dt;
      if (secCounter >= 1) {
        setFlightTimeSecs((t) => t + 1);
        secCounter = 0;
      }

      // RSSI fluctuate
      setRssi((r) => {
        const wiggle = (Math.random() - 0.5) * 3;
        return Math.max(60, Math.min(99, Math.round(r + wiggle)));
      });

      animationFrameId.current = requestAnimationFrame(gameLoop);
    };

    animationFrameId.current = requestAnimationFrame(gameLoop);
    return () => {
      if (animationFrameId.current) cancelAnimationFrame(animationFrameId.current);
    };
  }, [isRunning, flightMode]);

  // Simple clean keyboard handlers to pilot from keyboard if they aren't dragging the gimbals
  useEffect(() => {
    if (!isRunning) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      
      // Control with WASD or arrow keys
      if (key === "w" || e.key === "ArrowUp") {
        setPitch(25);
        setThrottle(Math.min(100, throttle + 8));
      }
      if (key === "s" || e.key === "ArrowDown") {
        setPitch(-25);
        setThrottle(Math.max(0, throttle - 8));
      }
      if (key === "a" || e.key === "ArrowLeft") {
        setRoll(-25);
        setYaw(-25);
      }
      if (key === "d" || e.key === "ArrowRight") {
        setRoll(25);
        setYaw(25);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      // Snap pitch and roll/yaw back on release
      if (key === "w" || key === "s" || e.key === "ArrowUp" || e.key === "ArrowDown") {
        setPitch(0);
      }
      if (key === "a" || key === "d" || e.key === "ArrowLeft" || e.key === "ArrowRight") {
        setRoll(0);
        setYaw(0);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [isRunning, throttle]);

  // Convert voltage back to cell count (6S)
  const averageCellVoltage = Math.round((voltage / 6) * 100) / 100;
  
  // Format seconds to standard mm:ss
  const formatTime = (secs: number) => {
    const min = Math.floor(secs / 60);
    const ss = secs % 60;
    return `${min}:${ss < 10 ? "0" : ""}${ss}`;
  };

  // Betaflight artificial horizon angles calculation
  const horizonRollDeg = roll * 0.75;
  const horizonPitchOffset = pitch * 0.45;

  return (
    <div className="flex-1 w-full bg-[#050505] text-white p-6 md:p-12 overflow-y-auto flex flex-col justify-start relative select-none">
      
      {/* Container header */}
      <div className="max-w-7xl mx-auto w-full mb-8 border-l-2 border-orange-600 pl-4 py-1 text-left">
        <span className="text-zinc-500 font-mono text-[9px] tracking-[0.3em] uppercase block mb-1">REAL-TIME AERODYNAMIC VIRTUAL SIMULATOR</span>
        <h2 className="text-3xl md:text-4xl font-black uppercase italic -skew-x-12 tracking-tighter text-zinc-100 flex flex-col md:flex-row md:items-baseline justify-between gap-2">
          <span>COCKPIT HUD PILOT</span>
          <span className="text-[10px] font-mono text-zinc-550 tracking-normal normal-case not-italic block mt-1 md:mt-0 font-normal">
            Keyboard WASD / ARROWS supported for piloting. Configure link, arm motors, and switches below!
          </span>
        </h2>
      </div>

      <div className="max-w-4xl mx-auto w-full flex flex-col items-center">
        
        {/* Main virtual FPV screen box */}
        <div className="relative w-full aspect-16/10 max-h-[500px] border-4 border-zinc-900 rounded-3xl overflow-hidden bg-black shadow-[0_0_50px_rgba(0,0,0,0.8)] flex items-center justify-center">
          
          {/* FPV Canyon Flight Backdrop (Parallax Shifted based on steer coords) */}
          <div
            className="absolute inset-0 transition-transform duration-200 ease-out"
            style={{
              backgroundImage: `url(${fpvCanyonRun})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              transform: isRunning
                ? `scale(1.2) translate(${flightStateRef.current.px * 0.4}px, ${flightStateRef.current.py * 0.4}px) rotate(${-roll * 0.3}deg)`
                : "scale(1.0)",
            }}
          />

          {/* Analog scanlines fuzz overlay */}
          {analogFeed && (
            <div className="absolute inset-0 pointer-events-none z-10 opacity-30 bg-linear-to-b from-transparent via-zinc-950/20 to-transparent bg-[size:100%_4px] before:content-[''] before:absolute before:inset-0 before:bg-[radial-gradient(circle,rgba(255,255,255,0.06)_1px,transparent_1px)] before:bg-[size:3px_3px] before:animate-pulse">
              {/* Overlay random white static signal bars */}
              <div className="absolute top-1/3 left-0 right-0 h-1.5 bg-white/10 animate-[bounce_0.2s_infinite]" />
              <div className="absolute top-2/3 left-0 right-0 h-0.5 bg-cyan-400/5 animate-[bounce_0.3s_infinite]" />
            </div>
          )}

          {/* SIMULATOR NOT STARTED COVER */}
          {!isRunning && (
            <div className="absolute inset-0 bg-zinc-950/90 backdrop-blur-md z-20 flex flex-col items-center justify-center p-6 text-center">
              <div className="w-16 h-16 rounded-full border-2 border-orange-500/30 flex items-center justify-center shadow-[0_0_30px_rgba(234,88,12,0.15)] mb-6 animate-pulse">
                <Radio className="text-orange-500" size={24} />
              </div>
              <h3 className="text-xl font-bold uppercase tracking-widest text-zinc-100 font-mono mb-2">FPV Drone Unarmed</h3>
              <p className="text-xs text-zinc-500 max-w-sm mb-8 font-normal leading-relaxed">
                Ready to flash signal firmware onto your custom <span className="text-cyan-400 font-bold uppercase">{config.frame.name}</span>. Start motor rotation and takeoff.
              </p>
              <button
                onClick={handleStartSim}
                className="px-8 py-4 bg-orange-600 hover:bg-orange-500 text-zinc-100 font-extrabold font-mono text-xs rounded-full uppercase tracking-widest cursor-pointer hover-glow-orange transition-all duration-150"
              >
                Engage ESC Core & Takeoff
              </button>
            </div>
          )}

          {/* PRE-FLIGHT CHECKLIST MODAL */}
          {checklistOpen && (
            <div className="absolute inset-0 bg-zinc-950/95 backdrop-blur-lg z-30 flex flex-col justify-between p-6 md:p-8 text-left border-2 border-orange-600/30 rounded-3xl overflow-y-auto">
              
              {/* Header */}
              <div className="flex justify-between items-start border-b border-zinc-900 pb-3 h-14 shrink-0">
                <div>
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="text-orange-600 animate-pulse" size={18} />
                    <span className="text-zinc-500 font-mono text-[9px] tracking-[0.3em] uppercase block">BETAFLIGHT SECURE CORE // INITIALIZATION</span>
                  </div>
                  <h3 className="text-xl font-black italic -skew-x-12 uppercase tracking-tighter text-zinc-100 mt-1">
                    PRE-FLIGHT HARDWARE CHECKS
                  </h3>
                </div>
                <button
                  onClick={handleCloseChecklist}
                  className="p-1 px-3.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-[10px] text-zinc-400 hover:text-white uppercase font-mono tracking-wider transition-all cursor-pointer hover:bg-zinc-800"
                >
                  [ CANCEL ]
                </button>
              </div>

              {/* Checklist Items list */}
              <div className="flex-1 my-4 flex flex-col gap-3 justify-center overflow-y-auto">
                {/* 1. Throttle check */}
                <div id="check-throttle" className={`p-3 rounded-xl border flex items-center justify-between transition-all duration-200 ${
                  throttle === 0 ? "bg-emerald-905/20 border-emerald-900/40" : "bg-red-955/10 border-red-900/30 animate-pulse"
                }`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      throttle === 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-500"
                    }`}>
                      {throttle === 0 ? (
                        <Check className="font-black" size={16} />
                      ) : (
                        <Sliders size={16} />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-bold font-mono text-zinc-200 uppercase">1. Safety Throttle Position</span>
                      <span className="text-[10px] text-zinc-550 font-sans leading-relaxed">
                        Drag Left Stick completely DOWN to 0%. Prevent high RPM spin on armed state.
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-[10px] font-mono font-bold tracking-wider px-2 py-1 rounded uppercase ${
                      throttle === 0 ? "bg-emerald-900/30 text-emerald-400" : "bg-red-900/30 text-red-500 animate-pulse"
                    }`}>
                      {throttle === 0 ? `PASSED (0%)` : `ALERT (${throttle}%)`}
                    </span>
                  </div>
                </div>

                {/* 2. Arm state check */}
                <div id="check-arm" className={`p-3 rounded-xl border flex items-center justify-between transition-all duration-200 ${
                  !isArmed ? "bg-emerald-955/20 border-emerald-900/40" : "bg-red-955/10 border-red-900/30 animate-pulse"
                }`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      !isArmed ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-500"
                    }`}>
                      {!isArmed ? (
                        <Check className="font-black" size={16} />
                      ) : (
                        <Radio size={16} />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-bold font-mono text-zinc-200 uppercase">2. Motor Security Force SF Switch</span>
                      <span className="text-[10px] text-zinc-550 font-sans leading-relaxed">
                        Toggle SF Switch down to DIS. System safety rules reject initial active boot flags.
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-[10px] font-mono font-bold tracking-wider px-2 py-1 rounded uppercase ${
                      !isArmed ? "bg-emerald-900/30 text-emerald-400" : "bg-red-900/30 text-red-500 animate-pulse"
                    }`}>
                      {!isArmed ? "DISARMED (SAFE)" : "ARMED (LOCKED)"}
                    </span>
                  </div>
                </div>

                {/* 3. Beeper check */}
                <div id="check-beeper" className={`p-3 rounded-xl border flex items-center justify-between transition-all duration-200 ${
                  !beeperActive ? "bg-emerald-955/20 border-emerald-900/40" : "bg-red-955/10 border-red-900/30 animate-pulse"
                }`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      !beeperActive ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-500"
                    }`}>
                      {!beeperActive ? (
                        <Check className="font-black" size={16} />
                      ) : (
                        <VolumeX size={16} />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-bold font-mono text-zinc-200 uppercase">3. Receiver Buzzer SD Switch</span>
                      <span className="text-[10px] text-zinc-550 font-sans leading-relaxed">
                        Toggle SD Switch down to MUTE. Protecting diagnostic sound cards during boot cycles.
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-[10px] font-mono font-bold tracking-wider px-2 py-1 rounded uppercase ${
                      !beeperActive ? "bg-emerald-900/30 text-emerald-400" : "bg-red-900/30 text-red-500 animate-pulse"
                    }`}>
                      {!beeperActive ? "MUTE (SAFE)" : "BUZZING"}
                    </span>
                  </div>
                </div>

                {/* 4. Flight Mode check */}
                <div id="check-flightmode" className={`p-3 rounded-xl border flex items-center justify-between transition-all duration-200 ${
                  flightMode === "ACRO" ? "bg-emerald-955/20 border-emerald-900/40" : "bg-red-955/10 border-red-900/30 animate-pulse"
                }`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      flightMode === "ACRO" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-500"
                    }`}>
                      {flightMode === "ACRO" ? (
                        <Check className="font-black" size={16} />
                      ) : (
                        <RefreshCw size={16} />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-bold font-mono text-zinc-200 uppercase">4. Flight Control Envelope SB Switch</span>
                      <span className="text-[10px] text-zinc-550 font-sans leading-relaxed">
                        Cycle SB Switch to ACRO (strictest dynamic tuning mode). Required for full canyon acrobatics.
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-[10px] font-mono font-bold tracking-wider px-2 py-1 rounded uppercase ${
                      flightMode === "ACRO" ? "bg-emerald-900/30 text-emerald-400" : "bg-red-900/30 text-red-500 animate-pulse"
                    }`}>
                      {flightMode === "ACRO" ? "ACRO FREESTYLE" : `${flightMode} (FAIL)`}
                    </span>
                  </div>
                </div>
              </div>

              {/* Bottom Interactive Trigger Actions */}
              <div className="border-t border-zinc-900 pt-3.5 flex flex-col sm:flex-row items-center justify-between gap-4 h-20 shrink-0">
                <div className="flex flex-col text-left">
                  <span className="text-[8px] sm:text-[9px] uppercase tracking-[0.2em] font-black italic text-zinc-500">PRE-FLIGHT STATUS ENGINE</span>
                  {throttle === 0 && !isArmed && !beeperActive && flightMode === "ACRO" ? (
                    <span className="text-xs font-black text-emerald-400 flex items-center gap-1.5 uppercase tracking-wide">
                      <Unlock size={11} className="animate-bounce" /> ALL CLEAR. READY FOR LIFT-OFF.
                    </span>
                  ) : (
                    <span className="text-xs font-black text-orange-600 flex items-center gap-1.5 uppercase tracking-wide animate-pulse">
                      <Lock size={11} /> CALIBRATING PROPELLER PIDS...
                    </span>
                  )}
                </div>

                <button
                  id="checklist-ignite-btn"
                  disabled={!(throttle === 0 && !isArmed && !beeperActive && flightMode === "ACRO")}
                  onClick={handleIgnition}
                  className={`w-full sm:w-auto px-8 py-3.5 rounded-full uppercase tracking-widest text-[11px] font-black font-mono transition-all duration-250 flex items-center justify-center gap-2 ${
                    (throttle === 0 && !isArmed && !beeperActive && flightMode === "ACRO")
                      ? "bg-orange-600 text-zinc-100 hover:bg-orange-500 cursor-pointer shadow-[0_0_25px_rgba(234,88,12,0.35)] hover:scale-[1.01] hover-glow-orange text-white"
                      : "bg-[#0b0c0f] border border-zinc-900 text-zinc-500 cursor-not-allowed opacity-[0.55]"
                  }`}
                >
                  <Flame size={12} className={throttle === 0 && !isArmed && !beeperActive && flightMode === "ACRO" ? "animate-pulse" : ""} />
                  IGNITE CORE PROP MOTORS & TAKE OFF
                </button>
              </div>

            </div>
          )}

          {/* ACTIVE OSD FLIGHT SIMULATION LAYOUT */}
          {isRunning && (
            <div className="absolute inset-0 z-15 p-6 flex flex-col justify-between font-mono text-xs text-white uppercase select-none pointer-events-none drop-shadow-[0_1.5px_4px_rgba(0,0,0,1)]">
              
              {/* OSD TOP LINE BAR */}
              <div className="flex items-start justify-between">
                
                {/* Voltage block */}
                <div className="flex flex-col text-left text-neutral-200">
                  <div className="font-black flex items-center gap-1.5 text-orange-500">
                    <span>{voltage.toFixed(2)}V</span>
                    <span className="text-[10px] text-zinc-400 italic">({averageCellVoltage}V)</span>
                  </div>
                  <span className="text-[9px] text-zinc-500 font-black">6S LIPO LKD</span>
                </div>

                {/* Central notifications flashing message pop */}
                <div className="flex flex-col items-center">
                  <div className="bg-zinc-950/50 px-3.5 py-1.5 border border-zinc-900 text-[10px] text-emerald-400 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-650 animate-ping" />
                    BETAFLIGHT READY
                  </div>
                  
                  {/* LAP PASS NOTIFICATION */}
                  <AnimatePresence>
                    {gateMessage && (
                      <motion.div
                        initial={{ scale: 0.6, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.6, opacity: 0 }}
                        className={`text-sm md:text-base font-black tracking-widest text-center mt-6 px-4 py-2 bg-black border ${
                          gateMessage.includes("CRASH") ? "border-rose-500 text-rose-500" : "border-cyan-500 text-cyan-400 animate-pulse"
                        }`}
                      >
                        {gateMessage}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Signal RSSI block */}
                <div className="flex flex-col text-right text-cyan-400">
                  <div className="font-bold flex items-center gap-1 justify-end">
                    <span>RSSI: {rssi}%</span>
                  </div>
                  <span className="text-[8px] text-zinc-500 font-bold uppercase">{config.vtx.specs["Resolution"]} Latency: {analogFeed ? 0 : config.vtx.specs["Latency"]}</span>
                </div>

              </div>

              {/* FLOATING DIRECT NEON FP RACING GATES (Betaflight simulated 3D Gate) */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
                <div
                  className="rounded-lg border-4 border-dashed border-orange-500/80 flex items-center justify-center transition-all duration-75 relative"
                  style={{
                    width: `${gateSize}%`,
                    height: `${gateSize}%`,
                    maxWidth: "380px",
                    maxHeight: "260px",
                    transform: `translate(${gateOffsetX}px, ${gateOffsetY}px)`,
                    boxShadow: `0 0 ${gateSize / 2}px rgba(249,115,22,0.3), inset 0 0 ${gateSize / 2}px rgba(249,115,22,0.3)`,
                    borderColor: gateSize > 85 ? "rgb(6,182,212)" : "rgb(249,115,22)", // flashes cyan when close
                  }}
                >
                  {/* Gate identifier marker */}
                  <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] text-orange-400 font-extrabold tracking-widest uppercase bg-zinc-950/80 px-1 border border-orange-500/30">
                    GATE {laps + 1}
                  </span>
                  
                  {/* Target sight box directly on center of the Gate */}
                  <div className="w-5 h-5 border border-dashed border-orange-400/50 rounded-full" />
                </div>
              </div>

              {/* CENTRAL TELEMETRY: Artificial Horizon lines (Roll and pitch) */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                {/* Dynamically rolls and pitches */}
                <div
                  className="w-48 h-px bg-cyan-400/80 relative flex items-center justify-between"
                  style={{
                    transform: `rotate(${horizonRollDeg}deg) translateY(${horizonPitchOffset}px)`
                  }}
                >
                  <div className="w-12 h-1 bg-cyan-400" />
                  {/* Central target pip box */}
                  <div className="w-3.5 h-3.5 border-2 border-orange-500 bg-transparent rounded-full flex items-center justify-center">
                    <div className="w-1 h-1 rounded-full bg-orange-500" />
                  </div>
                  <div className="w-12 h-1 bg-cyan-400" />

                  {/* Pitch ticks above and below horizon line */}
                  <div className="absolute left-1/2 -translate-x-1/2 top-4 w-6 h-px bg-cyan-400/50 flex justify-between">
                    <span className="text-[7px] text-cyan-400 -mt-2.5">10</span>
                    <span className="text-[7px] text-cyan-400 -mt-2.5">10</span>
                  </div>
                  <div className="absolute left-1/2 -translate-x-1/2 -top-4 w-6 h-px bg-cyan-400/50 flex justify-between">
                    <span className="text-[7px] text-cyan-400 -mt-2.5">-10</span>
                    <span className="text-[7px] text-cyan-400 -mt-2.5">-10</span>
                  </div>
                </div>
              </div>

              {/* OSD BOTTOM LINE BAR */}
              <div className="flex items-end justify-between">
                
                {/* Mode details and lap count stats */}
                <div className="flex flex-col text-left">
                  <span className="text-zinc-500 text-[8px] tracking-[0.2em] font-black uppercase mb-0.5">ESTIMATED LAPS CLIMBED:</span>
                  <div className="text-2xl font-black text-orange-500 italic -skew-x-12">
                    LAPS: {laps}
                  </div>
                </div>

                {/* Flying diagnostics stats screen */}
                <div className="text-center">
                  <span className="text-xs text-orange-600 font-extrabold tracking-widest block animate-pulse">{flightMode} FLT MODE</span>
                  <span className="text-[8px] text-zinc-550 font-black uppercase">{config.frame.specs["Material"]}</span>
                </div>

                {/* Core battery drainage values */}
                <div className="flex flex-col text-right">
                  <div className="text-zinc-200 font-bold">{milliAmps} mAh</div>
                  <span className="text-cyan-400 text-base font-black tracking-widest">TIM: {formatTime(flightTimeSecs)}</span>
                </div>

              </div>

            </div>
          )}

        </div>

        {/* Outer Dashboard Controller Panel */}
        <div id="sim-control-board" className="mt-6 w-full bg-[#0b0c0f]/90 p-5 border border-zinc-900 rounded-3xl flex flex-col md:flex-row items-stretch justify-between gap-6 text-left font-mono">
          
          {/* Sound, Failsafe, Reset Actions */}
          <div className="flex flex-col gap-4 justify-between flex-1">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSoundEnabled(!soundEnabled)}
                className="p-3 bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 rounded-xl text-zinc-400 hover:text-white cursor-pointer transition-all flex items-center justify-center shadow-lg"
                title={soundEnabled ? "Mute engine buzz" : "Unmute engine buzz"}
              >
                {soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
              </button>
              <div className="flex flex-col">
                <span className="text-[9px] font-mono text-zinc-500 uppercase leading-none font-bold">ESC RPM SOUND SYSTEM</span>
                <span className="text-[11px] font-mono text-zinc-350 mt-1 uppercase">Synthesized Brushless 6S Audio</span>
              </div>
            </div>

            <div className="flex flex-wrap gap-2.5">
              {isRunning && (
                <button
                  onClick={handleStopSim}
                  className="px-4 py-2 bg-rose-950/40 hover:bg-rose-900/90 text-rose-450 hover:text-white border border-rose-900/60 font-mono text-[10px] uppercase font-black tracking-wide rounded-lg cursor-pointer transition-all"
                >
                  DISARM MOTOR FORCE
                </button>
              )}
              <button
                onClick={() => {
                  playSwitchClick();
                  setLaps(0);
                  setFailsafeTest(true);
                  setTimeout(() => setFailsafeTest(false), 2000);
                }}
                className="px-4 py-2 bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-zinc-300 font-mono text-[10px] uppercase font-black tracking-wide rounded-lg cursor-pointer transition-all hover:border-zinc-700"
              >
                SIMULATE GPS FAILSAFE
              </button>
            </div>
          </div>

          {/* Transmitter Hardware Toggle Swicthes Line */}
          <div className="flex flex-wrap items-center gap-3 md:border-l md:border-zinc-900 md:pl-6 justify-start md:justify-end shrink-0">
            {/* ARM MOTORS */}
            <div className="flex flex-col gap-1 text-left">
              <span className="text-[8px] text-zinc-500 uppercase tracking-widest font-black font-mono">SF Sw (Arm)</span>
              <button
                onClick={() => {
                  playSwitchClick();
                  if (!isArmed) {
                    setIsArmed(true);
                    playEscTones();
                  } else {
                    setIsArmed(false);
                    playBeep(2200, 0.15);
                    setThrottle(0);
                    setYaw(0);
                    setPitch(0);
                    setRoll(0);
                  }
                }}
                className={`py-2.5 px-3.5 rounded-xl border text-[10px] font-black uppercase tracking-wider transition-all cursor-pointer flex items-center gap-1.5 ${
                  isArmed
                    ? "bg-orange-950/30 border-orange-600/60 text-orange-400 shadow-[0_0_12px_rgba(234,88,12,0.15)]"
                    : "bg-zinc-900 hover:bg-zinc-850 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <ShieldAlert size={12} className={isArmed ? "text-orange-500 animate-pulse" : "text-zinc-650"} />
                <span>{isArmed ? "ARMED" : "ARM MOTORS"}</span>
              </button>
            </div>

            {/* FLIGHT MODE */}
            <div className="flex flex-col gap-1 text-left">
              <span className="text-[8px] text-zinc-500 uppercase tracking-widest font-black font-mono">SB Sw (Mode)</span>
              <button
                onClick={() => {
                  playSwitchClick();
                  if (flightMode === "ACRO") {
                    setFlightMode("ANGLE");
                    playBeep(3200, 0.05);
                  } else if (flightMode === "ANGLE") {
                    setFlightMode("HORIZON");
                    playBeep(3200, 0.05);
                    setTimeout(() => playBeep(3200, 0.05), 80);
                  } else {
                    setFlightMode("ACRO");
                    playBeep(2400, 0.06);
                  }
                }}
                className="py-2.5 px-3.5 bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 hover:border-zinc-700 text-zinc-200 rounded-xl text-[10px] font-black uppercase tracking-wider cursor-pointer"
              >
                {flightMode}
              </button>
            </div>

            {/* BEEPER */}
            <div className="flex flex-col gap-1 text-left">
              <span className="text-[8px] text-zinc-500 uppercase tracking-widest font-black font-mono">SD Sw (Buzz)</span>
              <button
                onClick={() => {
                  playSwitchClick();
                  setBeeperActive(!beeperActive);
                }}
                className={`py-2.5 px-3.5 border rounded-xl text-[10px] font-black uppercase tracking-wider transition-all cursor-pointer ${
                  beeperActive
                    ? "bg-yellow-950/25 border-yellow-700/60 text-yellow-400"
                    : "bg-zinc-900 hover:bg-zinc-850 border-zinc-800 text-zinc-400"
                }`}
              >
                {beeperActive ? "BUZZ ACTIVE" : "BUZZ MUTE"}
              </button>
            </div>

            {/* VIDEO FEED */}
            <div className="flex flex-col gap-1 text-left">
              <span className="text-[8px] text-zinc-500 uppercase tracking-widest font-black font-mono">VTX (Feed)</span>
              <button
                onClick={() => {
                  playSwitchClick();
                  setAnalogFeed(!analogFeed);
                  playBeep(1800, 0.08);
                }}
                className={`py-2.5 px-3.5 border rounded-xl text-[10px] font-black uppercase tracking-wider transition-all cursor-pointer ${
                  analogFeed
                    ? "bg-cyan-950/15 border-cyan-800/60 text-cyan-400"
                    : "bg-teal-950/20 border-teal-800/60 text-teal-400"
                }`}
              >
                {analogFeed ? "ANALOG" : "DIGITAL HD"}
              </button>
            </div>

          </div>

        </div>

        {/* Subtle GPS failsafe testing trigger info */}
        {failsafeTest && (
          <div className="mt-4 w-full bg-red-950/25 text-red-400 border border-red-900/40 p-3 text-center rounded-xl text-[10px] font-mono tracking-widest animate-pulse uppercase font-black">
            ⚠️ WARNING [RTH ACTIVE] - GPS RESCUE TRIGGERED // HOMING AUTO CORRIDOR ACTIVE
          </div>
        )}

      </div>

    </div>
  );
}
